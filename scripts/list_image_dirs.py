import sqlite3
from pathlib import Path
import sys

# Add project root to path to allow importing from lib
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

DB_PATH = project_root / "database" / "analysis.db"

def list_unique_directories():
    """
    Connects to the database and prints a unique list of all image_directory paths.
    """
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Query for distinct directory paths from the SourceFiles table
        cursor.execute("SELECT DISTINCT image_directory FROM SourceFiles ORDER BY image_directory")
        
        directories = [row[0] for row in cursor.fetchall()]

        if not directories:
            print("No image directories found in the database.")
            return

        #print("# List of unique image directories from the database:")
        for directory in directories:
            print(directory)

    except sqlite3.Error as e:
        print(f"An error occurred while querying the database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    list_unique_directories()