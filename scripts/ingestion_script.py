# scripts/ingestion_script.py
import sqlite3
import json
import os
import re
from datetime import datetime

# --- Database Configuration ---
DB_PATH = '../database/analysis.db'

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
            attributes.get('edge_density')
        )
        
        cursor.execute(
            '''INSERT INTO ImageTiles (source_file_id, webp_filename, status, col, row, size, 
                                      laplacian, avg_brightness, avg_saturation, entropy, edge_density)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            tile_values
        )
        tile_count += 1

    # 4. Commit the transaction for the entire file
    db_connection.commit()
    print(f"  Successfully ingested '{filename}' with {tile_count} tiles.")


# --- Main Execution Block ---

def main():
    # In a real app, you might get this from an argument
    folder_path = r'T:\tile_data\pathnet-json' # <-- IMPORTANT: Set this path

    # Use your existing file discovery logic
    try:
        file_pattern = r'.*\.json'
        filename_re = re.compile(file_pattern)
        all_files = os.listdir(folder_path)
        json_files = [os.path.join(folder_path, f) for f in all_files if filename_re.fullmatch(f)]
    except FileNotFoundError:
        print(f"Error: Source folder not found at '{folder_path}'")
        return

    if not json_files:
        print("No JSON files found to process.")
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