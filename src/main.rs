use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use fuzzy_matcher::skim::SkimMatcherV2;
use fuzzy_matcher::FuzzyMatcher;
use ratatui::{
    backend::{Backend, CrosstermBackend},
    layout::{Alignment, Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span, Text},
    widgets::{Block, Borders, Cell, List, ListItem, ListState, Paragraph, Row, Table, TableState},
    Frame, Terminal,
};
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use std::io;

#[derive(Debug, Clone)]
struct Route {
    route: String,
    bound: String,
    service_type: String,
    orig_tc: String,
    dest_tc: String,
}

#[derive(Debug, Clone)]
struct Stop {
    stop: String,
    name_tc: String,
    seq: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct EtaData {
    co: String,
    route: String,
    dir: String,
    service_type: i32,
    seq: i32,
    dest_tc: String,
    dest_sc: String,
    dest_en: String,
    eta_seq: i32,
    eta: Option<String>,
    rmk_tc: Option<String>,
    rmk_sc: Option<String>,
    rmk_en: Option<String>,
    data_timestamp: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct EtaResponse {
    #[serde(rename = "type")]
    response_type: String,
    version: String,
    generated_timestamp: String,
    data: Vec<EtaData>,
}

#[derive(Debug)]
struct EtaDisplay {
    destination: String,
    eta: String,
    remarks: String,
}

enum AppState {
    RouteSearch,
    StopSelection,
    EtaDisplay,
}

struct App {
    state: AppState,
    search_input: String,
    routes: Vec<Route>,
    filtered_routes: Vec<(Route, i64)>,
    selected_route_index: usize,
    stops: Vec<Stop>,
    selected_stop_index: usize,
    eta_data: Vec<EtaDisplay>,
    route_list_state: ListState,
    stop_list_state: ListState,
    eta_table_state: TableState,
    db_path: String,
}

impl App {
    fn new(db_path: String) -> Result<Self> {
        let mut app = App {
            state: AppState::RouteSearch,
            search_input: String::new(),
            routes: Vec::new(),
            filtered_routes: Vec::new(),
            selected_route_index: 0,
            stops: Vec::new(),
            selected_stop_index: 0,
            eta_data: Vec::new(),
            route_list_state: ListState::default(),
            stop_list_state: ListState::default(),
            eta_table_state: TableState::default(),
            db_path,
        };

        app.load_routes()?;
        Ok(app)
    }

    fn load_routes(&mut self) -> Result<()> {
        let conn = Connection::open(&self.db_path)?;
        let mut stmt = conn.prepare(
            "SELECT route, bound, service_type, orig_tc, dest_tc FROM routes ORDER BY route"
        )?;

        let routes = stmt.query_map([], |row| {
            Ok(Route {
                route: row.get(0)?,
                bound: row.get(1)?,
                service_type: row.get(2)?,
                orig_tc: row.get(3)?,
                dest_tc: row.get(4)?,
            })
        })?;

        self.routes = routes.collect::<Result<Vec<_>, _>>()?;
        self.update_filtered_routes();
        Ok(())
    }

    fn update_filtered_routes(&mut self) {
        if self.search_input.is_empty() {
            self.filtered_routes = self.routes.iter()
                .take(20)
                .map(|r| (r.clone(), 0i64))
                .collect();
        } else {
            let matcher = SkimMatcherV2::default();
            let mut scored_routes: Vec<(Route, i64)> = self.routes
                .iter()
                .filter_map(|route| {
                    let search_text = format!("{} {} {}", route.route, route.orig_tc, route.dest_tc);
                    matcher.fuzzy_match(&search_text, &self.search_input)
                        .map(|score| (route.clone(), score))
                })
                .collect();

            scored_routes.sort_by(|a, b| b.1.cmp(&a.1));
            self.filtered_routes = scored_routes.into_iter().take(20).collect();
        }

        self.selected_route_index = 0;
        if !self.filtered_routes.is_empty() {
            self.route_list_state.select(Some(0));
        }
    }

    fn select_route(&mut self) -> Result<()> {
        if let Some(route) = self.filtered_routes.get(self.selected_route_index) {
            self.load_stops(&route.0)?;
            self.state = AppState::StopSelection;
            self.selected_stop_index = 0;
            if !self.stops.is_empty() {
                self.stop_list_state.select(Some(0));
            }
        }
        Ok(())
    }

    fn load_stops(&mut self, route: &Route) -> Result<()> {
        let conn = Connection::open(&self.db_path)?;
        let mut stmt = conn.prepare(
            "SELECT s.stop, s.name_tc, rs.seq
             FROM route_stops rs
             JOIN stops s ON rs.stop = s.stop
             WHERE rs.route = ?1 AND rs.bound = ?2 AND rs.service_type = ?3
             ORDER BY rs.seq"
        )?;

        let stops = stmt.query_map(
            params![&route.route, &route.bound, &route.service_type],
            |row| {
                Ok(Stop {
                    stop: row.get(0)?,
                    name_tc: row.get(1)?,
                    seq: row.get(2)?,
                })
            }
        )?;

        self.stops = stops.collect::<Result<Vec<_>, _>>()?;
        Ok(())
    }

    async fn fetch_eta(&mut self) -> Result<()> {
        if let Some(route) = self.filtered_routes.get(self.selected_route_index) {
            if let Some(stop) = self.stops.get(self.selected_stop_index) {
                let url = format!(
                    "https://data.etabus.gov.hk/v1/transport/kmb/stop-eta/{}",
                    stop.stop
                );

                let client = reqwest::Client::new();
                let response = client.get(&url)
                    .send()
                    .await?
                    .json::<EtaResponse>()
                    .await?;

                let selected_route = &route.0;
                let mut eta_displays: Vec<EtaDisplay> = response.data
                    .into_iter()
                    .filter(|eta| {
                        eta.route == selected_route.route &&
                        eta.dir == selected_route.bound &&
                        eta.service_type.to_string() == selected_route.service_type
                    })
                    .map(|eta| {
                        let eta_str = if let Some(eta_time) = eta.eta {
                            if let Ok(eta_dt) = DateTime::parse_from_rfc3339(&eta_time) {
                                let now = Utc::now();
                                let duration = eta_dt.signed_duration_since(now);
                                let minutes = duration.num_minutes();
                                if minutes <= 0 {
                                    "Arriving".to_string()
                                } else {
                                    format!("{} min", minutes)
                                }
                            } else {
                                "N/A".to_string()
                            }
                        } else {
                            "N/A".to_string()
                        };

                        EtaDisplay {
                            destination: eta.dest_tc.clone(),
                            eta: eta_str,
                            remarks: eta.rmk_tc.unwrap_or_default(),
                        }
                    })
                    .collect();

                if eta_displays.is_empty() {
                    eta_displays.push(EtaDisplay {
                        destination: "No upcoming buses".to_string(),
                        eta: "-".to_string(),
                        remarks: "".to_string(),
                    });
                }

                self.eta_data = eta_displays;
                self.state = AppState::EtaDisplay;
                self.eta_table_state.select(Some(0));
            }
        }
        Ok(())
    }

    fn next_route(&mut self) {
        if !self.filtered_routes.is_empty() {
            self.selected_route_index = (self.selected_route_index + 1) % self.filtered_routes.len();
            self.route_list_state.select(Some(self.selected_route_index));
        }
    }

    fn previous_route(&mut self) {
        if !self.filtered_routes.is_empty() {
            if self.selected_route_index > 0 {
                self.selected_route_index -= 1;
            } else {
                self.selected_route_index = self.filtered_routes.len() - 1;
            }
            self.route_list_state.select(Some(self.selected_route_index));
        }
    }

    fn next_stop(&mut self) {
        if !self.stops.is_empty() {
            self.selected_stop_index = (self.selected_stop_index + 1) % self.stops.len();
            self.stop_list_state.select(Some(self.selected_stop_index));
        }
    }

    fn previous_stop(&mut self) {
        if !self.stops.is_empty() {
            if self.selected_stop_index > 0 {
                self.selected_stop_index -= 1;
            } else {
                self.selected_stop_index = self.stops.len() - 1;
            }
            self.stop_list_state.select(Some(self.selected_stop_index));
        }
    }
}

fn ui<B: Backend>(f: &mut Frame, app: &mut App) {
    match app.state {
        AppState::RouteSearch => render_route_search(f, app),
        AppState::StopSelection => render_stop_selection(f, app),
        AppState::EtaDisplay => render_eta_display(f, app),
    }
}

fn render_route_search<B: Backend>(f: &mut Frame, app: &mut App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .margin(2)
        .constraints([
            Constraint::Length(3),
            Constraint::Min(1),
            Constraint::Length(3),
        ])
        .split(f.area());

    let title = Paragraph::new("KMB Bus ETA - Route Search")
        .style(Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD))
        .alignment(Alignment::Center)
        .block(Block::default().borders(Borders::ALL));
    f.render_widget(title, chunks[0]);

    let input = Paragraph::new(app.search_input.as_str())
        .style(Style::default().fg(Color::Yellow))
        .block(Block::default().borders(Borders::ALL).title("Search Route"));
    f.render_widget(input, chunks[2]);

    let items: Vec<ListItem> = app.filtered_routes
        .iter()
        .map(|(route, _score)| {
            let content = format!(
                "{} - {} → {}",
                route.route, route.orig_tc, route.dest_tc
            );
            ListItem::new(content)
        })
        .collect();

    let list = List::new(items)
        .block(Block::default().borders(Borders::ALL).title("Routes"))
        .highlight_style(
            Style::default()
                .bg(Color::Blue)
                .add_modifier(Modifier::BOLD)
        )
        .highlight_symbol(">> ");

    f.render_stateful_widget(list, chunks[1], &mut app.route_list_state);
}

fn render_stop_selection<B: Backend>(f: &mut Frame, app: &mut App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .margin(2)
        .constraints([
            Constraint::Length(3),
            Constraint::Min(1),
            Constraint::Length(3),
        ])
        .split(f.area());

    let route_info = if let Some(route) = app.filtered_routes.get(app.selected_route_index) {
        format!("Route {} - {} → {}", route.0.route, route.0.orig_tc, route.0.dest_tc)
    } else {
        "No route selected".to_string()
    };

    let title = Paragraph::new(route_info)
        .style(Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD))
        .alignment(Alignment::Center)
        .block(Block::default().borders(Borders::ALL));
    f.render_widget(title, chunks[0]);

