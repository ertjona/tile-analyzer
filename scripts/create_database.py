import sqlite3
import os
from pathlib import Path

# Define the path for the database relative to the script's location
SCRIPT_DIR = Path(__file__).resolve().parent
DB_FOLDER = SCRIPT_DIR.parent / "database"
DB_NAME = 'analysis.db'
DB_PATH = DB_FOLDER / DB_NAME

def create_database_with_indexes():
    """
    Deletes the old database (if it exists) and creates a new one
    with performance-oriented indexes.
    """
    # --- NEW: Delete the old database file before creating a new one ---
    if os.path.exists(DB_PATH):
        print(f"Deleting existing database at '{os.path.abspath(DB_PATH)}'...")
        os.remove(DB_PATH)

    # Ensure the database folder exists
    os.makedirs(DB_FOLDER, exist_ok=True)

    print(f"Connecting to database at '{os.path.abspath(DB_PATH)}'...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Optional but Recommended: Set performance PRAGMAs for the creation ---
    # This helps the creation process itself be faster.
    cursor.execute("PRAGMA journal_mode = WAL;")

    print("Creating table: SourceFiles...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS SourceFiles (
        id INTEGER PRIMARY KEY, -- Removed AUTOINCREMENT for clarity, it's default
        json_filename TEXT NOT NULL UNIQUE,
        image_directory TEXT NOT NULL,
        ingested_at DATETIME NOT NULL
    );
    ''')

    print("Creating table: ImageTiles...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ImageTiles (
        id INTEGER PRIMARY KEY,
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
        edge_density_3060 REAL,
        foreground_ratio REAL,
        max_subject_area REAL,
        FOREIGN KEY (source_file_id) REFERENCES SourceFiles (id)
    );
    ''')
    print("Tables created successfully.")

    # --- ACTION: Use this updated list of indexes ---
    print("Creating indexes on ImageTiles based on query patterns...")

    # Essential indexes from before
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_imagetiles_source_file_id ON ImageTiles (source_file_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_imagetiles_status ON ImageTiles (status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_imagetiles_lookup ON ImageTiles (source_file_id, col, row);")

    # --- Indexes for frequently queried metrics ---
    print("Creating indexes for user-queried metrics...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_imagetiles_laplacian ON ImageTiles (laplacian);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_imagetiles_edge_density ON ImageTiles (edge_density);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_imagetiles_edge_density_3060 ON ImageTiles (edge_density_3060);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_imagetiles_max_subject_area ON ImageTiles (max_subject_area);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_imagetiles_avg_brightness ON ImageTiles (avg_brightness);")
    
    print("Indexes created successfully.")

    conn.commit()
    conn.close()
    print("Database connection closed.")


if __name__ == '__main__':
    create_database_with_indexes()