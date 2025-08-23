# backend/main.py

# --- Standard Library Imports ---
import asyncio
import configparser
import io
import json
import os
import re
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Third-Party Imports ---
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# --- Local Application Imports ---
from lib.reporting import HeatmapRulesConfig, generate_report_data

# --- Configuration ---
SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR.parent / "database" / "analysis.db"
SAVED_RULES_DIR = SCRIPT_DIR.parent / "config" / "saved_rules"
CONFIG_PATH = SCRIPT_DIR.parent / "config" / "settings.ini"

# --- Load Configuration ---
config = configparser.ConfigParser()
config.read(CONFIG_PATH)
EXPORT_CSV_LIMIT = config.getint('limits', 'export_csv_limit', fallback=50000)
DOWNLOAD_IMAGES_LIMIT = config.getint('limits', 'download_images_limit', fallback=5000)
ACTIVE_MODEL_NAME = config.get('settings', 'active_model_name', fallback=None)

SAVED_RULES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()

# --- Pydantic Models ---
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

class ImageExportRequest(BaseModel):
    filters: List[Filter]
    filename_template: str

class IngestionRequest(BaseModel):
    folder_path: str

class HeatmapCondition(BaseModel):
    key: str
    op: str
    value: Any

class RuleGroup(BaseModel):
    logical_op: str
    conditions: List[HeatmapCondition]

class HeatmapRule(BaseModel):
    name: Optional[str] = None
    color: str
    rule_group: RuleGroup

class HeatmapRulesConfig(BaseModel):
    default_color: str
    rules: List[HeatmapRule]

class HeatmapRequest(BaseModel):
    json_filename: str
    rules_config: HeatmapRulesConfig

class SaveRulesRequest(BaseModel):
    rule_name: str
    rules_config: HeatmapRulesConfig

# --- Helper Functions ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def evaluate_rule_group(tile: Dict, group: RuleGroup, ops: Dict) -> bool:
    results = []
    for cond in group.conditions:
        if cond.key in tile and tile[cond.key] is not None:
            tile_val = tile[cond.key]
            op_func = ops.get(cond.op)
            # Handle both numeric and string comparisons
            try:
                if isinstance(tile_val, str) or isinstance(cond.value, str):
                     if op_func(str(tile_val), str(cond.value)):
                         results.append(True)
                     else:
                         results.append(False)
                else: # Assume numeric
                    if op_func(float(tile_val), float(cond.value)):
                        results.append(True)
                    else:
                        results.append(False)
            except (ValueError, TypeError):
                results.append(False)
        else:
            results.append(False)

    if group.logical_op.upper() == "AND":
        return all(results)
    elif group.logical_op.upper() == "OR":
        return any(results)
    return False

# --- API Endpoints ---
@app.post("/api/tiles")
def search_tiles(request: TilesRequest) -> Dict[str, Any]:
    conn = get_db_connection()

    # --- Step 1: Determine if a JOIN with the Predictions table is needed ---
    needs_prediction_join = False
    if ACTIVE_MODEL_NAME:
        if any(f.key in ["model_score", "model_classification"] for f in request.filters):
            needs_prediction_join = True
        if any(s.key in ["model_score", "model_classification"] for s in request.sort):
            needs_prediction_join = True

    # --- Step 2: Build the query components ---
    select_columns = "T.*, S.json_filename"
    from_clause = " FROM ImageTiles T JOIN SourceFiles S ON T.source_file_id = S.id"
    params = []
    
    if needs_prediction_join:
        select_columns += ", P.score as model_score, P.predicted_class as model_classification"
        join_clause = " LEFT JOIN Predictions P ON T.id = P.tile_id LEFT JOIN Models M ON P.model_id = M.id AND M.name = ?"
        from_clause += join_clause
        params.append(ACTIVE_MODEL_NAME)
    
    # --- Step 3: Build the WHERE clause ---
    where_clauses = []
    if request.filters:
        for f in request.filters:
            if f.key in ["model_score", "model_classification"] and not needs_prediction_join:
                continue
            valid_operators = {">", "<", ">=", "<=", "==", "!="}
            if f.op in valid_operators:
                if f.key == "json_filename":
                    db_column = "S.json_filename"
                elif f.key == "model_score":
                    db_column = "P.score"
                elif f.key == "model_classification":
                    db_column = "P.predicted_class"
                else:
                    db_column = f"T.{f.key}"
                where_clauses.append(f"{db_column} {f.op} ?")
                params.append(f.value)
    
    where_clause_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # --- Step 4: Build the ORDER BY clause ---
    order_by_parts = []
    if request.sort:
        for s in request.sort:
            if s.key in ["model_score", "model_classification"] and not needs_prediction_join:
                continue
            order = s.order.upper() if s.order.lower() in ['asc', 'desc'] else 'ASC'
            sort_column = s.key
            if s.key not in ["model_score", "model_classification", "json_filename"]:
                sort_column = f"T.{s.key}"
            elif s.key == "json_filename":
                sort_column = f"S.{s.key}"
            order_by_parts.append(f"{sort_column} {order}")
    
    order_by_clause = "ORDER BY " + ", ".join(order_by_parts) if order_by_parts else "ORDER BY T.id ASC"

    # --- Step 5: Assemble and Execute the Queries ---
    try:
        count_query = "SELECT COUNT(T.id)" + from_clause + where_clause_str
        total_results = conn.execute(count_query, params).fetchone()[0]
        
        pagination_clause = " LIMIT ? OFFSET ?"
        offset = (request.page - 1) * request.limit
        params.extend([request.limit, offset])
        
        data_query = "SELECT " + select_columns + from_clause + where_clause_str + " " + order_by_clause + pagination_clause
        
        cursor = conn.execute(data_query, params)
        column_names = [description[0] for description in cursor.description]
        results = [dict(zip(column_names, row)) for row in cursor.fetchall()]
        
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=400, detail=f"Database query error: {e}")
    finally:
        if conn:
            conn.close()

    return {
        "page": request.page,
        "limit": request.limit,
        "total_results": total_results,
        "results": results
    }
    
