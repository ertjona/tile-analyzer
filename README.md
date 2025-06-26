# tile-analyzer

This project provides a suite of tools for measuring and analyzing image tiles. It consists of two main Python scripts: `measure_med_tiles.py` for extracting metrics from image files and `analyze_med_tiles.py` for in-depth analysis and visualization of the collected data.

## Features

  * **Comprehensive Image Metrics**: The tool can measure a variety of metrics from `.webp` image tiles:
      * File size
      * Image dimensions (width and height)
      * Sharpness (Laplacian variance)
      * Average brightness
      * Average saturation
      * Shannon entropy
      * Edge density, calculated using an adaptive Canny edge detector
  * **Interactive HTML Viewer**: It can generate a paginated HTML report to view the images alongside their measured metrics. This viewer allows for sorting the images by any of the measured metrics in ascending or descending order.
  * **In-depth Edge Density Analysis**: The tool can perform a detailed analysis of edge density across all tiles. It generates:
      * A statistical report with basic stats, zero-value analysis, and percentile distribution.
      * A binary heatmap showing tiles with zero vs. non-zero edge density.
      * A graded heatmap with a logarithmic scale to visualize the distribution of edge density values.
      * A histogram showing the distribution of non-zero edge density values.
  * **Efficient Processing**: The measurement script utilizes parallel processing to handle a large number of images efficiently.

## Prerequisites

Before you begin, ensure you have Python installed. You will also need to install the necessary libraries. Based on the scripts, the required libraries are:

  * `numpy`
  * `pandas`
  * `matplotlib`
  * `seaborn`
  * `scikit-image`
  * `opencv-python`

You can install these using pip:

```bash
pip install numpy pandas matplotlib seaborn scikit-image opencv-python
```

## Workflow & Usage

The workflow is a two-step process. First, you generate the metrics data from your images, and then you analyze that data.

### Step 1: Measure Image Tiles

Use the `measure_med_tiles.py` script to process a folder of `.webp` image tiles and save the extracted metrics into a JSON file.

**Command:**

```bash
python measure_med_tiles.py <path_to_image_folder> <output_json_file> [options]
```

**Arguments:**

  * `image_folder`: The path to the folder containing your `.webp` image tiles.
  * `output_json`: The path where the output JSON data file will be saved.

**Options:**

You can skip certain measurements to speed up the process if they are not needed. By default, all metrics are measured.

  * `--skip-size`: Do not measure file size.
  * `--skip-dimensions`: Do not measure image width and height.
  * `--skip-laplacian`: Do not measure sharpness.
  * `--skip-brightness`: Do not measure brightness.
  * `--skip-saturation`: Do not measure saturation.
  * `--skip-entropy`: Do not measure entropy.
  * `--skip-edge-density`: Do not measure edge density.

**Example:**

```bash
python measure_med_tiles.py ./my_tiles data.json
```

This command will process all `.webp` files in the `./my_tiles` directory and save the results to `data.json`.

### Step 2: Analyze and Visualize the Data

Once you have your `data.json` file, you can use the `analyze_med_tiles.py` script to generate the HTML viewer and/or the edge density analysis report.

**Command:**

```bash
python analyze_med_tiles.py <path_to_image_folder> --json-path <path_to_json_file> --output-dir <output_directory> [options]
```

**Arguments:**

  * `image_dir`: The directory containing the `.webp` image files. This is needed to display the images in the HTML viewer.
  * `--json-path`: The path to the input JSON file generated in Step 1.
  * `--output-dir`: The directory where the output files (HTML viewer, plots) will be saved.

**Options:**

You can choose to generate all outputs or only specific parts of the analysis.

  * `--html-only`: Generate only the paginated HTML viewer.
  * `--analysis-only`: Generate only the edge density analysis report and plots.

If neither option is specified, the script will run the complete analysis, generating both the HTML viewer and the edge density reports.

**Examples:**

  * **Run the complete analysis:**
    ```bash
    python analyze_med_tiles.py ./my_tiles --json-path data.json --output-dir results
    ```
  * **Generate only the HTML viewer:**
    ```bash
    python analyze_med_tiles.py ./my_tiles --json-path data.json --output-dir results --html-only
    ```
  * **Generate only the edge density analysis:**
    ```bash
    python analyze_med_tiles.py ./my_tiles --json-path data.json --output-dir results --analysis-only
    ```

## Outputs

After running the scripts, you will find the following files in your specified output directory:

  * `data.json`: A JSON file containing the metrics for each image tile.
  * `image_viewer.html`: An interactive HTML page for viewing and sorting the image tiles and their metrics.
  * `edge_density_binary_heatmap.png`: A heatmap visualizing which tiles have zero vs. non-zero edge density.
  * `edge_density_graded_heatmap_log_scale.png`: A graded heatmap showing the distribution of edge density values.
  * `edge_density_nonzero_histogram.png`: A histogram of the distribution of non-zero edge density values.
  * The script also logs a detailed statistical report for edge density to the console.
