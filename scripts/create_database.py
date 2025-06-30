import sqlite3
import os

# Define the path for the database relative to the script's location
DB_FOLDER = '../database'
DB_NAME = 'analysis.db'
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def create_database():
    """Creates the SQLite database and the necessary tables."""

    # Ensure the database folder exists
    os.makedirs(DB_FOLDER, exist_ok=True)

    print(f"Connecting to database at '{os.path.abspath(DB_PATH)}'...")

    # a .db file will be created if it does not exist
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Creating table: SourceFiles...")
    # SQL statement to create the SourceFiles table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS SourceFiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        json_filename TEXT NOT NULL UNIQUE,
        image_directory TEXT NOT NULL,
        ingested_at DATETIME NOT NULL
    );
    ''')

    print("Creating table: ImageTiles...")
    # SQL statement to create the ImageTiles table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ImageTiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_file_id INTEGER NOT NULL,
        webp_filename TEXT NOT NULL,
        status TEXT,
        col INTEGER,
        row INTEGER,
        size INTEGER,
        laplacian REAL,
        avg_brightness REAL,
        avg_saturation REAL,
        entropy REAL,
        edge_density REAL,
        FOREIGN KEY (source_file_id) REFERENCES SourceFiles (id)
    );
    ''')

    print("Tables created successfully.")

    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    print("Database connection closed.")


if __name__ == '__main__':
    create_database()
