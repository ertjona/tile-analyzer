import tensorflow as tf
import numpy as np
from PIL import Image
import argparse
import pathlib
import shutil
from tqdm import tqdm
import time
import concurrent.futures
import tempfile
import csv

# Custom layer definition required to load the model
class RandomBlur(tf.keras.layers.Layer):
    def __init__(self, probability=0.25, kernel_size=3, **kwargs):
        super().__init__(**kwargs)
        self.probability = probability
        self.kernel_size = kernel_size
    def call(self, images, training=None):
        return images
    def get_config(self):
        config = super().get_config()
        config.update({"probability": self.probability, "kernel_size": self.kernel_size})
        return config

# Helper function for the parallel preprocessing step
def process_image_for_prediction(source_path, temp_dir):
    try:
        with Image.open(source_path) as img:
            if img.size != (256, 256):
                return source_path, None, f'skipped_size_{img.size}'
        
        temp_png_path = temp_dir / f"{source_path.stem}_{hash(source_path)}.png"
        shutil.copy2(source_path, temp_png_path.with_suffix('.webp'))
        with Image.open(temp_png_path.with_suffix('.webp')) as temp_img:
            temp_img.convert('RGB').save(temp_png_path, 'png')
        temp_png_path.with_suffix('.webp').unlink()
        
        return source_path, temp_png_path, 'valid'
    except Exception as e:
        return source_path, None, f'skipped_error_{e}'

# Helper function for the tf.data pipeline
def parse_png_image(filepath):
    img_bytes = tf.io.read_file(filepath)
    image = tf.io.decode_png(img_bytes, channels=3)
    image = tf.image.resize(image, [256, 256])
    image.set_shape([256, 256, 3])
    return image, filepath

def main(args):
    script_start_time = time.time()
    
    # --- 1. SETUP ---
    output_path = pathlib.Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model = tf.keras.models.load_model(args.model_path, custom_objects={'RandomBlur': RandomBlur})
    # --- MODIFICATION: Hardcode the class names ---
    class_names = ['marker', 'not_marker']
    print(f"Using predefined classes: {class_names} (0={class_names[0]}, 1={class_names[1]})")

    # --- 2. PARALLEL PREPARATION in a TEMPORARY DIRECTORY ---
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = pathlib.Path(temp_dir_str)
        all_source_paths = list(pathlib.Path(args.image_folder).glob('**/*.webp'))
        
        # --- Start timing the conversion/filtering step ---
        conversion_start_time = time.time()
        
        valid_png_paths = []
        path_map = {}
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_to_path = {executor.submit(process_image_for_prediction, path, temp_dir): path for path in all_source_paths}
            for future in tqdm(concurrent.futures.as_completed(future_to_path), total=len(all_source_paths), desc="Converting & Filtering"):
                source_path, temp_path, status = future.result()
                if status == 'valid':
                    valid_png_paths.append(str(temp_path))
                    path_map[str(temp_path)] = source_path
        
        conversion_end_time = time.time() # --- End timing ---
        
        # --- 3. HIGH-PERFORMANCE PREDICTION ---
        prediction_results = []
        if valid_png_paths:
            AUTOTUNE = tf.data.AUTOTUNE
            path_ds = tf.data.Dataset.from_tensor_slices(valid_png_paths)
            dataset = path_ds.map(parse_png_image, num_parallel_calls=AUTOTUNE).batch(args.batch_size).prefetch(buffer_size=AUTOTUNE)

            # --- Start timing the prediction step ---
            prediction_start_time = time.time()
            
            for image_batch, path_batch in tqdm(dataset, desc="Predicting Batches"):
                predictions = model.predict(image_batch, verbose=0)
                path_batch_str = [p.numpy().decode('utf-8') for p in path_batch]
                for path_str, pred in zip(path_batch_str, predictions):
                    original_path = path_map.get(path_str)
                    if original_path:
                        prediction_results.append((original_path, pred[0]))
            
            prediction_end_time = time.time() # --- End timing ---

        # --- 4. SAVE RESULTS TO CSV ---
        with open(output_path, 'w', newline='') as csvfile:
            # ... (CSV writing is the same) ...
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(['filepath', 'predicted_class', 'confidence_score', 'raw_score'])
            for path, score in prediction_results:
                # ... (Logic to determine class and confidence) ...
                predicted_class = class_names[0] if score < 0.5 else class_names[1]
                confidence = 1 - score if score < 0.5 else score
                csv_writer.writerow([path, predicted_class, f"{confidence:.4f}", f"{score:.4f}"])

    # --- 5. FINAL ENHANCED REPORT ---
    script_end_time = time.time()
    total_duration = script_end_time - script_start_time
    conversion_duration = conversion_end_time - conversion_start_time
    prediction_duration = prediction_end_time - prediction_start_time if valid_png_paths else 0
    processed_count = len(prediction_results)
    images_per_second = processed_count / total_duration if total_duration > 0 else 0
    
    print("\n" + "="*40)
    print("        Batch Prediction Summary")
    print("="*40)
    print(f"Total files found:\t\t{len(all_source_paths)}")
    print(f"Files skipped:\t\t\t{len(all_source_paths) - processed_count}")
    print(f"Successfully processed:\t\t{processed_count} images")
    print("-" * 40)
    print(f"Conversion/Filtering time:\t{conversion_duration:.2f} seconds ({conversion_duration/60:.2f} minutes)")
    print(f"Prediction time:\t\t{prediction_duration:.2f} seconds ({prediction_duration/60:.2f} minutes)")
    print(f"Total time:\t\t\t{total_duration:.2f} seconds ({total_duration/60:.2f} minutes)")
    print(f"Overall speed:\t\t\t{images_per_second:.2f} images/second")
    print(f"Results saved to:\t\t{output_path.resolve()}")
    print("="*40)
    
    # Performance Suggestions
    if prediction_duration > 0 and conversion_duration > prediction_duration:
        print("💡 Performance suggestion: The data preparation step (conversion/filtering) is the bottleneck.")
        print("   Your GPU is fast! Increasing the --batch_size might help hide this latency further.")
    else:
        print("💡 Performance suggestion: The pipeline is well-balanced or GPU-bound.")
        print("   You are likely getting the maximum performance from your hardware with this configuration.")
    print("="*40)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Portable, high-performance batch prediction.")
    parser.add_argument('--image_folder', required=True, type=str)
    parser.add_argument('--model_path', required=True, type=str)
    # --- MODIFICATION: Removed the train_dir argument ---
    parser.add_argument('--output_csv', default='predictions.csv', type=str)
    parser.add_argument('--batch_size', default=128, type=int)
    # Adding max_workers argument for tuning
    parser.add_argument('--workers', default=None, type=int, help='Number of CPU workers for preprocessing. Defaults to all available cores.')
    
    parsed_args = parser.parse_args()
    main(parsed_args)