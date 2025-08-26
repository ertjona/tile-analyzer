import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path
import pandas as pd

# --- 1. Setup ---
# Add the project root to Python's path to allow importing from 'lib'
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Import the core logic and Pydantic model from the shared library
from lib.reporting import generate_report_data, HeatmapRulesConfig

# Configure logging to include timestamps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- 2. Core Logic ---
def create_report(rule_file_path, db_path, output_csv_path, report_format):
    """
    Generates a rule-based analysis report from the database and saves it as a CSV.
    Supports both 'wide' and 'long' formats.
    """
    logging.info("--- Report Generation Script Started ---")

    # --- Load and Validate Rule File ---
    logging.info(f"Loading rules from: {rule_file_path}")
    if not rule_file_path.is_file():
        logging.error(f"Rule file not found at: {rule_file_path}")
        return

    try:
        with open(rule_file_path, 'r') as f:
            rules_data = json.load(f)
        rules_config = HeatmapRulesConfig(**rules_data).model_dump()
        logging.info("Rule file is valid and loaded successfully.")
    except Exception as e:
        logging.error(f"Invalid rule file format: {e}")
        return

    # --- Connect to Database and Generate Core Data ---
    logging.info(f"Connecting to database: {db_path}")
    if not db_path.is_file():
        logging.error(f"Database not found at: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;") # Performance tuning
        conn.execute("PRAGMA cache_size = -20000000;") # 20GB cache
        logging.info("Querying database and generating report data... (This may take a while)")
        report_data = generate_report_data(conn, rules_config)
        logging.info("Core data generation complete.")
    except Exception as e:
        logging.error(f"An error occurred during report generation: {e}")
        return
    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed.")

    if not report_data:
        logging.warning("No data was generated. The CSV file will not be created.")
        return

    # --- Format Data and Save to CSV based on user's choice ---
    df = None
    if report_format == 'wide':
        logging.info("Formatting data into 'wide' format with summary row...")
        detailed_rows = []
        for file_report in report_data:
            row = {'json_filename': file_report['json_filename'], 'total_tiles': file_report['total_tiles']}
            for detail in file_report['rule_match_details']:
                rule_name = detail['rule_name'] if detail['rule_name'] else 'default'
                count = detail['count']
                percentage = (count / row['total_tiles'] * 100) if row['total_tiles'] > 0 else 0
                row[f'{rule_name} (Count)'] = count
                row[f'{rule_name} (%)'] = round(percentage, 2)
            detailed_rows.append(row)
        
        df = pd.DataFrame(detailed_rows)
        
        if not df.empty:
            summary_row = {'json_filename': 'TOTALS'}
            for col in df.columns:
                if '(Count)' in col or col == 'total_tiles':
                    summary_row[col] = df[col].sum()
            total_tiles_in_db = summary_row.get('total_tiles', 0)
            for col in df.columns:
                if '(%)' in col:
                    count_col = col.replace('(%)', '(Count)')
                    percentage = (summary_row.get(count_col, 0) / total_tiles_in_db * 100) if total_tiles_in_db > 0 else 0
                    summary_row[col] = round(percentage, 2)
            
            summary_df_row = pd.DataFrame([summary_row])
            df = pd.concat([df, summary_df_row], ignore_index=True)

    elif report_format == 'long':
        logging.info("Formatting data into 'long' format...")
        long_rows = []
        for file_report in report_data:
            for rule_detail in file_report['rule_match_details']:
                long_rows.append({
                    'source_filename': file_report['json_filename'],
                    'total_tiles_in_file': file_report['total_tiles'],
                    'rule_name': rule_detail['rule_name'] or 'default',
                    'match_count': rule_detail['count']
                })
        df = pd.DataFrame(long_rows)

    # --- Save the final DataFrame to CSV ---
    if df is not None and not df.empty:
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv_path, index=False)
        logging.info(f"✅ Report successfully saved to: {output_csv_path}")
    else:
        logging.warning("DataFrame was empty. No CSV file was created.")

    logging.info("--- Script Finished ---")

# --- 3. Main Execution Block ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a consolidated rule-based analysis report from the database.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--rule-file', type=Path, required=True, help='Path to the JSON file containing the heatmap rules.')
    parser.add_argument('--db-path', type=Path, required=True, help='Path to the SQLite database file.')
    parser.add_argument('--output-csv', type=Path, required=True, help='Path to save the final consolidated CSV report.')
    parser.add_argument('--format', type=str, default='wide', choices=['wide', 'long'], help="The output format for the CSV report ('wide' or 'long'). Default is 'wide'.")
    
    args = parser.parse_args()
    create_report(args.rule_file, args.db_path, args.output_csv, args.format)