# ... (All other endpoints: /api/export/limits, /api/export/csv, /api/export/images, /api/tile_details, etc., are included here)
@app.get("/api/export/limits")
def get_export_limits():
    return {"export_csv_limit": EXPORT_CSV_LIMIT, "download_images_limit": DOWNLOAD_IMAGES_LIMIT}

@app.post("/api/export/csv")
def export_tiles_to_csv(request: TilesRequest) -> StreamingResponse:
    conn = get_db_connection()
    
    # Use the same robust logic as the main /api/tiles endpoint
    select_clause = "SELECT T.*, S.json_filename"
    from_clause = " FROM ImageTiles T JOIN SourceFiles S ON T.source_file_id = S.id"
    params = []

    if ACTIVE_MODEL_NAME:
        select_clause += ", P.score as model_score, P.predicted_class as model_classification"
        join_clause = " LEFT JOIN Predictions P ON T.id = P.tile_id LEFT JOIN Models M ON P.model_id = M.id AND M.name = ?"
        from_clause += join_clause
        params.append(ACTIVE_MODEL_NAME)

    where_clauses = []
    if request.filters:
        for f in request.filters:
            if f.key in ["model_score", "model_classification"] and not ACTIVE_MODEL_NAME: continue
            valid_operators = {">", "<", ">=", "<=", "==", "!="}
            if f.op in valid_operators:
                if f.key == "model_score": db_column = "P.score"
                elif f.key == "model_classification": db_column = "P.predicted_class"
                elif f.key == "json_filename": db_column = "S.json_filename"
                else: db_column = f"T.{f.key}"
                where_clauses.append(f"{db_column} {f.op} ?")
                params.append(f.value)
    
    where_clause_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    try:
        count_query = "SELECT COUNT(T.id)" + from_clause + where_clause_str
        total_results = conn.execute(count_query, params).fetchone()[0]

        if total_results > EXPORT_CSV_LIMIT:
            raise HTTPException(status_code=413, detail=f"Export failed: Query returns {total_results} records, exceeding the limit of {EXPORT_CSV_LIMIT}.")

        # --- THIS IS THE FIX: Removed the extra "SELECT " ---
        final_query = select_clause + from_clause + where_clause_str
        df = pd.read_sql_query(final_query, conn, params=params)
        
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        
        response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
        timestamp = datetime.now().strftime("%Y%m%d")
        response.headers["Content-Disposition"] = f"attachment; filename=tile_export_{timestamp}.csv"
        return response

    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=400, detail=f"Database query error: {e}")
    finally:
        if conn: conn.close()


