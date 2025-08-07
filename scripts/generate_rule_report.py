# generate_rule_report.py

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path
# Get the project root directory (which is the parent of the 'scripts' folder)
project_root = Path(__file__).resolve().parent.parent
# Add the project root to Python's path
sys.path.append(str(project_root))

import pandas as pd

# --- Local Application Imports ---
# This imports the logic and Pydantic models from our shared library
from lib.reporting import generate_report_data, HeatmapRulesConfig


# --- 1. Setup Logging ---
# Configure logging to include timestamps, as you requested
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


# --- 2. Setup Command-Line Argument Parser ---
# This defines the --rule-file, --db-path, and --output-csv arguments
parser = argparse.ArgumentParser(
    description="Generate a rule-based analysis report from the database and save it as a CSV.",
    formatter_class=argparse.RawTextHelpFormatter
)
parser.add_argument(
    '--rule-file',
    type=Path,
    required=True,
    help='Path to the JSON file containing the heatmap rules.'
)
parser.add_argument(
    '--db-path',
    type=Path,
    required=True,
    help='Path to the SQLite database file (e.g., database/analysis.db).'
)
parser.add_argument(
    '--output-csv',
    type=Path,
    required=True,
    help='Path to save the final CSV report.'
)

# This is where the rest of our script's logic will go.
# We'll fill this in next.
if __name__ == "__main__":
    pass
    
# ... (keep all the code from Part A above this) ...

if __name__ == "__main__":
    args = parser.parse_args()

    logging.info("--- Report Generation Script Started ---")
    
    # --- 3. Load and Validate Rule File ---
    logging.info(f"Loading rules from: {args.rule_file}")
    if not args.rule_file.is_file():
        logging.error(f"Rule file not found at: {args.rule_file}")
        exit(1)
        
    with open(args.rule_file, 'r') as f:
        rules_data = json.load(f)
    
    # Use the Pydantic model for validation. This will raise an error if the file is malformed.
    try:
        rules_config = HeatmapRulesConfig(**rules_data).model_dump()
        logging.info("Rule file is valid and loaded successfully.")
    except Exception as e:
        logging.error(f"Invalid rule file format: {e}")
        exit(1)

    # --- 4. Connect to Database and Generate Report ---
    logging.info(f"Connecting to database: {args.db_path}")
    if not args.db_path.is_file():
        logging.error(f"Database not found at: {args.db_path}")
        exit(1)
        
    conn = sqlite3.connect(args.db_path)
    conn.row_factory = sqlite3.Row
    # Apply performance PRAGMAs for faster reads
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA cache_size = -1000000;") # Use a 1GB cache for this heavy script

    report_data = []
    try:
        logging.info("Querying database and generating report data... (This may take a while)")
        # Call the shared function to do the heavy lifting
        report_data = generate_report_data(conn, rules_config)
        logging.info("Data generation complete.")
    except Exception as e:
        logging.error(f"An error occurred during report generation: {e}")
    finally:
        conn.close()
        logging.info("Database connection closed.")
    
    # We will add the CSV writing logic here in the next step.
    
# ... (keep all the code from Part A and B above this) ...

    # --- 5. Format Data and Save to CSV ---
    if report_data:
        logging.info(f"Formatting {len(report_data)} source file records for CSV output...")
        
        # Flatten the nested data structure into a simple list of rows
        csv_rows = []
        for file_report in report_data:
            for rule_detail in file_report['rule_match_details']:
                csv_rows.append({
                    'source_filename': file_report['json_filename'],
                    'total_tiles': file_report['total_tiles'],
                    'rule_index': rule_detail['rule_index'],
                    'rule_name': rule_detail['rule_name'] or '', # Use empty string if name is null
                    'match_count': rule_detail['count']
                })
        
        # Create a pandas DataFrame
        df = pd.DataFrame(csv_rows)
        
        # Ensure output directory exists
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to CSV, without the pandas index column
        df.to_csv(args.output_csv, index=False)
        
        logging.info(f"✔ Report successfully saved to: {args.output_csv}")
    else:
        logging.warning("No data was generated, CSV file will not be created.")

    logging.info("--- Script Finished ---")