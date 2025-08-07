# scripts/ingestion_script.py
import sqlite3
import json
import os
import re
from datetime import datetime
import argparse
from pathlib import Path

# --- Database Configuration ---
SCRIPT_DIR = Path(__file__).resolve().parent
DB_FOLDER = SCRIPT_DIR.parent / "database"
DB_NAME = 'analysis.db'
DB_PATH = DB_FOLDER / DB_NAME

# --- Core Logic ---

def process_single_json(file_path, db_connection):
    """
    Parses a single JSON file and inserts its data into the database
    using optimized bulk insertion.
    """
    cursor = db_connection.cursor()
    filename = os.path.basename(file_path)

    cursor.execute("SELECT id FROM SourceFiles WHERE json_filename = ?", (filename,))
    if cursor.fetchone():
        print(f"Skipping '{filename}', already ingested.")
        return

    print(f"Processing '{filename}'...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print(f"  ERROR: Could not read or decode '{filename}'.")
        return

    # Insert into SourceFiles
    image_directory = data.get("image_directory", "")
    ingested_at_str = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO SourceFiles (json_filename, image_directory, ingested_at) VALUES (?, ?, ?)",
        (filename, image_directory, ingested_at_str)
    )
    source_file_id = cursor.lastrowid

    # --- OPTIMIZATION: Prepare data for executemany() instead of inserting in a loop ---
    tiles_to_insert = []
    tiles = data.get("tiles", {})
    for tile_name, attributes in tiles.items():
        if not isinstance(attributes, dict):
            continue

        tile_values = (
            source_file_id,
            tile_name,
            attributes.get('status'),
            attributes.get('col'),
            attributes.get('row'),
            attributes.get('size'),
            attributes.get('laplacian'),
            attributes.get('avg_brightness'),
            attributes.get('avg_saturation'),
            attributes.get('entropy'),
            attributes.get('edge_density'),
            attributes.get('edge_density_3060'),
            attributes.get('foreground_ratio'),
            attributes.get('max_subject_area')
        )
        tiles_to_insert.append(tile_values)

    # --- OPTIMIZATION: Execute a single bulk insert operation ---
    if tiles_to_insert:
        cursor.executemany(
            '''INSERT INTO ImageTiles (source_file_id, webp_filename, status, col, row, size,
                                      laplacian, avg_brightness, avg_saturation, entropy, edge_density, edge_density_3060,
                                      foreground_ratio, max_subject_area)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            tiles_to_insert
        )

    # The commit will happen in the main() loop after this function returns
    print(f"  Successfully prepared '{filename}' with {len(tiles_to_insert)} tiles for ingestion.")

# --- Main Execution Block ---

def main():
    parser = argparse.ArgumentParser(
        description='Ingest JSON metric files into the SQLite database.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('input_folder', type=str, help='Path to the folder containing JSON metric files.')
    args = parser.parse_args()

    folder_path = Path(args.input_folder)
    if not folder_path.is_dir():
        print(f"Error: Input folder not found at '{folder_path}'")
        return

    DB_FOLDER.mkdir(parents=True, exist_ok=True)
    
    try:
        json_files = [p for p in folder_path.glob('*.json')]
    except Exception as e:
        print(f"Error listing files in '{folder_path}': {e}")
        return

    if not json_files:
        print("No JSON files found to process.")
        return

    conn = sqlite3.connect(DB_PATH, timeout=30) # Increase timeout for busy DB
    
    # --- OPTIMIZATION: Set PRAGMAs for the life of the connection ---
    print("Applying performance PRAGMAs to database connection...")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -1000000;") # 1GB cache

    try:
        # --- OPTIMIZATION: Wrap the entire ingestion process in a single transaction ---
        print("Beginning ingestion transaction...")
        conn.execute("BEGIN TRANSACTION;")
        
        for file_path in json_files:
            process_single_json(file_path, conn)

        # Commit all changes at the very end
        conn.execute("COMMIT;")
        print("\nIngestion complete. All changes committed.")

    except sqlite3.Error as e:
        print(f"\nAn error occurred: {e}. Rolling back changes.")
        conn.rollback()
    finally:
        conn.close()
        print("Database connection closed.")


if __name__ == '__main__':
    main()