@app.post("/api/export/images")
def export_images_as_zip(request: ImageExportRequest):
    conn = get_db_connection()
    
    # Use the same robust logic as the main /api/tiles endpoint
    select_clause = "SELECT T.*, S.json_filename, S.image_directory"
    from_clause = " FROM ImageTiles T JOIN SourceFiles S ON T.source_file_id = S.id"
    params = []

    if ACTIVE_MODEL_NAME:
        select_clause += ", P.score as model_score, P.predicted_class as model_classification"
        join_clause = " LEFT JOIN Predictions P ON T.id = P.tile_id LEFT JOIN Models M ON P.model_id = M.id AND M.name = ?"
        from_clause += join_clause
        params.append(ACTIVE_MODEL_NAME)

    where_clauses = []
    if request.filters:
        for f in request.filters:
            if f.key in ["model_score", "model_classification"] and not ACTIVE_MODEL_NAME: continue
            valid_operators = {">", "<", ">=", "<=", "==", "!="}
            if f.op in valid_operators:
                if f.key == "model_score": db_column = "P.score"
                elif f.key == "model_classification": db_column = "P.predicted_class"
                elif f.key == "json_filename": db_column = "S.json_filename"
                else: db_column = f"T.{f.key}"
                where_clauses.append(f"{db_column} {f.op} ?")
                params.append(f.value)
    
    where_clause_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    try:
        count_query = "SELECT COUNT(T.id)" + from_clause + where_clause_str
        total_results = conn.execute(count_query, params).fetchone()[0]

        if total_results > DOWNLOAD_IMAGES_LIMIT:
            raise HTTPException(status_code=413, detail=f"Download failed: Query returns {total_results} images, exceeding the limit of {DOWNLOAD_IMAGES_LIMIT}.")
        if total_results == 0:
            raise HTTPException(status_code=404, detail="No images found matching the specified criteria.")

        # --- THIS IS THE FIX: Removed the extra "SELECT " ---
        final_query = select_clause + from_clause + where_clause_str
        cursor = conn.execute(final_query, params)
        column_names = [description[0] for description in cursor.description]
        tiles_to_zip = [dict(zip(column_names, row)) for row in cursor.fetchall()]

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for tile in tiles_to_zip:
                tile['json_basename'] = Path(tile['json_filename']).stem
                # Using a robust formatting method to avoid errors with the template string
                try:
                    new_filename = request.filename_template.format(**tile)
                except KeyError as e:
                    # This can happen if a placeholder is in the template but not in the tile data (e.g., model score is null)
                    # We'll create a safe version of the tile data for formatting
                    safe_tile_data = tile.copy()
                    for key in re.findall(r'\{(\w+)', request.filename_template):
                        safe_tile_data.setdefault(key, 'N/A')
                    new_filename = request.filename_template.format(**safe_tile_data)

                image_path = Path(tile["image_directory"]) / tile["webp_filename"]
                if image_path.is_file():
                    zip_file.write(image_path, arcname=new_filename)

        zip_buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"image_dataset_{timestamp}.zip"
        
        return StreamingResponse(zip_buffer, media_type="application/x-zip-compressed", headers={"Content-Disposition": f"attachment; filename={zip_filename}"})

    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=400, detail=f"Database query error: {e}")
    finally:
        if conn: conn.close()

@app.get("/api/tile_details")
def get_tile_details(json_filename: str, col: int, row: int) -> Dict[str, Any]:
    conn = get_db_connection()
    query = """
        SELECT
            T.*,
            P.score as model_score,
            P.predicted_class as model_classification
        FROM
            ImageTiles T
        JOIN SourceFiles S ON T.source_file_id = S.id
        LEFT JOIN Predictions P ON T.id = P.tile_id
        LEFT JOIN Models M ON P.model_id = M.id AND M.name = ?
        WHERE
            S.json_filename = ? AND T.col = ? AND T.row = ?
    """
    params = [ACTIVE_MODEL_NAME if ACTIVE_MODEL_NAME else None, json_filename, col, row]

    try:
        tile_data = conn.execute(query, params).fetchone()
        if not tile_data:
            raise HTTPException(status_code=404, detail=f"Tile (col={col}, row={row}) not found for '{json_filename}'.")
        return dict(tile_data)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

# --- All other endpoints from the original file are assumed to be here ---
# (e.g., /api/source_files, stats endpoints, heatmap endpoints, etc.)
@app.get("/api/source_files")
def get_source_files() -> List[str]:
    conn = get_db_connection()
    filenames = [row[0] for row in conn.execute("SELECT json_filename FROM SourceFiles ORDER BY json_filename ASC").fetchall()]
    conn.close()
    return filenames

