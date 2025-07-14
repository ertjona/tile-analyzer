import sqlite3
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import argparse
import ast 

# --- Database Configuration (consistent with other scripts) ---
from pathlib import Path
SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR.parent / "database" / "analysis.db"

# Mapping for display names of columns
COLUMN_DISPLAY_MAP = {
    'max_subject_area': 'Max Subject Area',
    'edge_density': 'Edge Density',
    'laplacian': 'Laplacian',
    'avg_brightness': 'Average Brightness',
    'avg_saturation': 'Average Saturation',
    'entropy': 'Shannon Entropy',
    'size': 'File Size'
}

def _build_sql_where_clause(column_name, status_success=True, is_not_null=True, 
                            filter_zeros=False, min_filter_value=None, max_filter_value=None):
    """
    Builds the SQL WHERE clause for filtering data.
    """
    where_clauses = []
    
    if status_success:
        where_clauses.append("status = 'success'")
    if is_not_null:
        where_clauses.append(f"{column_name} IS NOT NULL")
    
    if filter_zeros:
        where_clauses.append(f"{column_name} > 0")
    elif min_filter_value is not None:
        where_clauses.append(f"{column_name} >= {min_filter_value}")

    if max_filter_value is not None:
        where_clauses.append(f"{column_name} <= {max_filter_value}")
    
    where_clause_str = " AND ".join(where_clauses)
    if where_clause_str:
        return f" WHERE {where_clause_str}"
    return ""

def _fetch_raw_data(db_path, column_name, where_clause_str):
    """
    Connects to the database and fetches raw data based on column name and WHERE clause.
    """
    conn = None 
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        query = f"SELECT {column_name} FROM ImageTiles{where_clause_str}"
        print(f"\nExecuting query: {query}")
        results = cursor.execute(query).fetchall()
        return np.array([r[0] for r in results])
    except sqlite3.Error as e:
        print(f"Database error during data fetch: {e}")
        return np.array([]) 
    finally:
        if conn:
            conn.close()

def _apply_python_side_filters(all_values, filter_zeros, min_filter_value, max_filter_value):
    """
    Applies robust Python-side filtering (NumPy-based) to the fetched values.
    """
    filtered_values = all_values.copy() 

    if filter_zeros:
        epsilon = 1e-9 
        filtered_values = filtered_values[filtered_values > epsilon]
        print(f"Note: Applied robust Python-side filter for zeros/near-zeros. Remaining values: {filtered_values.size}")
    elif min_filter_value is not None:
        filtered_values = filtered_values[filtered_values >= min_filter_value]
        print(f"Note: Applied robust Python-side filter for min_filter_value. Remaining values: {filtered_values.size}")
    
    if max_filter_value is not None:
        filtered_values = filtered_values[filtered_values <= max_filter_value]
        print(f"Note: Applied robust Python-side filter for max_filter_value. Remaining values: {filtered_values.size}")

    return filtered_values

# NEW: Helper function to calculate and print statistics
def _calculate_and_print_statistics(values, display_column_name):
    """
    Calculates and prints statistical summaries for the given array of values.
    """
    print(f"Total successful tiles analyzed: {values.size}")
    
    # Stats
    print(f"Min: {np.min(values):.10f}")
    print(f"Max: {np.max(values):.10f}")
    print(f"Mean: {np.mean(values):.10f}")
    print(f"Median: {np.median(values):.10f}")
    print(f"Standard Deviation: {np.std(values):.10f}")

    # Percentiles
    percentiles_to_check = [1, 5, 10, 25, 33, 50, 67, 75, 90, 95, 99] 
    print(f"\n--- Percentiles for {display_column_name} ---")
    for p in percentiles_to_check:
        val = np.percentile(values, p)
        print(f"{p}th percentile: {val:.10f}")

