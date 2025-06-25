import os
import json
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import MinMaxScaler
import concurrent.futures
from functools import partial
import cv2
import logging
import matplotlib.ticker as mticker
from skimage.measure import shannon_entropy # NEW IMPORT



# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#======================================================================
# SECTION 1: DATA GENERATION (Modified for New Metrics)
#======================================================================

def process_single_tile(filepath, measure_size, measure_dimensions, measure_laplacian, measure_brightness,
                        measure_saturation, measure_entropy, measure_edgedensity):
    """
    Processes a single image file to extract key metrics, including new advanced metrics.
    """
    filename = os.path.basename(filepath)
    try:
        col, row = map(int, os.path.splitext(filename)[0].split("_"))
        data = {"col": col, "row": row}

        img = cv2.imread(filepath)
        if img is None:
            logging.error(f"Could not read or decode image: {filepath}")
            data.update({"status": "error", "error_message": "Could not read or decode image file"})
            return filename, data

        height, width = img.shape[:2]
        
        # --- NEW REQUIREMENT: Hardcoded dimension check ---
        if width < 240 or height < 240:
            logging.warning(f"Tile {filename} is too small ({width}x{height}). Marking as warning.")
            data["status"] = "warning"
            data["error_message"] = f"Tile is not qualified to analyze (dimensions {width}x{height} < 240px)"
            # Optionally save the failing dimensions for review
            data["width"] = width
            data["height"] = height
            return filename, data

        # If checks pass, proceed with measurements
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        data["status"] = "success"

        # --- Standard Measurements ---
        if measure_size: data["size"] = os.path.getsize(filepath)
        if measure_dimensions: data.update({"width": width, "height": height})
        if measure_laplacian: data["laplacian"] = cv2.Laplacian(gray_img, cv2.CV_64F).var()
        if measure_brightness: data["avg_brightness"] = gray_img.mean()

        # --- NEW: Advanced Measurements ---
        if measure_saturation:
            hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            # Saturation is the second channel, normalize to 0-1 range
            data["avg_saturation"] = np.mean(hsv_img[:, :, 1]) / 255.0

        if measure_entropy:
            data["entropy"] = shannon_entropy(gray_img)

        if measure_edgedensity:
            # Use automatic Canny edge thresholds based on image median
            median_val = np.median(gray_img)
            sigma = 0.33
            lower_thresh = int(max(0, (1.0 - sigma) * median_val))
            upper_thresh = int(min(255, (1.0 + sigma) * median_val))
            edges = cv2.Canny(gray_img, lower_thresh, upper_thresh)
            # Calculate density as percentage of edge pixels
            data["edge_density"] = np.mean(edges) / 255.0

        return filename, data
    except Exception as e:
        logging.error(f"Error processing file {filename}: {e}")
        return filename, {
            "col": None, "row": None, "status": "error",
            "error_message": f"Unexpected processing error: {e}"
        }

def generate_tile_data(args):
    """
    Generates a JSON file from a folder of image tiles using parallel processing.
    """
    logging.info(f"Starting data generation for folder: {args.image_folder}")
    if not os.path.isdir(args.image_folder):
        logging.error(f"Image folder not found: {args.image_folder}")
        return

    filepaths = [os.path.join(args.image_folder, f) for f in os.listdir(args.image_folder) if f.lower().endswith(".webp")]
    if not filepaths:
        logging.warning("No .webp files found in the directory.")
        return

    logging.info(f"Found {len(filepaths)} .webp files to process.")
    tile_data = {}

    worker_func = partial(process_single_tile,
                          measure_size=args.measure_size,
                          measure_dimensions=args.measure_dimensions,
                          measure_laplacian=args.measure_laplacian,
                          measure_brightness=args.measure_brightness,
                          measure_saturation=args.measure_saturation,
                          measure_entropy=args.measure_entropy,
                          measure_edgedensity=args.measure_edgedensity)

    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(worker_func, filepaths))

    for filename, data in results:
        if filename and data:
            tile_data[filename] = data

    logging.info(f"Processing complete. Saving data for {len(tile_data)} files to {args.output_json}")
    with open(args.output_json, "w") as f:
        json.dump(tile_data, f, indent=4)
    logging.info("JSON file generation complete.")

#======================================================================
# ANALYSIS HELPER AND FUNCTIONS
#======================================================================

def load_data(input_json):
    """Loads and prepares the DataFrame from a JSON file."""
    logging.info(f"Loading data from: {input_json}")
    with open(input_json, 'r') as f:
        data = json.load(f)
    records = [dict(filename=fn, **rec) for fn, rec in data.items()]
    df = pd.DataFrame(records)
    logging.info(f"Loaded {len(df)} records.")
    return df

