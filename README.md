# KMB Bus ETA

Simple, stupid KMB bus arrival times

A real-time bus tracker for Kowloon Motor Bus (KMB) routes in Hong Kong, available in both web and terminal interfaces.

## Features

- Real-time bus arrival information
- Fuzzy route search
- Interactive stop selection
- Web interface (Flask) and Terminal UI (ratatui)

## Installation

### Prerequisites

**For Web Interface:**
- Python 3.7+
- pip

**For Terminal UI:**
- Rust 1.70+ and Cargo

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd kmb-eta
```

2. Set up the database:
```bash
cd web
pip install -r requirements.txt
python populate_db.py init_db
python populate_db.py populate_all
```

This will create `kmb.db` with all route and stop information.

## Usage

### Web Interface

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Flask application:
```bash
cd web
python app.py
```

3. Open your browser to `http://localhost:5000`

4. Search for a route, select a stop, and view real-time ETAs!

### Terminal UI (TUI)

1. Build the Rust application:
```bash
cargo build --release
```

2. Run the TUI:
```bash
cargo run --release
```

Or specify a custom database path:
```bash
cargo run --release -- /path/to/kmb.db
```

#### TUI Controls

**Route Search Screen:**
- Type to search for routes (fuzzy matching)
- `↑/↓` - Navigate through routes
- `Enter` - Select route
- `Esc` or `q` - Quit

**Stop Selection Screen:**
- `↑/↓` - Navigate through stops
- `Enter` - View ETA for selected stop
- `Esc` - Go back to route search
- `q` - Quit

**ETA Display Screen:**
- `R` - Refresh ETA data
- `Esc` - Go back to stop selection
- `Q` - Quit

## Project Structure

```
kmb-eta/
├── Cargo.toml              # Rust dependencies
├── src/
│   └── main.rs            # Terminal UI application
├── web/
│   ├── app.py             # Flask web application
│   ├── populate_db.py     # Database setup CLI
│   ├── templates/         # HTML templates
│   └── static/            # CSS/JS assets
├── kmb.db                 # SQLite database (generated)
└── requirements.txt       # Python dependencies
```

## Technologies

**Web Interface:**
- Flask
- HTMX
- Bootstrap 4
- Folium (maps)
- FuzzyWuzzy (fuzzy matching)

**Terminal UI:**
- Ratatui (TUI framework)
- Crossterm (terminal handling)
- Tokio (async runtime)
- Rusqlite (SQLite)
- Fuzzy-matcher (fuzzy search)

## Data Source

Real-time ETA data is fetched from the Hong Kong government's open data API:
`https://data.etabus.gov.hk/v1/transport/kmb/`

## License

MIT License - see LICENSE file for details

