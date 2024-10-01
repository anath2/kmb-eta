import sqlite3
import folium
import requests
from datetime import datetime
from flask import Flask, render_template, request, g

app = Flask(__name__)

DATABASE = 'kmb.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def get_all_routes():
    if 'routes' not in g:
        db = get_db()
        cur = db.execute('SELECT route, bound, destination FROM routes')
        g.routes = cur.fetchall()  # Store the result in g
    return g.routes


@app.before_request
def before_request():
    g.routes = get_all_routes()
    g.route_selected = None
    g.direction_selected = None
    g.route_stops = []


def get_stops_by_route_and_bound(route, bound):
    db = get_db()
    cur = db.execute('''
        SELECT stops.name, stops.stop, stops.long, stops.lat
        FROM route_stops
        JOIN stops ON route_stops.stop = stops.stop
        WHERE route_stops.route = ? AND route_stops.bound = ?
    ''', (route, bound))                     
    stops = cur.fetchall()
    return stops


# Route to serve the main index.html
@app.route('/')
def index():
    routes = g.routes
    return render_template('index.html', routes=routes)


# Route to handle HTMX requests for updates
@app.route('/update', methods=['GET'])
def update():
    # Get the selected items from the dropdown menus
    stop_data = request.args.get('stop', '')
    route, dir = request.args.get('route', '').split(',')
    route = route.strip()
    dir = dir.strip()

    stop_name, stop_id, stop_long, stop_lat = stop_data.split(',')
    stop_name = stop_name.strip()
    stop_id = stop_id.strip()
    stop_long = float(stop_long.strip())
    stop_lat = float(stop_lat.strip())

    folium_map = folium.Map(location=[stop_lat, stop_long], zoom_start=20)
    folium.Marker([stop_lat, stop_long], popup=stop_name).add_to(folium_map)
    map_html = folium_map._repr_html_()

    bus_eta = get_bus_eta(route, dir, stop_id)
    return render_template('update.html', route=route, stop=stop_name, bus_eta=bus_eta, map_html=map_html)


@app.route('/update-options', methods=['GET'])
def update_options():
    route, bound = request.args.get('route', '').split(',')
    route = route.strip()
    bound = bound.strip()
    stops = get_stops_by_route_and_bound(route, bound)
    # Return the stop options as a string of <option> elements
    options = ''.join([
        f'<option value="{stop_name},{stop_id},{stop_long},{stop_lat}">{stop_name}</option>' 
        for stop_name, stop_id, stop_long, stop_lat in stops
    ])
    return options

       
def get_bus_eta(bus_no: str, bound: str, stop: str):
    eta_url = f"https://data.etabus.gov.hk/v1/transport/kmb/eta/{stop}/{bus_no}/1"
    curr_time = datetime.now()

    try:
        content = requests.get(eta_url).json()['data']
        content = [c for c in content if c['dir'] == bound]  # ensures same direction
        content = [c for c in content if c['eta'] != '']
        content = [calculate_time_diff(curr_time, c['eta']) for c in content]
        return list(sorted(content))
    except Exception as e:
        print('Exception', e)
        return []


def calculate_time_diff(curr, eta):
    eta = datetime.fromisoformat(eta)
    eta = eta.replace(tzinfo=None)  # Remove timezone info
    diff = eta - curr
    return round(diff.total_seconds() / 60)


if __name__ == '__main__':
    app.run(debug=True)