    let items: Vec<ListItem> = app.stops
        .iter()
        .map(|stop| {
            let content = format!("{}. {}", stop.seq, stop.name_tc);
            ListItem::new(content)
        })
        .collect();

    let list = List::new(items)
        .block(Block::default().borders(Borders::ALL).title("Select Stop"))
        .highlight_style(
            Style::default()
                .bg(Color::Blue)
                .add_modifier(Modifier::BOLD)
        )
        .highlight_symbol(">> ");

    f.render_stateful_widget(list, chunks[1], &mut app.stop_list_state);

    let help = Paragraph::new("Press Enter to view ETA | Esc to go back")
        .style(Style::default().fg(Color::Gray))
        .alignment(Alignment::Center)
        .block(Block::default().borders(Borders::ALL));
    f.render_widget(help, chunks[2]);
}

fn render_eta_display<B: Backend>(f: &mut Frame, app: &mut App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .margin(2)
        .constraints([
            Constraint::Length(3),
            Constraint::Length(5),
            Constraint::Min(1),
            Constraint::Length(3),
        ])
        .split(f.area());

    let title = Paragraph::new("KMB Bus ETA")
        .style(Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD))
        .alignment(Alignment::Center)
        .block(Block::default().borders(Borders::ALL));
    f.render_widget(title, chunks[0]);

    let route_info = if let Some(route) = app.filtered_routes.get(app.selected_route_index) {
        if let Some(stop) = app.stops.get(app.selected_stop_index) {
            vec![
                Line::from(format!("Route: {}", route.0.route)),
                Line::from(format!("Stop: {}", stop.name_tc)),
                Line::from(format!("Direction: {} → {}", route.0.orig_tc, route.0.dest_tc)),
            ]
        } else {
            vec![Line::from("No stop selected")]
        }
    } else {
        vec![Line::from("No route selected")]
    };

    let info = Paragraph::new(route_info)
        .block(Block::default().borders(Borders::ALL).title("Route Information"));
    f.render_widget(info, chunks[1]);

    let header = Row::new(vec!["Destination", "ETA", "Remarks"])
        .style(Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD))
        .height(1);

    let rows: Vec<Row> = app.eta_data
        .iter()
        .map(|eta| {
            Row::new(vec![
                Cell::from(eta.destination.clone()),
                Cell::from(eta.eta.clone()),
                Cell::from(eta.remarks.clone()),
            ])
        })
        .collect();

    let table = Table::new(
        rows,
        [Constraint::Percentage(40), Constraint::Percentage(20), Constraint::Percentage(40)]
    )
        .header(header)
        .block(Block::default().borders(Borders::ALL).title("Estimated Time of Arrival"))
        .highlight_style(Style::default().bg(Color::DarkGray));

    f.render_stateful_widget(table, chunks[2], &mut app.eta_table_state);

    let help = Paragraph::new("Press R to refresh | Esc to go back | Q to quit")
        .style(Style::default().fg(Color::Gray))
        .alignment(Alignment::Center)
        .block(Block::default().borders(Borders::ALL));
    f.render_widget(help, chunks[3]);
}

