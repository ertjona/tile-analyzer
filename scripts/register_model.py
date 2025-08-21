import sqlite3
from pathlib import Path
import argparse
import json

# Define the database path
DB_PATH = Path(__file__).resolve().parent.parent / "database" / "analysis.db"

def register_model(name, version, model_type, class_names, path):
    """Inserts a new model record into the Models table."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print(f"Registering model '{name}' version '{version}'...")
        
        cursor.execute("""
        INSERT INTO Models (name, version, type, class_names, path)
        VALUES (?, ?, ?, ?, ?)
        """, (name, version, model_type, json.dumps(class_names), path))
        
        conn.commit()
        print("✅ Model registered successfully!")
        
    except sqlite3.IntegrityError:
        print(f"⚠️  WARNING: A model with the name '{name}' already exists. No new record was added.")
    except sqlite3.Error as e:
        print(f"❌ ERROR: An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Register a new ML model in the database.")
    parser.add_argument('--name', required=True, help="A unique name for the model (e.g., 'marker_classifier').")
    parser.add_argument('--version', required=True, help="The version of the model (e.g., '1.0').")
    parser.add_argument('--type', required=True, choices=['binary', 'multiclass'], help="The type of model.")
    parser.add_argument('--class-names', required=True, nargs='+', help="The output class names, in order (e.g., --class-names not_marker marker).")
    parser.add_argument('--path', required=True, help="The file path to the .keras model file.")
    
    args = parser.parse_args()
    register_model(args.name, args.version, args.type, args.class_names, args.path)