def create_heatmap(df, value_col, title, output_path, cmap='viridis'):
    """Helper function to create and save a heatmap."""
    safe_title = title.lower().replace(' ', '_').replace('(', '').replace(')', '')
    output_filename = f"{safe_title}.png"
    try:
        heatmap_data = df.pivot(index='row', columns='col', values=value_col)
        plt.figure(figsize=(10, 8))
        sns.heatmap(heatmap_data, cmap=cmap, square=True)
        plt.title(title)
        full_output_path = os.path.join(output_path, output_filename)
        plt.savefig(full_output_path)
        plt.close()
        logging.info(f"Generated '{full_output_path}'")
    except Exception as e:
        logging.error(f"Could not generate heatmap for {title}. Error: {e}")

def save_list_to_file(filename_series, output_path, filename_prefix):
    """Helper function to save a list of filenames to a text file."""
    if not filename_series.empty:
        filepath = os.path.join(output_path, f"{filename_prefix}.txt")
        filename_series.to_csv(filepath, index=False, header=False)
        logging.info(f"Generated file list: '{filepath}'")

def analyze_correlation_quadrants(success_df, output_path, args):
    """
    Identifies, visualizes, and exports filenames for four key groups
    based on brightness and sharpness.
    """
    logging.info("\n--- Running 4-Quadrant Correlation Analysis ---")

    if 'avg_brightness' not in success_df.columns or 'laplacian' not in success_df.columns:
        logging.warning("Cannot perform quadrant analysis. 'avg_brightness' or 'laplacian' column is missing.")
        return

    # --- NEW LOGIC: Determine which thresholds to use ---
    # Determine brightness thresholds
    if args.bright_low is not None and args.bright_high is not None:
        logging.info(f"Using FIXED brightness thresholds: Low < {args.bright_low}, High > {args.bright_high}")
        bright_low_thresh = args.bright_low
        bright_high_thresh = args.bright_high
    else:
        logging.info(f"Using QUANTILE brightness thresholds: Low={args.q_low*100}%, High={args.q_high*100}%")
        bright_low_thresh = success_df['avg_brightness'].quantile(args.q_low)
        bright_high_thresh = success_df['avg_brightness'].quantile(args.q_high)

    # Determine sharpness thresholds
    if args.sharp_low is not None and args.sharp_high is not None:
        logging.info(f"Using FIXED sharpness thresholds: Low < {args.sharp_low}, High > {args.sharp_high}")
        sharp_low_thresh = args.sharp_low
        sharp_high_thresh = args.sharp_high
    else:
        logging.info(f"Using QUANTILE sharpness thresholds: Low={args.q_low*100}%, High={args.q_high*100}%")
        sharp_low_thresh = success_df['laplacian'].quantile(args.q_low)
        sharp_high_thresh = success_df['laplacian'].quantile(args.q_high)

    # 2. Identify the four groups using the determined thresholds
    bright_and_sharp = success_df[(success_df['avg_brightness'] >= bright_high_thresh) & (success_df['laplacian'] >= sharp_high_thresh)]
    bright_and_blurry = success_df[(success_df['avg_brightness'] >= bright_high_thresh) & (success_df['laplacian'] <= sharp_low_thresh)]
    dark_and_sharp = success_df[(success_df['avg_brightness'] <= bright_low_thresh) & (success_df['laplacian'] >= sharp_high_thresh)]
    dark_and_blurry = success_df[(success_df['avg_brightness'] <= bright_low_thresh) & (success_df['laplacian'] <= sharp_low_thresh)]
    
    # --- NEW FEATURE: Save filename lists to .txt files ---
    save_list_to_file(bright_and_sharp['filename'], output_path, 'group_bright_and_sharp')
    save_list_to_file(bright_and_blurry['filename'], output_path, 'group_bright_and_blurry')
    save_list_to_file(dark_and_sharp['filename'], output_path, 'group_dark_and_sharp')
    save_list_to_file(dark_and_blurry['filename'], output_path, 'group_dark_and_blurry')
    
    print(f"Found {len(bright_and_sharp)} 'Bright & Sharp' tiles.")
    print(f"Found {len(bright_and_blurry)} 'Bright & Blurry' tiles.")
    print(f"Found {len(dark_and_sharp)} 'Dark & Sharp' tiles.")
    print(f"Found {len(dark_and_blurry)} 'Dark & Blurry' tiles.")    

    # 3. Create annotated scatter plot
    success_df['quadrant'] = 'Normal'
    success_df.loc[bright_and_sharp.index, 'quadrant'] = 'Bright & Sharp'
    success_df.loc[bright_and_blurry.index, 'quadrant'] = 'Bright & Blurry'
    success_df.loc[dark_and_sharp.index, 'quadrant'] = 'Dark & Sharp'
    success_df.loc[dark_and_blurry.index, 'quadrant'] = 'Dark & Blurry'
    plt.figure(figsize=(10, 8))
    sns.scatterplot(data=success_df, x='avg_brightness', y='laplacian', hue='quadrant',
                    palette={'Normal': 'lightgray', 'Bright & Sharp': 'red', 'Bright & Blurry': 'orange',
                             'Dark & Sharp': 'blue', 'Dark & Blurry': 'purple'},
                    hue_order=['Normal', 'Bright & Sharp', 'Bright & Blurry', 'Dark & Sharp', 'Dark & Blurry'],
                    alpha=0.7)
    plt.title('Quadrant Analysis of Sharpness vs. Brightness'); plt.xlabel('Average Brightness'); plt.ylabel('Laplacian Variance'); plt.grid(True)
    output_scatter = os.path.join(output_path, 'quadrant_scatterplot.png')
    plt.savefig(output_scatter); plt.close()
    logging.info(f"Generated annotated scatter plot: '{output_scatter}'")

    # 4. Create combined spatial heatmap
    success_df['quadrant_code'] = 0
    success_df.loc[success_df['filename'].isin(bright_and_sharp['filename']), 'quadrant_code'] = 1
    success_df.loc[success_df['filename'].isin(bright_and_blurry['filename']), 'quadrant_code'] = 2
    success_df.loc[success_df['filename'].isin(dark_and_sharp['filename']), 'quadrant_code'] = 3
    success_df.loc[success_df['filename'].isin(dark_and_blurry['filename']), 'quadrant_code'] = 4
    create_heatmap(success_df, 'quadrant_code', 'Spatial Heatmap of Quadrant Categories', output_path, cmap='Paired')
    logging.info("Category Mapping for Heatmap: 0=Normal, 1=Bright&Sharp, 2=Bright&Blurry, 3=Dark&Sharp, 4=Dark&Blurry")

