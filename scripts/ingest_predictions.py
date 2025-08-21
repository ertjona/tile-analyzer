import sqlite3
import pandas as pd
from pathlib import Path
import argparse
import sys
from tqdm import tqdm

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

DB_PATH = project_root / "database" / "analysis.db"

def ingest_live_data(csv_path, image_directory, model_name):
    """
    Performs a live ingestion of prediction data into the database.
    """
    print("--- Starting Live Ingestion ---")

    # --- 1. Load CSV and prepare data ---
    try:
        df = pd.read_csv(csv_path)
        df.rename(columns={
            'filepath': 'image_path',
            'predicted_class': 'classification',
            'raw_score': 'score'
        }, inplace=True)
        df['webp_filename'] = df['image_path'].apply(lambda p: Path(p).name)
        print(f"✅ Loaded {len(df)} rows from {csv_path.name}")
    except Exception as e:
        print(f"❌ ERROR reading CSV: {e}")
        return

    # --- 2. Connect to DB and get IDs ---
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        
        # Get Model ID
        model_id_record = conn.execute("SELECT id FROM Models WHERE name = ?", (model_name,)).fetchone()
        if model_id_record is None:
            print(f"❌ ERROR: Model name '{model_name}' not found in the 'Models' table. Please register the model first.")
            conn.close()
            return
        model_id = model_id_record[0]

        # Get Source File ID
        source_id_record = conn.execute("SELECT id FROM SourceFiles WHERE image_directory = ?", (image_directory,)).fetchone()
        if source_id_record is None:
            print(f"❌ ERROR: Directory '{image_directory}' not found in 'SourceFiles' table.")
            conn.close()
            return
        source_id = source_id_record[0]

        # Get all tiles for this source
        tiles_df = pd.read_sql_query("SELECT id, webp_filename FROM ImageTiles WHERE source_file_id = ?", conn, params=(source_id,))
        
    except sqlite3.Error as e:
        print(f"❌ ERROR during database lookup: {e}")
        return

    # --- 3. Match and Prepare Data for Insertion ---
    merged_df = pd.merge(df, tiles_df, on='webp_filename', how='inner')
    merged_df.rename(columns={'id': 'tile_id'}, inplace=True)
    merged_df['model_id'] = model_id
    
    records_to_insert = merged_df[['tile_id', 'model_id', 'score', 'classification']].to_dict('records')
    
    if not records_to_insert:
        print("⚠️ No matching records found to insert. Ingestion complete.")
        conn.close()
        return

    print(f"✅ Matched {len(records_to_insert)} records. Preparing to write to the database...")

    # --- 4. Write to Database ---
    try:
        cursor = conn.cursor()
        # Optional: Delete old predictions for this model and source file to prevent duplicates
        cursor.execute("""
            DELETE FROM Predictions WHERE model_id = ? AND tile_id IN (
                SELECT id FROM ImageTiles WHERE source_file_id = ?
            )
        """, (model_id, source_id))
        
        insert_query = "INSERT INTO Predictions (tile_id, model_id, score, predicted_class) VALUES (?, ?, ?, ?)"
        
        # Use tqdm for a progress bar during the database insert
        for record in tqdm(records_to_insert, desc="Inserting predictions"):
            cursor.execute(insert_query, (record['tile_id'], record['model_id'], record['score'], record['classification']))

        conn.commit()
        print(f"\n✅ Successfully inserted {len(records_to_insert)} prediction records.")

    except sqlite3.Error as e:
        print(f"❌ ERROR during database write operation: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest model prediction CSV data into the database.")
    parser.add_argument('--csv-path', type=Path, required=True, help='Path to the model prediction CSV file.')
    parser.add_argument('--image-directory', type=str, required=True, help='The EXACT image directory path (use Windows path).')
    parser.add_argument('--model-name', type=str, required=True, help="The name of the model as registered in the 'Models' table.")
    
    args = parser.parse_args()
    ingest_live_data(args.csv_path, args.image_directory, args.model_name)