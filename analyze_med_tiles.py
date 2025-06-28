import json
import argparse
import os
import statistics
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import logging
from matplotlib.colors import LogNorm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ImageAnalyzer:
    """Main class for analyzing image data and generating outputs."""
    
    def __init__(self, json_path, output_dir):
        self.json_path = json_path
        self.output_dir = output_dir
        self.image_dir = None
        self.data = None
        self.image_data = []
        self.stats = {}
        
    def load_data(self):
        """Load and validate JSON data."""
        try:
            with open(self.json_path, 'r') as f:
                loaded_json = json.load(f)
            
            self.image_dir = loaded_json.get("image_directory")
            if not self.image_dir:
                logging.error("Error: 'image_directory' not found in the JSON file.")
                return False

            self.data = loaded_json.get("tiles", {})
            logging.info(f"Loaded data from: {self.json_path}")
            return True
        except FileNotFoundError:
            logging.error(f"Error: The file '{self.json_path}' was not found.")
            return False
        except json.JSONDecodeError:
            logging.error(f"Error: The file '{self.json_path}' is not a valid JSON file.")
            return False
    
    def prepare_data(self):
        """Extract and prepare image data for analysis."""
        if not self.data:
            return False
            
        # Extract successful images and their metrics
        self.image_data = []
        score_lists = {
            "brightness": [], "laplacian": [], "saturation": [],
            "entropy": [], "edgedensity": []
        }

        missing_files_count = 0
        
        for filename, attributes in self.data.items():
            if attributes.get('status') == 'success':
                # Check if the image file actually exists
                image_path = os.path.join(self.image_dir, filename)
                if os.path.exists(image_path):
                    item_data = {
                        'filename': filename,
                        'brightness': attributes.get('avg_brightness', 0),
                        'laplacian': attributes.get('laplacian', 0),
                        'saturation': attributes.get('avg_saturation', 0),
                        'entropy': attributes.get('entropy', 0),
                        'edgedensity': attributes.get('edge_density', 0)
                    }
                    self.image_data.append(item_data)
                    for key in score_lists:
                        # Make sure the key exists in item_data before appending
                        if key in item_data:
                            score_lists[key].append(item_data[key])
                else:
                    missing_files_count += 1

        if missing_files_count > 0:
            logging.warning(f"{missing_files_count} images from the JSON file were not found in the image directory and will be excluded from the analysis.")

        # Calculate statistics
        self.stats = {
            "total_images": len(self.data),
            "successful_images": len(self.image_data) # This now reflects existing files
        }
        
        percentiles_to_calc = [50, 67, 75, 90, 95, 99]
        for key, scores in score_lists.items():
            if not scores:
                continue
            self.stats[key] = {
                "min": min(scores),
                "max": max(scores),
                "mean": statistics.mean(scores),
                "mode": statistics.mode(scores),
                "stdev": statistics.stdev(scores),
                "percentiles": {}
            }
            percentile_values = np.percentile(scores, percentiles_to_calc)
            for i, p in enumerate(percentiles_to_calc):
                self.stats[key]["percentiles"][p] = percentile_values[i]
        
        logging.info(f"Prepared data for {len(self.image_data)} successful and existing images")
        
        if not self.image_data:
            logging.error("No valid image data to analyze after checking for file existence.")
            return False
                       
        return True
    
    def generate_html_viewer(self):
        """Generate the paginated HTML viewer."""
        if not self.image_data:
            logging.warning("No image data available for HTML generation")
            return False
            
        # Pre-format statistics HTML strings
        stats_html = {}
        score_keys = ["brightness", "laplacian", "saturation", "entropy", "edgedensity"]
        
        for key in score_keys:
            s = self.stats.get(key, {})
            min_val = s.get('min', 0)
            max_val = s.get('max', 0)
            mean_val = s.get('mean', 0)
            mode_val = s.get('mode', 0)
            stdev_val = s.get('stdev', 0)

            stats_html[f'{key}_main'] = f"<p><b>Min:</b> {min_val:.6f} | <b>Max:</b> {max_val:.6f} | <b>Mean:</b> {mean_val:.6f} | <b>Mode:</b> {mode_val:.6f} | <b>Stdev:</b> {stdev_val:.6f}</p>"
            
            p_dict = s.get('percentiles', {})
            if p_dict:
                p_strings = [f"<b>{p}th:</b> {val:.6f}" for p, val in p_dict.items()]
                stats_html[f'{key}_percentiles'] = "<p>" + " | ".join(p_strings) + "</p>"
            else:
                stats_html[f'{key}_percentiles'] = ""

        # Generate HTML content
        image_data_json = json.dumps(self.image_data)
        html_content = self._generate_html_template(stats_html, image_data_json)
        
        # Save HTML file
        output_path = os.path.join(self.output_dir, 'image_viewer.html')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logging.info(f"Generated HTML viewer: {output_path}")
        return True
    
    def _generate_html_template(self, stats_html, image_data_json):
        """Generate the HTML template with embedded data."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebP Image Viewer (Paginated)</title>
    <style>
        body {{ font-family: sans-serif; margin: 20px; }}
        h1, h2, h3 {{ text-align: center; }}
        .stats {{ margin-bottom: 20px; padding: 20px; border: 1px solid #ccc; }}
        .stats p {{ margin: 8px 0; text-align: center; }}
        .controls, .pagination {{ text-align: center; margin: 20px 0; display: flex; justify-content: center; align-items: center; flex-wrap: wrap; }}
        button {{ padding: 10px 15px; font-size: 14px; cursor: pointer; margin: 5px; }}
        button:disabled {{ cursor: not-allowed; opacity: 0.5; }}
        .image-grid {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 15px; min-height: 500px; }}
        .image-item {{ border: 1px solid #ddd; padding: 10px; text-align: center; width: 270px; }}
        img {{ max-width: 256px; max-height: 256px; }}
        .filename {{ font-weight: bold; margin-top: 5px; word-break: break-all; }}
        #page-info {{ font-size: 16px; font-weight: bold; margin: 0 15px; }}
        .page-input {{ width: 70px; text-align: center; padding: 10px; margin: 0 5px; }}
    </style>
</head>
<body>
    <h1>{self.image_dir.replace(os.path.sep, '/')}</h1>

    <div class="stats">
        <h2>Statistics</h2>
        <p><b>Total Images in JSON:</b> {self.stats['total_images']} | <b>Displayed Images (status 'success'):</b> {self.stats['successful_images']}</p>
        <hr>
        <h3>Brightness</h3>
        {stats_html.get('brightness_main', '')}
        {stats_html.get('brightness_percentiles', '')}
        <hr>
        <h3>Laplacian</h3>
        {stats_html.get('laplacian_main', '')}
        {stats_html.get('laplacian_percentiles', '')}
        <hr>
        <h3>Saturation</h3>
        {stats_html.get('saturation_main', '')}
        {stats_html.get('saturation_percentiles', '')}
        <hr>
        <h3>Entropy</h3>
        {stats_html.get('entropy_main', '')}
        {stats_html.get('entropy_percentiles', '')}
        <hr>
        <h3>Edge Density</h3>
        {stats_html.get('edgedensity_main', '')}
        {stats_html.get('edgedensity_percentiles', '')}
    </div>

    <div class="controls">
        <button onclick="sortImages('brightness', 'desc')">Sort Brightness (High-Low)</button>
        <button onclick="sortImages('brightness', 'asc')">Sort Brightness (Low-High)</button>
        <button onclick="sortImages('laplacian', 'desc')">Sort Laplacian (High-Low)</button>
        <button onclick="sortImages('laplacian', 'asc')">Sort Laplacian (Low-High)</button>
        <button onclick="sortImages('saturation', 'desc')">Sort Saturation (High-Low)</button>
        <button onclick="sortImages('saturation', 'asc')">Sort Saturation (Low-High)</button>
        <button onclick="sortImages('entropy', 'desc')">Sort Entropy (High-Low)</button>
        <button onclick="sortImages('entropy', 'asc')">Sort Entropy (Low-High)</button>
        <button onclick="sortImages('edgedensity', 'desc')">Sort Edge Density (High-Low)</button>
        <button onclick="sortImages('edgedensity', 'asc')">Sort Edge Density (Low-High)</button>
    </div>

    <div class="pagination" id="pagination-top">
        <button id="prev-btn-top" onclick="prevPage()">Previous</button>
        <span id="page-info-top"></span>
        <button id="next-btn-top" onclick="nextPage()">Next</button>
        <input type="number" id="page-input-top" class="page-input" placeholder="Page #">
        <button id="go-btn-top" onclick="goToPage('top')">Go</button>
    </div>

    <div class="image-grid" id="image-grid"></div>

    <div class="pagination" id="pagination-bottom">
        <button id="prev-btn-bottom" onclick="prevPage()">Previous</button>
        <span id="page-info-bottom"></span>
        <button id="next-btn-bottom" onclick="nextPage()">Next</button>
        <input type="number" id="page-input-bottom" class="page-input" placeholder="Page #">
        <button id="go-btn-bottom" onclick="goToPage('bottom')">Go</button>
    </div>

    <script>
        const imageData = {image_data_json};
        const imageDir = "{self.image_dir.replace(os.path.sep, '/')}";
        const grid = document.getElementById('image-grid');
        
        const pageInfoTop = document.getElementById('page-info-top');
        const pageInfoBottom = document.getElementById('page-info-bottom');
        const pageInputTop = document.getElementById('page-input-top');
        const pageInputBottom = document.getElementById('page-input-bottom');

        const nav = {{
            'top': {{'prev': document.getElementById('prev-btn-top'), 'next': document.getElementById('next-btn-top')}},
            'bottom': {{'prev': document.getElementById('prev-btn-bottom'), 'next': document.getElementById('next-btn-bottom')}}
        }};

        let currentPage = 1;
        const itemsPerPage = 100;

        function sortImages(sortBy, order) {{
            imageData.sort((a, b) => {{
                const valA = a[sortBy];
                const valB = b[sortBy];
                return order === 'asc' ? valA - valB : valB - valA;
            }});
            currentPage = 1;
            renderPage();
        }}

        function prevPage() {{
            if (currentPage > 1) {{
                currentPage--;
                renderPage();
            }}
        }}

        function nextPage() {{
            const totalPages = Math.ceil(imageData.length / itemsPerPage);
            if (currentPage < totalPages) {{
                currentPage++;
                renderPage();
            }}
        }}
        
        function goToPage(pos) {{
            const pageInput = (pos === 'top') ? pageInputTop : pageInputBottom;
            const pageNum = parseInt(pageInput.value, 10);
            const totalPages = Math.ceil(imageData.length / itemsPerPage);

            if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {{
                currentPage = pageNum;
                renderPage();
            }} else {{
                alert(`Invalid page number. Please enter a number between 1 and ${{totalPages}}.`);
            }}
            pageInput.value = '';
        }}

        function renderPage() {{
            grid.innerHTML = ''; 
            window.scrollTo(0, 0);

            const totalPages = Math.ceil(imageData.length / itemsPerPage);
            const start = (currentPage - 1) * itemsPerPage;
            const end = start + itemsPerPage;
            const pageItems = imageData.slice(start, end);

            for (const item of pageItems) {{
                const itemDiv = document.createElement('div');
                itemDiv.className = 'image-item';
                itemDiv.innerHTML = `
                    <img src="${{imageDir}}/${{item.filename}}" alt="${{item.filename}}">
                    <p class="filename">${{item.filename}}</p>
                    <p>
                        Brightness: ${{item.brightness.toFixed(6)}}<br>
                        Laplacian: ${{item.laplacian.toFixed(6)}}<br>
                        Saturation: ${{item.saturation.toFixed(6)}}<br>
                        Entropy: ${{item.entropy.toFixed(6)}}<br>
                        Edge Density: ${{item.edgedensity.toFixed(6)}}
                    </p>
                `;
                grid.appendChild(itemDiv);
            }}

            const pageStr = `Page ${{currentPage}} of ${{totalPages}}`;
            pageInfoTop.textContent = pageStr;
            pageInfoBottom.textContent = pageStr;
            
            for (const pos in nav) {{
                nav[pos].prev.disabled = currentPage === 1;
                nav[pos].next.disabled = currentPage === totalPages;
            }}
        }}

        document.addEventListener('DOMContentLoaded', () => {{
            if (imageData.length > 0) {{
                renderPage();
            }} else {{
                grid.innerHTML = '<p>No successful images to display.</p>';
                document.getElementById('pagination-top').style.display = 'none';
                document.getElementById('pagination-bottom').style.display = 'none';
            }}
        }});
    </script>
</body>
</html>
"""
    
    def analyze_edge_density(self):
        """Perform detailed edge density analysis and generate visualizations."""
        if not self.data:
            logging.warning("No data available for edge density analysis")
            return False
            
        # Check if edge_density exists in the data
        has_edge_density = any(
            'edge_density' in attrs for attrs in self.data.values() 
            if isinstance(attrs, dict)
        )
        
        if not has_edge_density:
            logging.error("The input JSON file does not contain the 'edge_density' metric.")
            logging.error("Please re-run the 'generate' command with the --measure-edgedensity flag.")
            return False
        
        # Create DataFrame for analysis
        records = [dict(filename=fn, **rec) for fn, rec in self.data.items()]
        df = pd.DataFrame(records)
        
        # Filter for successful tiles
        df_success = df[df['status'] == 'success'].copy()
        if df_success.empty:
            logging.warning("No records with status 'success' found. No edge density analysis to perform.")
            return False
            
        logging.info(f"Analyzing edge density for {len(df_success)} tiles with status 'success'.")
        
        # Generate analysis report
        self._generate_edge_density_report(df_success)
        
        # Generate visualizations
        self._generate_edge_density_visualizations(df_success)
        
        return True
    
    def _generate_edge_density_report(self, df_success):
        """Generate and log edge density statistics."""
        logging.info("="*50)
        logging.info("EDGE DENSITY ANALYSIS REPORT")
        logging.info("="*50)
        
        # Basic statistics
        stats = df_success['edge_density'].describe()
        logging.info("\n--- Basic Statistics ---")
        print(f"Count: {stats['count']:.0f}")
        print(f"Min: {stats['min']:.6f}")
        print(f"Max: {stats['max']:.6f}")
        print(f"Mean: {stats['mean']:.6f}")
        #print(f"Median: {stats['50%']:.6f}")
        print(f"Std Dev: {stats['std']:.6f}")
        
        # Zero-value analysis
        zero_density_tiles = df_success[df_success['edge_density'] == 0]
        zero_count = len(zero_density_tiles)
        total_count = len(df_success)
        zero_percentage = (zero_count / total_count) * 100
        
        logging.info("\n--- Zero-Value Analysis ---")
        print(f"Tiles with zero edge density: {zero_count} / {total_count} ({zero_percentage:.2f}%)")
        
        # Percentile distribution
        percentiles = [0.5, 0.67, 0.75, 0.90, 0.95, 0.99]
        percentile_values = df_success['edge_density'].quantile(percentiles)
        
        logging.info("\n--- Percentile Distribution ---")
        for p, val in percentile_values.items():
            print(f"{p*100:.0f}th percentile: {val:.6f}")
    
    def _generate_edge_density_visualizations(self, df_success):
        """Generate edge density visualizations."""
        logging.info("\n--- Generating Edge Density Visualizations ---")
        
        # Check if we have spatial data (row/col) for heatmaps
        has_spatial_data = 'row' in df_success.columns and 'col' in df_success.columns
        
        if has_spatial_data:
            # Binary heatmap (Zero vs. Non-Zero)
            self._create_binary_heatmap(df_success)
            
            # Graded heatmap with log scale
            self._create_graded_heatmap(df_success)
        else:
            logging.warning("No spatial data (row/col columns) found. Skipping heatmap generation.")
        
        # Histogram of non-zero values
        self._create_edge_density_histogram(df_success)
    
    def _create_binary_heatmap(self, df_success):
        """Create binary heatmap showing zero vs non-zero edge density."""
        df_success['is_zero'] = np.where(df_success['edge_density'] == 0, 0, 1)
        
        # Calculate statistics
        zero_count = (df_success['is_zero'] == 0).sum()
        total_count = len(df_success)
        zero_percentage = (zero_count / total_count) * 100 if total_count > 0 else 0
        
        # Create heatmap
        heatmap_data = df_success.pivot(index='row', columns='col', values='is_zero')
        
        plt.figure(figsize=(12, 10))
        sns.heatmap(heatmap_data, square=True, cmap='cividis', cbar_kws={'ticks': [0, 1]})
        plt.title('Edge Density Binary Heatmap (0 = Zero, 1 = Non-Zero)', fontsize=14, pad=20)
        
        # Add statistics annotation
        stats_text = f"Tiles with Zero Edge Density: {zero_count} of {total_count} ({zero_percentage:.2f}%)"
        plt.figtext(0.05, 0.01, stats_text, ha="center", fontsize=12,
                   bbox={"facecolor":"white", "alpha":0.8, "pad":8})
        
        output_path = os.path.join(self.output_dir, 'edge_density_binary_heatmap.png')
        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        plt.close()
        logging.info(f"Generated binary heatmap: {output_path}")
    
    def _create_graded_heatmap(self, df_success):
        """Create graded heatmap with logarithmic scale."""
        heatmap_data = df_success.pivot(index='row', columns='col', values='edge_density')
        
        # Set up logarithmic scaling
        min_val = heatmap_data[heatmap_data > 0].min().min()
        
        if pd.isna(min_val):
            logging.warning("All edge density values are zero. Using linear scale for graded heatmap.")
            norm = None
            title_suffix = ""
        else:
            norm = LogNorm(vmin=min_val, vmax=heatmap_data.max().max())
            title_suffix = " (Log Scale)"
        
        plt.figure(figsize=(12, 10))
        sns.heatmap(heatmap_data, square=True, cmap='jet', norm=norm)
        plt.title(f'Edge Density Graded Heatmap{title_suffix}', fontsize=14, pad=20)
        
        output_path = os.path.join(self.output_dir, 'edge_density_graded_heatmap_log_scale.png')
        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        plt.close()
        logging.info(f"Generated graded heatmap: {output_path}")
    
    def _create_edge_density_histogram(self, df_success):
        """Create histogram of non-zero edge density values."""
        non_zero_df = df_success[df_success['edge_density'] > 0]
        
        if non_zero_df.empty:
            logging.info("No non-zero edge density tiles found. Skipping histogram generation.")
            return
        
        plt.figure(figsize=(12, 8))
        ax = sns.histplot(non_zero_df['edge_density'], bins=50, kde=True, alpha=0.7)
        ax.set_title('Distribution of Non-Zero Edge Density Values', fontsize=14, pad=20)
        ax.set_xlabel('Edge Density', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        
        # Add statistics text
        stats_text = (f"Count: {len(non_zero_df)}\n"
                     f"Mean: {non_zero_df['edge_density'].mean():.6f}\n"
                     f"Median: {non_zero_df['edge_density'].median():.6f}")
        
        plt.text(0.75, 0.95, stats_text, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        plt.tight_layout()
        output_path = os.path.join(self.output_dir, 'edge_density_nonzero_histogram.png')
        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        plt.close()
        logging.info(f"Generated histogram: {output_path}")
    
    def run_complete_analysis(self):
        """Run the complete analysis pipeline."""
        logging.info("Starting complete image analysis pipeline...")
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Load and prepare data
        if not self.load_data():
            return False
        
        if not self.prepare_data():
            return False
        
        # Generate HTML viewer
        html_success = self.generate_html_viewer()
        
        # Generate edge density analysis
        edge_analysis_success = self.analyze_edge_density()
        
        # Summary
        logging.info("="*50)
        logging.info("ANALYSIS COMPLETE")
        logging.info("="*50)
        logging.info(f"Output directory: {self.output_dir}")
        logging.info(f"HTML viewer generated: {'✓' if html_success else '✗'}")
        logging.info(f"Edge density analysis: {'✓' if edge_analysis_success else '✗'}")
        
        return html_success or edge_analysis_success


def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(
        description='Generate HTML viewer and perform edge density analysis for webp images from JSON data.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate both HTML viewer and edge density analysis
  python analyze_med_tiles.py --json-path data.json --output-dir results
  
  # Generate only HTML viewer
  python analyze_med_tiles.py --json-path data.json --output-dir results --html-only
  
  # Generate only edge density analysis
  python analyze_med_tiles.py --json-path data.json --output-dir results --analysis-only
        """
    )
    
    parser.add_argument('--json-path', type=str, required=True,
                       help='Path to the input JSON file containing image metrics')
    parser.add_argument('--output-dir', type=str, default='RESULTS',
                       help='Directory to save all output files (default: RESULTS)')
    parser.add_argument('--html-only', action='store_true',
                       help='Generate only the HTML viewer')
    parser.add_argument('--analysis-only', action='store_true',
                       help='Generate only the edge density analysis')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.html_only and args.analysis_only:
        parser.error("Cannot specify both --html-only and --analysis-only")
    
    if not os.path.exists(args.json_path):
        parser.error(f"JSON file does not exist: {args.json_path}")
    
    # Create analyzer instance
    analyzer = ImageAnalyzer(args.json_path, args.output_dir)
    
    # Load data
    if not analyzer.load_data():
        return

    # Validate image directory from JSON
    if not os.path.isdir(analyzer.image_dir):
        parser.error(f"Image directory '{analyzer.image_dir}' from JSON file not found.")

    # Run analysis based on arguments
    if args.html_only:
        # Load data and generate HTML only
        if analyzer.prepare_data():
            analyzer.generate_html_viewer()
    elif args.analysis_only:
        analyzer.analyze_edge_density()
    else:
        # Run complete analysis
        analyzer.run_complete_analysis()


if __name__ == '__main__':
    main()