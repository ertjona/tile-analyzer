# backend/main.py

import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import numpy as np
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
import asyncio
import re
from datetime import datetime
import os
import json # <-- ENSURE THIS LINE IS PRESENT

# --- Configuration ---
SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR.parent / "database" / "analysis.db"
app = FastAPI()


## NEW: Pydantic models to define the structure of our POST request body
class Filter(BaseModel):
    key: str
    op: str
    value: Any

class Sort(BaseModel):
    key: str
    order: str

class TilesRequest(BaseModel):
    filters: List[Filter] = []
    sort: List[Sort] = [Sort(key="id", order="asc")]
    page: int = 1
    limit: int = 50

# --- Add this new Pydantic model with your others ---
class IngestionRequest(BaseModel):
    folder_path: str

# --- Helper Functions ---
def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    return conn


# --- API Endpoints ---

@app.post("/api/tiles")
def search_tiles(request: TilesRequest) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()

    base_query = "SELECT T.*, S.json_filename FROM ImageTiles T JOIN SourceFiles S ON T.source_file_id = S.id"
    count_query = "SELECT COUNT(T.id) FROM ImageTiles T JOIN SourceFiles S ON T.source_file_id = S.id"
    
    where_clauses = []
    params = []

    if request.filters:
        for f in request.filters:
            valid_operators = {">", "<", ">=", "<=", "==", "!="}
            if f.op in valid_operators:
                # MODIFIED: Backend now intelligently adds the correct prefix
                prefix = "S" if f.key == "json_filename" else "T"
                where_clauses.append(f"{prefix}.{f.key} {f.op} ?")
                params.append(f.value)
            else:
                continue

    order_by_parts = []
    if request.sort:
        for s in request.sort:
            order = s.order.upper() if s.order.lower() in ['asc', 'desc'] else 'ASC'
            prefix = "S" if s.key == "json_filename" else "T"
            order_by_parts.append(f"{prefix}.{s.key} {order}")
    
    order_by_clause = "ORDER BY " + ", ".join(order_by_parts) if order_by_parts else "ORDER BY T.id ASC"

    pagination_clause = "LIMIT ? OFFSET ?"
    offset = (request.page - 1) * request.limit
    
    final_query = base_query
    if where_clauses:
        final_query += f" WHERE {' AND '.join(where_clauses)}"
        count_query += f" WHERE {' AND '.join(where_clauses)}"
    
    final_query += f" {order_by_clause} {pagination_clause}"

    try:
        cursor.execute(count_query, params)
        total_results = cursor.fetchone()[0]

        cursor.execute(final_query, params + [request.limit, offset])
        tiles = cursor.fetchall()
        results = [dict(row) for row in tiles]
        
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=400, detail=f"Database query error: {e}")
    finally:
        conn.close()

    return {
        "page": request.page, 
        "limit": request.limit, 
        "total_results": total_results, 
        "results": results
    }

