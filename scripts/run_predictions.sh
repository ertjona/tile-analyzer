#!/bin/bash

# --- Configuration ---
# PLEASE UPDATE these two variables before running the script.

# 1. The path to your colleague's prediction script.
#    This should be the path accessible from your WSL environment.
PREDICTION_SCRIPT_PATH="/mnt/e/QC_TRAIN_SET/tile-analyzer/scripts/batch_predict.py"
PREDICTION_MODEL_PATH="./marker_classifier_local_final.keras"

# 2. The path to the Python executable in the environment that has TensorFlow installed.
#    You can find this by running `which python` or `which python3` in your WSL terminal.
PYTHON_EXECUTABLE="/home/aixmed/ENTER/envs/tf_stable/bin/python"


# --- Script Logic ---

# The input file containing the list of Windows directories.
INPUT_FILE="directories_to_process.txt"

# The directory where the output CSV files will be saved.
CSV_OUTPUT_DIR="prediction_results"

# Exit immediately if a command fails.
set -e

# Check if the input file exists.
if [ ! -f "$INPUT_FILE" ]; then
    echo "❌ ERROR: Input file not found at '$INPUT_FILE'"
    echo "Please run 'python scripts/list_image_dirs.py > $INPUT_FILE' first."
    exit 1
fi

# Create the output directory if it doesn't exist.
mkdir -p "$CSV_OUTPUT_DIR"
echo "✅ CSV files will be saved in the '$CSV_OUTPUT_DIR' directory."
echo "--------------------------------------------------"

# Read the input file line by line.
while IFS= read -r windows_path || [ -n "$windows_path" ]; do
    # Skip empty lines
    if [ -z "$windows_path" ]; then
        continue
    fi
    
    echo "Processing Windows path: $windows_path"

    # --- NEW: Use wslpath for robust conversion ---
    # Use the 'wslpath -a' command to convert the path
    wsl_path=$(wslpath -a "$windows_path")
    echo "   -> Converted to WSL path: '$wsl_path'"
    # --- END OF NEW LOGIC ---

    # --- NEW, IMPROVED NAMING LOGIC ---
    # 1. Get the parent directory of the path (e.g., E:\...\Z0_files)
    parent_dir=$(dirname "$wsl_path")
    # 2. Get the parent of that directory, which is the unique slide name
    slide_name_dir=$(dirname "$parent_dir")
    # 3. Get just the final component of that path
    meaningful_name=$(basename "$slide_name_dir")
    
    output_csv_path="$CSV_OUTPUT_DIR/${meaningful_name}_predictions.csv"
    # --- END OF NEW LOGIC ---
    
    echo "   -> Generating CSV: $output_csv_path"

    # Construct and run the command.
    command_to_run="$PYTHON_EXECUTABLE $PREDICTION_SCRIPT_PATH --image_folder \"$wsl_path\" --output_csv \"$output_csv_path\" --model_path $PREDICTION_MODEL_PATH --batch_size 1024"
    
    echo "   -> Executing: $command_to_run"
    eval $command_to_run
    
    echo "✅ Done."
    echo "--------------------------------------------------"

done < "$INPUT_FILE"

echo "🎉 All directories have been processed."
