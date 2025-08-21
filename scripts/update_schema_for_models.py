import sqlite3
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

DB_PATH = project_root / "database" / "analysis.db"

def update_database_schema():
    """
    Connects to the database and adds the new Models and Predictions
    tables required for storing ML model results.
    """
    if not DB_PATH.exists():
        print(f"❌ ERROR: Database not found at {DB_PATH}")
        print("Please run create_database.py first.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        print(f"✅ Connected to database: {DB_PATH}")

        # --- Create Models Table ---
        print("Creating 'Models' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            version TEXT,
            type TEXT,
            class_names TEXT,
            path TEXT
        );
        """)

        # --- Create Predictions Table ---
        print("Creating 'Predictions' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tile_id INTEGER NOT NULL,
            model_id INTEGER NOT NULL,
            score REAL,
            predicted_class TEXT,
            FOREIGN KEY (tile_id) REFERENCES ImageTiles (id),
            FOREIGN KEY (model_id) REFERENCES Models (id)
        );
        """)

        # --- Create Indexes for Performance ---
        print("Creating indexes on new tables...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_tile_id ON Predictions (tile_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_model_id ON Predictions (model_id);")

        conn.commit()
        print("✅ Database schema updated successfully.")

    except sqlite3.Error as e:
        print(f"❌ An error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    update_database_schema()