def generate_html_report(df_tissue, df_background, threshold, image_folder, output_path):
    """Generates an HTML report for visually verifying the tissue threshold."""
    logging.info("Generating HTML report for threshold verification...")

    # Find tiles closest to the threshold on both sides
    tiles_just_below = df_tissue.sort_values(by='avg_brightness', ascending=False).head(24)
    tiles_just_above = df_background.sort_values(by='avg_brightness', ascending=True).head(24)

    html_content = f"""
    <html>
    <head>
    <title>Threshold Verification Report</title>
    <style>
        body {{ font-family: sans-serif; margin: 2em; }}
        h1, h2 {{ text-align: center; }}
        .container {{ display: flex; flex-wrap: wrap; justify-content: center; border: 2px solid #ccc; padding: 10px; margin-bottom: 20px; }}
        .tile {{ margin: 10px; text-align: center; font-size: 12px; border: 1px solid #eee; padding: 5px; }}
        .tile img {{ width: 128px; height: 128px; border: 1px solid #ddd; }}
        .tile p {{ margin: 5px 0 0 0; }}
    </style>
    </head>
    <body>
    <h1>Threshold Verification Report</h1>
    <h2>Threshold Value: {threshold}</h2>

    <h2>Tiles Classified as Tissue (Brightness < {threshold})</h2>
    <p>Displaying up to 24 tissue tiles with the <strong>highest brightness</strong> (closest to the threshold).</p>
    <div class="container">
    """
    for _, row in tiles_just_below.iterrows():
        img_path = os.path.join(image_folder, row['filename'])
        html_content += f"""
        <div class="tile">
            <img src="{img_path}" alt="{row['filename']}">
            <p>{row['filename']}</p>
            <p>Brightness: {row['avg_brightness']:.4f}</p>
        </div>
        """
    html_content += "</div>"

    html_content += f"""
    <h2>Tiles Classified as Background (Brightness >= {threshold})</h2>
    <p>Displaying up to 24 background tiles with the <strong>lowest brightness</strong> (closest to the threshold).</p>
    <div class="container">
    """
    for _, row in tiles_just_above.iterrows():
        img_path = os.path.join(image_folder, row['filename'])
        html_content += f"""
        <div class="tile">
            <img src="{img_path}" alt="{row['filename']}">
            <p>{row['filename']}</p>
            <p>Brightness: {row['avg_brightness']:.4f}</p>
        </div>
        """
    html_content += "</div></body></html>"

    report_path = os.path.join(output_path, 'threshold_verification_report.html')
    with open(report_path, 'w') as f:
        f.write(html_content)
    logging.info(f"Generated HTML report: '{report_path}'")

