import sqlite3
import click
import requests

# Define your SQLite database path
DATABASE = 'kmb.db'

# Helper function to get a database connection
def get_db():
    db = sqlite3.connect(DATABASE)
    return db

# Close the database connection when done
def close_connection():
    db = sqlite3.connect(DATABASE)
    db.close()


# Create tables if they do not exist
def create_tables():
    conn = sqlite3.connect(DATABASE)
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        route TEXT NOT NULL, 
        bound TEXT NOT NULL,
        origin TEXT NOT NULL,
        destination TEXT NOT NULL,
        service_type TEXT NOT NULL
    );                   

    CREATE TABLE IF NOT EXISTS stops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stop TEXT NOT NULL, 
        lat NUMERIC NOT NULL,
        long NUMERIC NOT NULL,
        name TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS route_stops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        route TEXT NOT NULL,
        bound TEXT NOT NULL,
        seq INTEGER NOT NULL,
        stop TEXT NOT NULL
    );
    ''')
    conn.commit()
    conn.close()


# Fetch data from the REST API and populate the 'routes' table
def fetch_and_populate_routes():
    api_url = 'https://data.etabus.gov.hk/v1/transport/kmb/route/'

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()['data']

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()

            for item in data:
                route = item['route']
                bound = item['bound']
                origin = item['orig_en']
                destination = item['dest_en']
                service_type = item['service_type']

                cursor.execute('INSERT INTO routes (route, bound, origin, destination, service_type) VALUES (?, ?, ?, ?, ?)',
                               (route, bound, origin, destination, service_type))

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")


# Fetch data from the REST API and populate the 'stops' table
def fetch_and_populate_stops():
    api_url = 'https://data.etabus.gov.hk/v1/transport/kmb/stop/'

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()['data']

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()

            for item in data:
                stop = item['stop']
                lat = item['lat']
                long = item['long']
                name = item['name_en']

                cursor.execute('INSERT INTO stops (stop, lat, long, name) VALUES (?, ?, ?, ?)',
                               (stop, lat, long, name))

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")


# Fetch data from the REST API and populate the 'route_stops' table
def fetch_and_populate_route_stops():
    api_url = 'https://data.etabus.gov.hk/v1/transport/kmb/route-stop/'

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()['data']

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()

            for item in data:
                route = item['route']
                bound = item['bound']
                seq = item['seq']
                stop = item['stop']
                cursor.execute('INSERT INTO route_stops (route, bound, seq, stop) VALUES (?, ?, ?, ?)',
                               (route, bound, seq, stop))

            conn.commit()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")


# Grouping the commands together
@click.group()
def cli():
    pass


# Adding the commands under the CLI group
@cli.command()
def init_db():
    create_tables()
    print("Database initialized.")


@cli.command()
def populate_routes():
    fetch_and_populate_routes()
    print("Routes populated.")


@cli.command()
def populate_stops():
    fetch_and_populate_stops()
    print("Stops populated.")


@cli.command()
def populate_route_stops():
    fetch_and_populate_route_stops()
    print("Route stops populated.")


@cli.command()
def populate_all():
    create_tables()
    fetch_and_populate_routes()
    fetch_and_populate_stops()
    fetch_and_populate_route_stops()
    print("All data populated.")


if __name__ == '__main__':
    cli()