import sqlite3
import folium
import requests
from fuzzywuzzy import process, fuzz
from datetime import datetime
from flask import Flask, render_template, request, g, jsonify
import time

# Add this near the top of your file, after the imports
timestamp = int(time.time())

app = Flask(__name__)

DATABASE = 'kmb.db'


def get_db():
    if '_database' not in g:
        g._database = sqlite3.connect(DATABASE)
    return g._database


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
    with get_db() as db:
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
    return render_template('index.html', routes=routes, timestamp=timestamp)


@app.route('/search-routes', methods=['GET'])
def search_routes():
    query = request.args.get('route-search', '')
    app.logger.info(f"Search query: {query}")
    routes = {f"{route}|{bound}": destination for route, bound, destination in g.routes}

    def custom_scorer(query, key_value):
        route_bound, destination = key_value
        route = route_bound.split('|')[0]
        route_score = fuzz.ratio(query.lower(), route.lower()) * 2  # Give more weight to exact route matches
        dest_score = fuzz.partial_ratio(query.lower(), destination.lower())  # Partial match for destinations
        return max(route_score, dest_score)
    
    results = process.extractBests(query, routes.items(), scorer=custom_scorer, score_cutoff=40, limit=50)

    response = [
        f'<div class="route-option" data-id="{route_bound}">{route_bound.split("|")[0]} - {destination} (Score: {score})</div>'
        for (route_bound, destination), score in results
    ]

    app.logger.info(f"Search results: {response}")
    return '\n'.join(response)


@app.route('/update-options', methods=['GET'])
def update_options():
    route = request.args.get('route', '').strip()
    direction = request.args.get('direction', '').strip()
    stops = get_stops_by_route_and_bound(route, direction)
    # Return the stop options as a string of <option> elements
    options = ''.join([
        f'<option value="{stop_name},{stop_id},{stop_long},{stop_lat}">{stop_name}</option>' 
        for stop_name, stop_id, stop_long, stop_lat in stops
    ])
    return options


@app.route('/update', methods=['GET'])
def update():
    # Get the selected items from the dropdown menus
    stop_data = request.args.get('stop', '')
    route_data = request.args.get('route', '')
    route, direction = route_data.split('|')
    route = route.strip()
    direction = direction.strip()

    stop_name, stop_id, stop_long, stop_lat = stop_data.split(',')
    stop_name = stop_name.strip()
    stop_id = stop_id.strip()
    stop_long = float(stop_long.strip())
    stop_lat = float(stop_lat.strip())

    folium_map = folium.Map(location=[stop_lat, stop_long], zoom_start=18, tiles='CartoDB Voyager')
    folium.Marker([stop_lat, stop_long], popup=stop_name).add_to(folium_map)
    map_html = folium_map._repr_html_()

    bus_eta = get_bus_eta(route, direction, stop_id)
    print(route, direction, stop_id)
    map_content = render_template('map.html', map_html=map_html)
    table_content = render_template('table.html', bus_eta=bus_eta)
    return jsonify({
        'map': map_content,
        'table': table_content
    })


       
def get_bus_eta(bus_no: str, direction: str, stop: str):
    eta_url = f"https://data.etabus.gov.hk/v1/transport/kmb/eta/{stop}/{bus_no}/1"
    curr_time = datetime.now().replace(tzinfo=None)

    try:
        content = requests.get(eta_url).json()['data']
        content = [c for c in content if c['dir'] == direction]  # ensures same direction
        content = [c for c in content if c['eta'] != '']
        content = [calculate_time_diff(curr_time, c['eta']) for c in content]
        return list(sorted(content))
    except requests.exceptions.RequestException as e:
        print('Exception', e)
        return []


def calculate_time_diff(curr, eta):
    try:
        eta = datetime.fromisoformat(eta)
        eta = eta.replace(tzinfo=None)
        diff = eta - curr
        return round(diff.total_seconds() / 60)
    except ValueError as e:
        print('Exception', e)
        return -1


if __name__ == '__main__':
    app.run(debug=True)