def analyze_data(args):
    """
    Main function to run the complete analysis pipeline on a JSON file.
    """
    logging.info(f"Starting analysis of: {args.input_json}")
    os.makedirs(args.output_path, exist_ok=True)
    
    df = load_data(args.input_json)
    df_success = df[df['status'] == 'success'].copy()

    if df_success.empty:
        logging.warning("No successful records found to analyze. Exiting.")
        return

    # --- 1. Tissue/Background Segmentation ---
    logging.info("\n--- Running Tissue/Background Segmentation ---")
    if 'avg_brightness' not in df_success.columns:
        logging.error("Cannot perform tissue segmentation. 'avg_brightness' column not found.")
        logging.error("Please re-run the 'generate' command with the --measure_brightness flag.")
        return

    threshold = args.tissue_threshold
    logging.info(f"Using brightness threshold: {threshold} (tiles with brightness < {threshold} are considered tissue)")
    
    df_tissue = df_success[df_success['avg_brightness'] < threshold].copy()
    df_background = df_success[df_success['avg_brightness'] >= threshold].copy()
    
    logging.info(f"Identified {len(df_tissue)} tissue tiles and {len(df_background)} background tiles.")
    
    # Save filename lists
    save_list_to_file(df_tissue['filename'], args.output_path, 'tissue_tiles')
    save_list_to_file(df_background['filename'], args.output_path, 'background_tiles')

    if df_tissue.empty:
        logging.warning("No tissue tiles were identified based on the threshold. No further analysis will be performed.")
        return

    # --- 2. Generate Tissue Mask Heatmap ---
    df['is_tissue'] = 0
    df.loc[df['filename'].isin(df_tissue['filename']), 'is_tissue'] = 1
    create_heatmap(df, 'is_tissue', 'Tissue Mask Heatmap', args.output_path, cmap='viridis')

    # --- 3. Generate HTML report if image folder is provided ---
    if args.image_folder:
        if os.path.isdir(args.image_folder):
            generate_html_report(df_tissue, df_background, threshold, args.image_folder, args.output_path)
        else:
            logging.warning(f"Image folder for HTML report not found: {args.image_folder}. Skipping report generation.")

    # --- 4. Run All Subsequent Analyses on TISSUE TILES ONLY ---
    logging.info("\n--- Running all subsequent analyses on TISSUE tiles only ---")
    analyze_distributions(df_tissue, args.output_path)
    analyze_spatial_patterns(df_tissue, args.output_path)
    analyze_correlation_quadrants(df_tissue, args.output_path, args)
        
        
    # Pass the entire `args` object to the analysis function
    #analyze_correlation_quadrants(df, df_success, args.output_path, args)

    # Distribution Analysis
def analyze_distributions(df, output_path):
    plt.figure(figsize=(12, 5))
    
    # Step 1: Create the plot and get the Axes object
    ax_size = sns.histplot(df['size'], bins=50, kde=True)
    # Step 2: Use the Axes object to set properties
    ax_size.set_title('Distribution of File Size')
    ax_size.set_xlabel('File Size (bytes)')
    ax_size.set_ylabel('Frequency')
    ax_size.xaxis.set_major_locator(mticker.MaxNLocator(nbins=10))
    plt.xticks(rotation=30, ha='right')
    plt.tight_layout()
    plt.savefig(os.path.join(output_path, 'distribution_size.png'))
    plt.close()
    
    # Step 1: Create the plot and get the Axes object
    ax_lap = sns.histplot(df['laplacian'], bins=50, kde=True)
    # Step 2: Use the Axes object to set properties
    ax_lap.set_title('Distribution of Sharpness (Laplacian)')
    ax_lap.set_xlabel('Laplacian Variance')
    ax_lap.set_ylabel('Frequency')
    ax_lap.xaxis.set_major_locator(mticker.MaxNLocator(nbins=10))
    plt.xticks(rotation=30, ha='right')
    plt.tight_layout()
    plt.savefig(os.path.join(output_path, 'distribution_laplacian.png'))
    plt.close()

    # Step 1: Create the plot and get the Axes object
    ax_lap = sns.histplot(df['avg_brightness'], bins=50, kde=True)
    # Step 2: Use the Axes object to set properties
    ax_lap.set_title('Distribution of Brightness')
    ax_lap.set_xlabel('Brightness')
    ax_lap.set_ylabel('Frequency')
    ax_lap.xaxis.set_major_locator(mticker.MaxNLocator(nbins=10))
    plt.xticks(rotation=30, ha='right')
    plt.tight_layout()
    plt.savefig(os.path.join(output_path, 'distribution_brightness.png'))
    plt.close()
    
    logging.info("Generated distribution plots.")