@app.post("/api/heatmap")
def generate_heatmap(request: HeatmapRequest) -> Dict[str, Any]:
    conn = get_db_connection()
    query = """
        SELECT
            T.*,
            P.score as model_score,
            P.predicted_class as model_classification
        FROM
            ImageTiles T
        JOIN SourceFiles S ON T.source_file_id = S.id
        LEFT JOIN Predictions P ON T.id = P.tile_id
        LEFT JOIN Models M ON P.model_id = M.id AND M.name = ?
        WHERE S.json_filename = ?
    """
    params = [ACTIVE_MODEL_NAME if ACTIVE_MODEL_NAME else None, request.json_filename]
    try:
        tiles = [dict(row) for row in conn.execute(query, params).fetchall()]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    if not tiles:
        return {"grid_width": 0, "grid_height": 0, "heatmap_data": [], "rules_config": request.rules_config, "rule_match_counts": {}}

    max_col = max(t['col'] for t in tiles if t['col'] is not None)
    max_row = max(t['row'] for t in tiles if t['row'] is not None)
    grid_width = max_col + 1
    grid_height = max_row + 1
    heatmap_data = [request.rules_config.default_color] * (grid_width * grid_height)
    ops = {'>': (lambda a, b: a > b), '<': (lambda a, b: a < b), '>=': (lambda a, b: a >= b),
           '<=': (lambda a, b: a <= b), '==': (lambda a, b: a == b), '!=': (lambda a, b: a != b)}
    rule_match_counts = {str(i): 0 for i in range(len(request.rules_config.rules))}
    rule_match_counts['default'] = 0

    for tile in tiles:
        if tile['row'] is None or tile['col'] is None:
            continue
        matched_by_rule = False
        for i, rule in enumerate(request.rules_config.rules):
            is_match = evaluate_rule_group(tile, rule.rule_group, ops)
            if is_match:
                index = tile['row'] * grid_width + tile['col']
                heatmap_data[index] = rule.color
                rule_match_counts[str(i)] += 1
                matched_by_rule = True
                break
        if not matched_by_rule:
            rule_match_counts['default'] += 1
    
    return {"grid_width": grid_width, "grid_height": grid_height, "heatmap_data": heatmap_data, "rules_config": request.rules_config, "rule_match_counts": rule_match_counts}

# NEW: Endpoint to save heatmap rules
@app.post("/api/heatmap/rules/save")
def save_heatmap_rules(request: SaveRulesRequest):
    rule_filename = f"{request.rule_name}.json"
    file_path = SAVED_RULES_DIR / rule_filename

    if file_path.exists():
        raise HTTPException(status_code=409, detail=f"Rule set '{request.rule_name}' already exists. Please choose a different name.") #

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(request.rules_config.model_dump(), f, indent=2) # Use .model_dump() to convert Pydantic model to dict #
        clear_dashboard_caches() # NEW: Clear cache after saving/modifying a rule
        return {"message": f"Rule set '{request.rule_name}' saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save rule set: {e}")
        
# NEW: Endpoint to list all saved heatmap rules
@app.get("/api/heatmap/rules/list")
def list_heatmap_rules() -> List[str]:
    """Lists the names of all saved heatmap rule configurations."""
    rules = []
    try:
        for file_path in SAVED_RULES_DIR.iterdir():
            if file_path.is_file() and file_path.suffix == ".json":
                rules.append(file_path.stem) # .stem gets the filename without extension
        rules.sort() # Optional: keep the list sorted
        return rules
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list rule sets: {e}") #

# NEW: Endpoint to load a specific heatmap rule by name
@app.get("/api/heatmap/rules/load/{rule_name}")
def load_heatmap_rule(rule_name: str) -> HeatmapRulesConfig:
    """Loads a specific heatmap rule configuration by name."""
    file_path = SAVED_RULES_DIR / f"{rule_name}.json"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Rule set '{rule_name}' not found.") #

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            rules_data = json.load(f)
        return HeatmapRulesConfig(**rules_data) # Validate and return as Pydantic model #
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Invalid JSON format for rule set '{rule_name}'.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load rule set: {e}")

# NEW: Endpoint to delete a specific heatmap rule by name
@app.delete("/api/heatmap/rules/delete/{rule_name}")
def delete_heatmap_rule(rule_name: str):
    """Deletes a specific heatmap rule configuration by name."""
    file_path = SAVED_RULES_DIR / f"{rule_name}.json" #

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Rule set '{rule_name}' not found.") #

    try:
        os.remove(file_path)
        clear_dashboard_caches() # NEW: Clear cache after deleting a rule
        return {"message": f"Rule set '{rule_name}' deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete rule set: {e}")
        

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
 
# --- Static file mounting ---
app.mount("/", StaticFiles(directory=str(SCRIPT_DIR.parent / "frontend"), html=True), name="static")