# scripts/ingestion_script.py
import sqlite3
import json
import os
import re
from datetime import datetime
import argparse # NEW: Import argparse for command-line arguments
from pathlib import Path # NEW: Import Path for robust path handling

# --- Database Configuration ---
# MODIFIED: Use Path for robust database path, relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
DB_FOLDER = SCRIPT_DIR.parent / "database"
DB_NAME = 'analysis.db'
DB_PATH = DB_FOLDER / DB_NAME

# --- Core Logic (Adapted from your JSONFileProcessor) ---

def process_single_json(file_path, db_connection):
    """
    Parses a single JSON file and inserts its data into the database.
    """
    cursor = db_connection.cursor()
    filename = os.path.basename(file_path)

    # 1. Check if the file has already been ingested (Idempotency)
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

    # 2. Insert into SourceFiles table
    image_directory = data.get("image_directory", "")
    ingested_at = datetime.now()
    
    # Convert the datetime object to an ISO 8601 formatted string
    ingested_at_str = ingested_at.isoformat()
    
    cursor.execute(
        "INSERT INTO SourceFiles (json_filename, image_directory, ingested_at) VALUES (?, ?, ?)",
        (filename, image_directory, ingested_at_str) # Use the string version
    )
    source_file_id = cursor.lastrowid # Get the ID of the new row


    # 3. Loop through tiles and insert into ImageTiles table
    tiles = data.get("tiles", {})
    tile_count = 0
    for tile_name, attributes in tiles.items():
        if not isinstance(attributes, dict):
            continue

        # Prepare a tuple of values in the correct order for the table columns
        # MODIFIED: Added foreground_ratio and max_subject_area
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
            attributes.get('foreground_ratio'), # NEW
            attributes.get('max_subject_area') # NEW
        )
        
        # MODIFIED: Added foreground_ratio and max_subject_area columns to INSERT statement
        cursor.execute(
            '''INSERT INTO ImageTiles (source_file_id, webp_filename, status, col, row, size, 
                                      laplacian, avg_brightness, avg_saturation, entropy, edge_density,
                                      foreground_ratio, max_subject_area)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            tile_values
        )
        tile_count += 1

    # 4. Commit the transaction for the entire file
    db_connection.commit()
    print(f"  Successfully ingested '{filename}' with {tile_count} tiles.")


# --- Main Execution Block (MODIFIED to use argparse) ---

def main():
    parser = argparse.ArgumentParser(
        description='Ingest JSON metric files into the SQLite database.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'input_folder',
        type=str,
        help='Path to the folder containing JSON metric files to ingest.'
    )
    args = parser.parse_args()

    # Use the input_folder from arguments
    folder_path = Path(args.input_folder)

    if not folder_path.is_dir():
        print(f"Error: Input folder not found or is not a directory at '{folder_path}'")
        return

    # Ensure the database folder exists before connecting
    DB_FOLDER.mkdir(parents=True, exist_ok=True)
    
    # Use your existing file discovery logic
    try:
        file_pattern = r'.*\.json'
        filename_re = re.compile(file_pattern)
        all_files = os.listdir(folder_path)
        json_files = [folder_path / f for f in all_files if filename_re.fullmatch(f)] # Use Path objects
    except FileNotFoundError: # This might be redundant due to folder_path.is_dir() check
        print(f"Error: Source folder not found at '{folder_path}'")
        return
    except Exception as e:
        print(f"Error listing files in '{folder_path}': {e}")
        return

    if not json_files:
        print("No JSON files found to process in the specified folder.")
        return
        
    # Establish a single database connection
    conn = sqlite3.connect(DB_PATH)
    try:
        for file_path in json_files:
            process_single_json(file_path, conn)
    finally:
        conn.close()
        print("Database connection closed.")


if __name__ == '__main__':
    main()