def analyze_spatial_patterns(success_df, output_path):
    """
    Generates heatmaps for spatial analysis.
    This function now correctly accepts the output_path argument.
    """
    logging.info("\n--- Running Spatial Analysis ---")
    
    # Heatmap for Sharpness (on tissue only)
    create_heatmap(success_df, 'laplacian', 'Spatial Heatmap of Sharpness', output_path, cmap='hot_r')
    
    # Heatmap for File Size (on tissue only)
    create_heatmap(success_df, 'size', 'Spatial Heatmap of File Size', output_path)

    # Heatmap for Brightness (on tissue only)
    create_heatmap(success_df, 'avg_brightness', 'Spatial Heatmap of Brightness', output_path, cmap='hot')

    logging.info("Spatial Analysis complete.")

#======================================================================
# SCRIPT ENTRY POINT
#======================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="An all-in-one tool to generate and analyze medical image tile data.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    # --- Sub-parser for the "generate" command ---
    parser_generate = subparsers.add_parser('generate', help='Generate a JSON file from a folder of image tiles.')
    parser_generate.add_argument('image_folder', help='Path to the folder containing .webp image tiles.')
    parser_generate.add_argument('output_json', help='Path to save the output JSON file.')
    parser_generate.add_argument('--measure_size', action='store_true', help='Measure tile file size.')
    parser_generate.add_argument('--measure_dimensions', action='store_true', help='Measure tile dimensions (width/height).')
    parser_generate.add_argument('--measure_laplacian', action='store_true', help='Measure Laplacian variance for sharpness.')
    parser_generate.add_argument('--measure_brightness', action='store_true', help='Measure average pixel brightness (luminance).')
    # --- NEW: Advanced measurement flags ---
    parser_generate.add_argument('--measure-saturation', action='store_true', help='Measure average color saturation.')
    parser_generate.add_argument('--measure-entropy', action='store_true', help='Measure Shannon entropy (complexity).')
    parser_generate.add_argument('--measure-edgedensity', action='store_true', help='Measure density of detected edges.')

    # --- Sub-parser for the "analyze" command ---
    parser_analyze = subparsers.add_parser('analyze', help='Analyze an existing tile data JSON file.')
    parser_analyze.add_argument('input_json', help='Path to the input JSON file to analyze.')
    parser_analyze.add_argument('output_path', help='Path to the directory where output analysis images will be saved.')

    # --- NEW: Add required argument for tissue segmentation ---
    parser_analyze.add_argument(
        '--tissue-threshold',
        type=float,
        required=True,
        help='Brightness threshold to separate tissue from background (e.g., 220). Required for analysis.'
    )
    # --- NEW: Add optional argument for the HTML report's image source ---
    parser_analyze.add_argument(
        '--image-folder',
        type=str,
        default=None,
        help='(Optional) Path to the original image folder to generate an HTML report for visual inspection.'
    )

    # --- Threshold arguments ---
    # Quantile-based (default method)
    parser_analyze.add_argument('--q-low', type=float, default=0.25, help='The low quantile threshold for analysis (default: 0.25).')
    parser_analyze.add_argument('--q-high', type=float, default=0.75, help='The high quantile threshold for analysis (default: 0.75).')
    
    # --- NEW: Fixed value arguments (override quantiles if used) ---
    parser_analyze.add_argument('--bright-low', type=float, default=None, help='Fixed threshold for "dark" (e.g., 50). Overrides --q-low for brightness.')
    parser_analyze.add_argument('--bright-high', type=float, default=None, help='Fixed threshold for "bright" (e.g., 200). Overrides --q-high for brightness.')
    parser_analyze.add_argument('--sharp-low', type=float, default=None, help='Fixed threshold for "blurry" (e.g., 10). Overrides --q-low for sharpness.')
    parser_analyze.add_argument('--sharp-high', type=float, default=None, help='Fixed threshold for "sharp" (e.g., 500). Overrides --q-high for sharpness.')
            
    args = parser.parse_args()

    # Execute the chosen command
    if args.command == 'generate':
        generate_tile_data(args)
    elif args.command == 'analyze':
        analyze_data(args)