def analyze_metric_from_db(db_path, column_name, output_dir=None, 
                           filter_zeros=False, min_filter_value=None, max_filter_value=None,
                           min_threshold_for_analysis=None, max_threshold_for_analysis=None):
    """
    Connects to the database, fetches all values for a given column,
    and performs statistical analysis and generates a histogram.
    """
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    display_column_name = COLUMN_DISPLAY_MAP.get(column_name, column_name)
    
    where_clause_str = _build_sql_where_clause(
        column_name,
        filter_zeros=filter_zeros, 
        min_filter_value=min_filter_value, 
        max_filter_value=max_filter_value
    )

    all_values = _fetch_raw_data(db_path, column_name, where_clause_str)
    
    if all_values.size == 0:
        print(f"No {display_column_name} data found for successful tiles matching criteria.")
        return

    all_values = _apply_python_side_filters(
        all_values,
        filter_zeros=filter_zeros,
        min_filter_value=min_filter_value,
        max_filter_value=max_filter_value
    )

    if all_values.size == 0:
        print(f"No {display_column_name} data found after robust Python-side filtering.")
        return

    # MODIFIED: Use new helper to calculate and print statistics
    _calculate_and_print_statistics(all_values, display_column_name)

    # ... (rest of analyze_metric_from_db function, including histogram generation) ...

    # Generate Histograms
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
        # Base filename part
        filename_base = f"{column_name}_distribution"

        # Histogram for all retrieved values
        plt.figure(figsize=(16, 8))
        sns.histplot(all_values, bins=50, kde=True, color='skyblue')
        plt.title(f'Distribution of {display_column_name} (All Retrieved Values)')
        plt.xlabel(f'{display_column_name} Value')
        plt.ylabel('Frequency')
        plt.grid(axis='y', alpha=0.75)
        plt.savefig(os.path.join(output_dir, f"{filename_base}_all.png"))
        plt.close()
        print(f"Histogram saved: {os.path.join(output_dir, f'{filename_base}_all.png')}")

        # Histogram for specific analysis range (if provided)
        if min_threshold_for_analysis is not None or max_threshold_for_analysis is not None:
            
            # Filter for the zoomed range, min/max_threshold_for_analysis could be floats.
            zoomed_values = all_values
            if min_threshold_for_analysis is not None:
                zoomed_values = zoomed_values[zoomed_values >= min_threshold_for_analysis]
            if max_threshold_for_analysis is not None:
                zoomed_values = zoomed_values[zoomed_values <= max_threshold_for_analysis]
            
            if zoomed_values.size > 0:
                zoom_range_str = ""
                if min_threshold_for_analysis is not None and max_threshold_for_analysis is not None:
                    zoom_range_str = f" ({min_threshold_for_analysis}-{max_threshold_for_analysis} Range)"
                elif min_threshold_for_analysis is not None:
                    zoom_range_str = f" (>= {min_threshold_for_analysis} Range)"
                elif max_threshold_for_analysis is not None:
                    zoom_range_str = f" (<= {max_threshold_for_analysis} Range)"

                zoomed_filename_part = ""
                if min_threshold_for_analysis is not None:
                    zoomed_filename_part += f"_min{min_threshold_for_analysis}"
                if max_threshold_for_analysis is not None:
                    zoomed_filename_part += f"_max{max_threshold_for_analysis}"
                
                plt.figure(figsize=(16, 8))
                sns.histplot(zoomed_values, bins=min(100, zoomed_values.size // 5) if zoomed_values.size > 0 else 1, kde=True, color='lightcoral') 
                plt.title(f'Distribution of {display_column_name}{zoom_range_str}')
                plt.xlabel(f'{display_column_name} Value')
                plt.ylabel('Frequency')
                plt.grid(axis='y', alpha=0.75)
                plt.savefig(os.path.join(output_dir, f"{filename_base}{zoomed_filename_part}_zoomed.png"))
                plt.close()
                print(f"Zoomed histogram saved: {os.path.join(output_dir, f'{filename_base}{zoomed_filename_part}_zoomed.png')}")
            else:
                print(f"No {display_column_name} values found in the specified zoom range for zoomed histogram.")
        else:
            print("No specific zoom range provided. Skipping zoomed histogram generation.")
    else:
        print("Output directory not specified. Skipping histogram generation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze metric distribution from the database.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  # Analyze max_subject_area (default column)
  python analyze_metric_from_db.py --output-dir analysis_results

  # Analyze edge_density, filtering out zeros
  python analyze_metric_from_db.py --column-name edge_density --filter-zeros --output-dir analysis_results

  # Analyze laplacian, for values between 0.1 and 100, and save histogram for this range
  python analyze_metric_from_db.py --column-name laplacian --min-filter-value 0.1 --max-filter-value 100 --output-dir analysis_results --min-threshold-for-analysis 0.1 --max-threshold-for-analysis 100
        """
    )
    parser.add_argument('--db-path', type=str, default=str(DB_PATH),
                        help=f'Path to the SQLite database file (default: {DB_PATH})')
    parser.add_argument('--output-dir', type=str, default='metric_analysis_results',
                        help='Directory to save generated histograms (default: metric_analysis_results)')
    
    parser.add_argument('--column-name', type=str, default='max_subject_area',
                        help='Name of the column to analyze (e.g., max_subject_area, edge_density, laplacian). (default: max_subject_area)')
    
    parser.add_argument('--filter-zeros', action='store_true',
                        help='Filter out zero values for analysis and histogram (e.g., for max_subject_area, edge_density).')
    
    parser.add_argument('--min-filter-value', type=float,
                        help='Minimum value to include in analysis (inclusive). Overrides --filter-zeros.')
    parser.add_argument('--max-filter-value', type=float,
                        help='Maximum value to include in analysis (inclusive).')
    
    parser.add_argument('--min-threshold-for-analysis', type=float,
                        help='Minimum value for the zoomed histogram range (inclusive).')
    parser.add_argument('--max-threshold-for_analysis', type=float,
                        help='Maximum value for the zoomed histogram range (inclusive).')


    args = parser.parse_args()

    # Determine filter values based on precedence
    final_min_filter_value = None
    if args.min_filter_value is not None:
        final_min_filter_value = args.min_filter_value
    elif args.filter_zeros:
        # A very small non-zero value to effectively filter zeros due to float precision
        # This acts as a soft lower bound when --filter-zeros is used.
        final_min_filter_value = 1e-9 

    analyze_metric_from_db(
        db_path=args.db_path,
        column_name=args.column_name,
        output_dir=args.output_dir,
        filter_zeros=args.filter_zeros, # Pass this as a flag, though min_filter_value takes precedence
        min_filter_value=final_min_filter_value, # Use the determined filter value
        max_filter_value=args.max_filter_value,
        min_threshold_for_analysis=args.min_threshold_for_analysis,
        max_threshold_for_analysis=args.max_threshold_for_analysis
    )