#[tokio::main]
async fn main() -> Result<()> {
    let db_path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "kmb.db".to_string());

    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let mut app = App::new(db_path).context("Failed to initialize app")?;
    let res = run_app(&mut terminal, &mut app).await;

    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;

    if let Err(err) = res {
        eprintln!("Error: {:?}", err);
    }

    Ok(())
}

async fn run_app<B: Backend>(terminal: &mut Terminal<B>, app: &mut App) -> Result<()> {
    loop {
        terminal.draw(|f| ui(f, app))?;

        if let Event::Key(key) = event::read()? {
            if key.kind == KeyEventKind::Press {
                match app.state {
                    AppState::RouteSearch => {
                        match key.code {
                            KeyCode::Char('q') => return Ok(()),
                            KeyCode::Char(c) => {
                                app.search_input.push(c);
                                app.update_filtered_routes();
                            }
                            KeyCode::Backspace => {
                                app.search_input.pop();
                                app.update_filtered_routes();
                            }
                            KeyCode::Down => app.next_route(),
                            KeyCode::Up => app.previous_route(),
                            KeyCode::Enter => app.select_route()?,
                            KeyCode::Esc => return Ok(()),
                            _ => {}
                        }
                    }
                    AppState::StopSelection => {
                        match key.code {
                            KeyCode::Down => app.next_stop(),
                            KeyCode::Up => app.previous_stop(),
                            KeyCode::Enter => app.fetch_eta().await?,
                            KeyCode::Esc => {
                                app.state = AppState::RouteSearch;
                            }
                            KeyCode::Char('q') => return Ok(()),
                            _ => {}
                        }
                    }
                    AppState::EtaDisplay => {
                        match key.code {
                            KeyCode::Char('r') | KeyCode::Char('R') => {
                                app.fetch_eta().await?;
                            }
                            KeyCode::Esc => {
                                app.state = AppState::StopSelection;
                            }
                            KeyCode::Char('q') | KeyCode::Char('Q') => return Ok(()),
                            _ => {}
                        }
                    }
                }
            }
        }
    }
}
