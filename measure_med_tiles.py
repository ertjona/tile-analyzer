import os
import json
import argparse
import numpy as np
import concurrent.futures
from functools import partial
import cv2
import logging
from skimage.measure import shannon_entropy

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#======================================================================
# SECTION 1: DATA GENERATION
#======================================================================

def process_single_tile(filepath, skip_measurements=None):
    """
    Process a single image file to extract all metrics by default.
    
    Args:
        filepath: Path to the image file
        skip_measurements: Set of measurement names to skip (optional)
    
    Returns:
        tuple: (filename, data_dict)
    """
    if skip_measurements is None:
        skip_measurements = set()
    
    filename = os.path.basename(filepath)
    
    try:
        # Extract coordinates from filename
        col, row = map(int, os.path.splitext(filename)[0].split("_"))
        data = {"col": col, "row": row}

        # Read image
        img = cv2.imread(filepath)
        if img is None:
            logging.error(f"Could not read image: {filepath}")
            data.update({
                "status": "error", 
                "error_message": "Could not read or decode image file"
            })
            return filename, data

        height, width = img.shape[:2]
        
        # Check minimum dimensions (240px requirement)
        if width < 240 or height < 240:
            logging.warning(f"Tile {filename} too small ({width}x{height})")
            data.update({
                "status": "warning",
                "error_message": f"Tile dimensions {width}x{height} < 240px minimum",
                "width": width,
                "height": height
            })
            return filename, data

        # Prepare images for analysis
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        data["status"] = "success"
        
        # Perform all measurements unless specifically skipped
        measurements = {
            "size": lambda: os.path.getsize(filepath),
            "width": lambda: width,
            "height": lambda: height,
            "laplacian": lambda: cv2.Laplacian(gray_img, cv2.CV_64F).var(),
            "avg_brightness": lambda: gray_img.mean(),
            "avg_saturation": lambda: np.mean(hsv_img[:, :, 1]) / 255.0,
            "entropy": lambda: shannon_entropy(gray_img),
            "edge_density": lambda: calculate_edge_density(gray_img)
        }
        
        # Execute measurements
        for measurement_name, measurement_func in measurements.items():
            if measurement_name not in skip_measurements:
                try:
                    data[measurement_name] = measurement_func()
                except Exception as e:
                    logging.warning(f"Failed to calculate {measurement_name} for {filename}: {e}")
                    data[f"{measurement_name}_error"] = str(e)

        return filename, data
        
    except Exception as e:
        logging.error(f"Error processing {filename}: {e}")
        return filename, {
            "col": None, 
            "row": None, 
            "status": "error",
            "error_message": f"Processing error: {e}"
        }

def calculate_edge_density(gray_img):
    """Calculate edge density using adaptive Canny thresholds."""
    median_val = np.median(gray_img)
    logging.debug(f"Gray image median: {median_val}")
    sigma = 0.33
    lower_thresh = int(max(0, (1.0 - sigma) * median_val))
    logging.debug(f"Lower threshold: {lower_thresh}")
    upper_thresh = int(min(255, (1.0 + sigma) * median_val))
    logging.debug(f"Upper threshold: {upper_thresh}")
    edges = cv2.Canny(gray_img, lower_thresh, upper_thresh)
    logging.debug(f"Mean of Edges: {np.mean(edges)}")
    return np.mean(edges) / 255.0

def generate_tile_data(args):
    """Generate JSON data from image tiles using parallel processing."""
    logging.info(f"Starting data generation for: {args.image_folder}")
    
    if not os.path.isdir(args.image_folder):
        logging.error(f"Image folder not found: {args.image_folder}")
        return

    # Find all .webp files
    filepaths = [
        os.path.join(args.image_folder, f) 
        for f in os.listdir(args.image_folder) 
        if f.lower().endswith(".webp")
    ]
    
    if not filepaths:
        logging.warning("No .webp files found in directory")
        return

    logging.info(f"Found {len(filepaths)} .webp files to process")
    
    # Prepare skip measurements set
    skip_measurements = set()
    if hasattr(args, 'skip_size') and args.skip_size:
        skip_measurements.add('size')
    if hasattr(args, 'skip_dimensions') and args.skip_dimensions:
        skip_measurements.update(['width', 'height'])
    if hasattr(args, 'skip_laplacian') and args.skip_laplacian:
        skip_measurements.add('laplacian')
    if hasattr(args, 'skip_brightness') and args.skip_brightness:
        skip_measurements.add('avg_brightness')
    if hasattr(args, 'skip_saturation') and args.skip_saturation:
        skip_measurements.add('avg_saturation')
    if hasattr(args, 'skip_entropy') and args.skip_entropy:
        skip_measurements.add('entropy')
    if hasattr(args, 'skip_edge_density') and args.skip_edge_density:
        skip_measurements.add('edge_density')

    # Process tiles in parallel
    worker_func = partial(process_single_tile, skip_measurements=skip_measurements)
    
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(worker_func, filepaths))

    # Collect results
    tile_data = {}
    success_count = 0
    error_count = 0
    warning_count = 0
    
    for filename, data in results:
        if filename and data:
            tile_data[filename] = data
            if data.get("status") == "success":
                success_count += 1
            elif data.get("status") == "error":
                error_count += 1
            elif data.get("status") == "warning":
                warning_count += 1

    # Create the final data structure to be saved in JSON
    output_data = {
        "image_directory": args.image_folder,
        "tiles": tile_data
    }

    # Save results
    logging.info(f"Processing complete: {success_count} successful, {warning_count} warnings, {error_count} errors")
    
    with open(args.output_json, "w") as f:
        json.dump(output_data, f, indent=2)
    
    logging.info(f"Data saved to: {args.output_json}")


#======================================================================
# MAIN ENTRY POINT
#======================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Med tile measurement tool",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument('image_folder', help='Path to folder containing .webp tiles')
    parser.add_argument('output_json', help='Output JSON file path')
    
    # Optional skip flags (measurements are ON by default)
    parser.add_argument('--skip-size', action='store_true', help='Skip file size measurement')
    parser.add_argument('--skip-dimensions', action='store_true', help='Skip dimension measurements')
    parser.add_argument('--skip-laplacian', action='store_true', help='Skip sharpness measurement')
    parser.add_argument('--skip-brightness', action='store_true', help='Skip brightness measurement')
    parser.add_argument('--skip-saturation', action='store_true', help='Skip saturation measurement')
    parser.add_argument('--skip-entropy', action='store_true', help='Skip entropy measurement')
    parser.add_argument('--skip-edge-density', action='store_true', help='Skip edge density measurement')

    args = parser.parse_args()

    # Execute tile data generation
    generate_tile_data(args)