@app.post("/api/ingest")
async def start_ingestion(request: Request, ingestion_request: IngestionRequest):
    """
    Starts an ingestion process and streams logs back to the client.
    """
    async def log_generator():
        """A generator function that yields log messages."""
        folder_path = ingestion_request.folder_path
        yield f"data: Starting ingestion for folder: {folder_path}\n\n"
        await asyncio.sleep(0.1)

        if not os.path.isdir(folder_path):
            yield f"data: ERROR: Folder not found.\n\n"
            return

        try:
            file_pattern = r'.*\.json'
            filename_re = re.compile(file_pattern)
            all_files_in_dir = os.listdir(folder_path)
            json_files = [os.path.join(folder_path, f) for f in all_files_in_dir if filename_re.fullmatch(f)]
        except Exception as e:
            yield f"data: ERROR: Could not read folder contents: {e}\n\n"
            return
            
        if not json_files:
            yield f"data: No new JSON files found to process.\n\n"
            return

        yield f"data: Found {len(json_files)} JSON files to process.\n\n"
        await asyncio.sleep(0.1)
        
        conn = get_db_connection()
        cursor = conn.cursor()

        for file_path in json_files:
            filename = os.path.basename(file_path)
            
            # Idempotency Check
            cursor.execute("SELECT id FROM SourceFiles WHERE json_filename = ?", (filename,))
            if cursor.fetchone():
                yield f"data: Skipping '{filename}', already ingested.\n\n"
                await asyncio.sleep(0.1)
                continue

            yield f"data: Processing '{filename}'...\n\n"
            await asyncio.sleep(0.1)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Insert into SourceFiles
                image_directory = data.get("image_directory", "")
                ingested_at_str = datetime.now().isoformat()
                cursor.execute(
                    "INSERT INTO SourceFiles (json_filename, image_directory, ingested_at) VALUES (?, ?, ?)",
                    (filename, image_directory, ingested_at_str)
                )
                source_file_id = cursor.lastrowid

                # Insert tiles
                tiles = data.get("tiles", {})
                tile_count = 0
                for tile_name, attributes in tiles.items():
                    if not isinstance(attributes, dict): continue
                    tile_values = (
                        source_file_id, tile_name, attributes.get('status'), attributes.get('col'),
                        attributes.get('row'), attributes.get('size'), attributes.get('laplacian'),
                        attributes.get('avg_brightness'), attributes.get('avg_saturation'),
                        attributes.get('entropy'), attributes.get('edge_density'),
                        attributes.get('foreground_ratio') # Add the new value
                    )
                    cursor.execute(
                        '''INSERT INTO ImageTiles (source_file_id, webp_filename, status, col, row, size, 
                                                  laplacian, avg_brightness, avg_saturation, entropy, edge_density, foreground_ratio)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        tile_values
                    )
                    tile_count += 1
                
                conn.commit()
                yield f"data: SUCCESS: Ingested '{filename}' with {tile_count} tiles.\n\n"
                await asyncio.sleep(0.1)

            except Exception as e:
                yield f"data: ERROR: Failed to process '{filename}': {e}\n\n"
                await asyncio.sleep(0.1)
                conn.rollback()

        conn.close()
        yield f"data: Ingestion process complete.\n\n"

    return EventSourceResponse(log_generator())
    
# --- (Your other endpoints: /images, /api/stats, etc. remain unchanged) ---

@app.get("/images/{source_id}/{webp_filename}")
def get_image(source_id: int, webp_filename: str):
    """
    Finds the image on the server's disk and returns it as a file response.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Find the image_directory from the SourceFiles table
    cursor.execute("SELECT image_directory FROM SourceFiles WHERE id = ?", (source_id,))
    record = cursor.fetchone()
    conn.close()
    
    if not record:
        raise HTTPException(status_code=404, detail="Source file ID not found.")
        
    # Construct the full path to the image file
    # NOTE: This assumes the image_directory is an absolute path or accessible from the server
    image_path = Path(record["image_directory"]) / webp_filename
    
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail=f"Image file not found at: {image_path}")
        
    # Return the image file
    return FileResponse(image_path)

# --- NEW: Endpoint to get a list of all source JSON filenames ---
@app.get("/api/source_files")
def get_source_files() -> List[str]:
    """Retrieves a list of all unique json_filename values."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # The ORDER BY clause ensures the list is sorted alphabetically
    cursor.execute("SELECT json_filename FROM SourceFiles ORDER BY json_filename ASC")
    # We use a list comprehension to flatten the list of tuples into a simple list of strings
    filenames = [row[0] for row in cursor.fetchall()]
    conn.close()
    return filenames

# --- NEW: Endpoint for a high-level summary ---
@app.get("/api/stats/summary")
def get_summary_stats():
    """Returns a summary of the dataset (total files and tiles)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    total_files = cursor.execute("SELECT COUNT(*) FROM SourceFiles").fetchone()[0]
    total_tiles = cursor.execute("SELECT COUNT(*) FROM ImageTiles").fetchone()[0]
    
    conn.close()
    
    return {
        "total_source_files": total_files,
        "total_image_tiles": total_tiles
    }

# --- NEW: Endpoint for detailed distribution stats of a column ---
@app.get("/api/stats/distribution/{column_name}")
def get_distribution_stats(column_name: str):
    """
    Calculates and returns descriptive statistics for a given numeric column.
    """
    # Validate column name to prevent SQL injection
    allowed_columns = ["laplacian", "avg_brightness", "avg_saturation", "entropy", "edge_density"]
    if column_name not in allowed_columns:
        raise HTTPException(status_code=400, detail="Invalid column name for statistics.")

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch all non-null values from the column
    query = f"SELECT {column_name} FROM ImageTiles WHERE {column_name} IS NOT NULL"
    values = [row[0] for row in cursor.execute(query).fetchall()]
    conn.close()
    
    if not values:
        return {"column": column_name, "count": 0}

    # Use NumPy to calculate statistics
    np_values = np.array(values)
    
    return {
        "column": column_name,
        "count": len(np_values),
        "mean": np.mean(np_values),
        "std_dev": np.std(np_values),
        "min": np.min(np_values),
        "percentile_25": np.percentile(np_values, 25),
        "median_50": np.median(np_values),
        "percentile_75": np.percentile(np_values, 75),
        "max": np.max(np_values),
    }

# In backend/main.py

# ... (keep all your existing imports and Pydantic models) ...
# ... (No new Python libraries are needed for this step) ...

# NEW: Define Pydantic models for the heatmap request
class HeatmapCondition(BaseModel):
    key: str
    op: str
    value: Any

class RuleGroup(BaseModel):
    logical_op: str
    conditions: List[HeatmapCondition]

class HeatmapRule(BaseModel):
    color: str
    rule_group: RuleGroup

class HeatmapRulesConfig(BaseModel):
    default_color: str
    rules: List[HeatmapRule]

class HeatmapRequest(BaseModel):
    json_filename: str
    rules_config: HeatmapRulesConfig


# ... (keep your get_db_connection, search_tiles, get_image, and stats endpoints) ...


# --- NEW: Endpoint to generate heatmap data ---
@app.post("/api/heatmap")
def generate_heatmap(request: HeatmapRequest) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all tiles for the specified JSON file
    query = "SELECT T.* FROM ImageTiles T JOIN SourceFiles S ON T.source_file_id = S.id WHERE S.json_filename = ?"
    try:
        tiles = [dict(row) for row in cursor.execute(query, (request.json_filename,)).fetchall()]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    if not tiles:
        return {"grid_width": 0, "grid_height": 0, "heatmap_data": []}

    # Determine grid size
    max_col = max(t['col'] for t in tiles)
    max_row = max(t['row'] for t in tiles)
    grid_width = max_col + 1
    grid_height = max_row + 1

    # Initialize grid with default color
    heatmap_data = [request.rules_config.default_color] * (grid_width * grid_height)

    # Dictionary of operators for easy lookup
    ops = {'>': (lambda a, b: a > b), '<': (lambda a, b: a < b), '>=': (lambda a, b: a >= b),
           '<=': (lambda a, b: a <= b), '==': (lambda a, b: a == b), '!=': (lambda a, b: a != b)}

    # Process each tile against the rules
    for tile in tiles:
        for rule in request.rules_config.rules:
            is_match = evaluate_rule_group(tile, rule.rule_group, ops)
            if is_match:
                # Set color and break to next tile (rule priority)
                index = tile['row'] * grid_width + tile['col']
                heatmap_data[index] = rule.color
                break
    
    return {
        "grid_width": grid_width,
        "grid_height": grid_height,
        "heatmap_data": heatmap_data
    }

# NEW HELPER FUNCTION: This can be placed right after the heatmap endpoint
def evaluate_rule_group(tile: Dict, group: RuleGroup, ops: Dict) -> bool:
    """Evaluates a group of conditions against a tile's data."""
    results = []
    for cond in group.conditions:
        if cond.key in tile and tile[cond.key] is not None:
            tile_val = tile[cond.key]
            op_func = ops.get(cond.op)
            if op_func and op_func(tile_val, cond.value):
                results.append(True)
            else:
                results.append(False)
        else:
            results.append(False) # Key not present or null, condition is false

    if group.logical_op.upper() == "AND":
        return all(results)
    elif group.logical_op.upper() == "OR":
        return any(results)
    return False


# --- (The app.mount line remains at the very bottom) ---
# NEW: We need to tell FastAPI it can serve files from the /config directory
app.mount("/config", StaticFiles(directory="config"), name="config")

# This line tells FastAPI to serve all files from the '../frontend' directory
# when a request is made to the root URL ("/").
# The html=True argument makes it serve index.html for the root path.
app.mount("/", StaticFiles(directory=str(SCRIPT_DIR.parent / "frontend"), html=True), name="static")
