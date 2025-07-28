import os
import json
import argparse
import numpy as np
import concurrent.futures
from functools import partial
import cv2
import logging
from skimage.measure import shannon_entropy
import ast # For parsing string tuples from argparse

# --- Configure logging (moved to be dynamic in main) ---
# Removed global basicConfig call here, it's now in __main__

# Define a temporary debug output directory name, if none is specified by user
DEFAULT_DEBUG_OUTPUT_DIR_NAME = 'debug_output_default'

#======================================================================
# SECTION 1: DATA GENERATION
#======================================================================

# Helper to convert string tuple "(H,S,V)" to actual tuple
def _parse_hsv_tuple(hsv_str):
    try:
        return ast.literal_eval(hsv_str)
    except (ValueError, SyntaxError):
        raise argparse.ArgumentTypeError(f"Invalid HSV tuple format: {hsv_str}. Expected (H, S, V).")

def process_single_tile(filepath, skip_measurements=None, debug_output_dir=None, debug_mode_active=False,
                        msa_lower_white=None, msa_upper_white=None, msa_kernel_size=None):
    """
    Process a single image file to extract all metrics by default.
    """
    # NEW: Re-initialize logging basicConfig for this worker process if debug mode is active
    if debug_mode_active and not logging.getLogger().handlers: # Only configure if not already set up (e.g., in parent)
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        logging.debug(f"Worker process logging configured for DEBUG.") # Debug message for worker start

    logging.debug(f"Processing tile: {os.path.basename(filepath)}") # This was your test message


    if skip_measurements is None:
        skip_measurements = set()
    
    filename = os.path.basename(filepath)
    
    try:
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
        
        # Check minimum dimensions (256px requirement)
        if width < 256 or height < 256:
            logging.debug(f"Tile {filename} too small ({width}x{height})")
            data = { # Ensure data dict is initialized here
                "col": int(os.path.splitext(filename)[0].split("_")[0]), # Try to get col/row even if small
                "row": int(os.path.splitext(filename)[0].split("_")[1]),
                "status": "warning",
                "error_message": f"Tile dimensions {width}x{height} < 256px minimum",
                "width": width,
                "height": height
            }
            return filename, data

        # Prepare images for analysis
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        data = {"col": int(os.path.splitext(filename)[0].split("_")[0]), # Parse col/row
                "row": int(os.path.splitext(filename)[0].split("_")[1]),
                "status": "success"} # Initialize data dict for success case
        
        # Perform all measurements unless specifically skipped
        measurements = {
            "size": lambda: os.path.getsize(filepath),
            "width": lambda: width,
            "height": lambda: height,
            "laplacian": lambda: cv2.Laplacian(gray_img, cv2.CV_64F).var(),
            "avg_brightness": lambda: gray_img.mean(),
            "avg_saturation": lambda: np.mean(hsv_img[:, :, 1]) / 255.0,
            "entropy": lambda: shannon_entropy(gray_img),
            "edge_density": lambda: calculate_edge_density(gray_img),
            "edge_density_3060": lambda: calculate_edge_density_3060(gray_img),
            "foreground_ratio": lambda: calculate_foreground_ratio(hsv_img),
            "max_subject_area": lambda: calculate_max_subject_area(
                hsv_img, # Corrected typo: hsv -> hsv_img
                lower_white=_parse_hsv_tuple(msa_lower_white),
                upper_white=_parse_hsv_tuple(msa_upper_white),
                kernel_size=msa_kernel_size,
                debug_output_dir=debug_output_dir if debug_mode_active else None,
                filename_base=filename if debug_mode_active else None
            )
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

def calculate_edge_density_3060(gray_image):
    """Calculates edge density using fixed Canny thresholds of 30 and 60."""
    edged = cv2.Canny(gray_image, 30, 60)
    return np.sum(edged > 0) / (edged.shape[0] * edged.shape[1])
    
def calculate_foreground_ratio(hsv, lower_white=(0, 0, 200), upper_white=(180, 20, 255), kernel_size=3):
    """Calculates and returns the foreground ratio for a given image."""
    lower_white_np = np.array(lower_white, dtype=np.uint8)
    upper_white_np = np.array(upper_white, dtype=np.uint8)
    mask_bg = cv2.inRange(hsv, lower_white_np, upper_white_np)

    total_pixels = mask_bg.size
    background_pixels = (mask_bg == 255).sum()
    foreground_pixels = total_pixels - background_pixels
    
    if total_pixels == 0:
        return 0.0
        
    return foreground_pixels / total_pixels

def calculate_max_subject_area(hsv, lower_white=(0, 0, 220), upper_white=(180, 20, 255), kernel_size=3, debug_output_dir=None, filename_base=None): # Corrected default params to final decision
    lower_white_np = np.array(lower_white, dtype=np.uint8)
    upper_white_np = np.array(upper_white, dtype=np.uint8)
    mask_bg = cv2.inRange(hsv, lower_white_np, upper_white_np)
    mask_fg = cv2.bitwise_not(mask_bg)
    
    if debug_output_dir and filename_base:
        os.makedirs(debug_output_dir, exist_ok=True)
        debug_output_path_fg = os.path.join(debug_output_dir, f"{filename_base}_mask_fg.png") 
        cv2.imwrite(debug_output_path_fg, mask_fg)

    # --- Hole Filling Logic ---
    filled_mask_fg = mask_fg.copy()
    contours, hierarchy = cv2.findContours(mask_fg, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is not None:
        hierarchy = hierarchy[0]
        for i in range(len(contours)):
            if hierarchy[i][3] != -1: # If the contour has a parent (it's a hole)
                cv2.drawContours(filled_mask_fg, [contours[i]], 0, 255, -1) # Fill the hole

    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    mask_fg_clean = cv2.morphologyEx(filled_mask_fg, cv2.MORPH_OPEN, kernel)
    
    if debug_output_dir and filename_base:
        debug_output_path_clean = os.path.join(debug_output_dir, f"{filename_base}_mask_fg_clean.png")
        cv2.imwrite(debug_output_path_clean, mask_fg_clean)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask_fg_clean)
    
    if num_labels > 1:
        label_hue = np.uint8(179 * labels / np.max(labels))
        blank_ch = 255 * np.ones_like(label_hue)
        labeled_img = cv2.merge([label_hue, blank_ch, blank_ch])
        labeled_img = cv2.cvtColor(labeled_img, cv2.COLOR_HSV2BGR)
        labeled_img[labels == 0] = 0 # Set background to black
        
        subject_areas = stats[1:, cv2.CC_STAT_AREA]
        max_subj_area = max(subject_areas)

        if debug_output_dir and filename_base:
            debug_output_path_labels = os.path.join(debug_output_dir, f"{filename_base}_maxArea{max_subj_area}_labeled_components.png")
            cv2.imwrite(debug_output_path_labels, labeled_img)
            
    else:
        max_subj_area = 0
    
    logging.debug(f"Max subject area for {filename_base}: {max_subj_area}") # Use logging.debug()
    
    return int(max_subj_area)

def generate_tile_data(args, debug_mode_active):
    """Generate JSON data from image tiles using parallel processing."""
    logging.info(f"Starting data generation for: {args.image_folder}")
    
    if not os.path.isdir(args.image_folder):
        logging.error(f"Image folder not found: {args.image_folder}")
        return

    filepaths = [
        os.path.join(args.image_folder, f) 
        for f in os.listdir(args.image_folder) 
        if f.lower().endswith(".webp") # Only .webp files
    ]
    
    if not filepaths:
        logging.warning("No .webp files found in directory")
        return

    logging.info(f"Found {len(filepaths)} .webp files to process")
    
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
    if hasattr(args, 'skip_edge_density_3060') and args.skip_edge_density_3060:
        skip_measurements.add('edge_density_3060')

    worker_func = partial(
        process_single_tile,
        skip_measurements=skip_measurements,
        debug_output_dir=args.debug_output_dir,
        debug_mode_active=debug_mode_active,
        msa_lower_white=args.msa_lower_white,
        msa_upper_white=args.msa_upper_white,
        msa_kernel_size=args.msa_kernel_size
    )
    
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(worker_func, filepaths))

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

    output_data = {
        "image_directory": args.image_folder,
        "tiles": tile_data
    }

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

    parser.add_argument('--debug-output-dir', type=str,
                       help='Optional: Directory to save debug output images (e.g., masks). Requires --debug-mode.')
    
    parser.add_argument('--debug-mode', action='store_true',
                       help='Enable debug mode to generate intermediate images and print debug info. Use with --debug-output-dir.')

    # Arguments for calculate_max_subject_area parameters
    parser.add_argument('--msa-lower-white', type=str, default='(0, 0, 220)',
                       help='Lower HSV bound for white background in max_subject_area. Format: (H, S, V)')
    parser.add_argument('--msa-upper-white', type=str, default='(180, 20, 255)',
                       help='Upper HSV bound for white background in max_subject_area. Format: (H, S, V)')
    parser.add_argument('--msa-kernel-size', type=int, default=3,
                       help='Kernel size for morphological open in max_subject_area.')

    args = parser.parse_args()

    # Determine if debug mode is active and set debug_output_dir if needed
    debug_mode_active = args.debug_mode
    if debug_mode_active and not args.debug_output_dir:
        # If debug mode is on but no directory is specified, use a default
        args.debug_output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', DEFAULT_DEBUG_OUTPUT_DIR_NAME)
        print(f"Debug mode enabled. Debug output will be saved to default: {args.debug_output_dir}")
    elif not debug_mode_active and args.debug_output_dir:
        print("Warning: --debug-output-dir specified but --debug-mode is off. Debug images will NOT be generated.")
        args.debug_output_dir = None

    # Configure logging AFTER args are parsed
    if debug_mode_active:
        _log_level = logging.DEBUG
    else:
        _log_level = logging.INFO
        
    logging.basicConfig(level=_log_level, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # NEW LINE: Add a test debug message here
    logging.debug("This is a test debug message from main after logging setup.") # NEW LINE

    # Execute tile data generation
    generate_tile_data(args, debug_mode_active)