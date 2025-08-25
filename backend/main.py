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

# --- Pydantic Models (Consolidated) ---
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
            try:
                if isinstance(tile_val, str) or isinstance(cond.value, str):
                     if op_func(str(tile_val), str(cond.value)): results.append(True)
                     else: results.append(False)
                else:
                    if op_func(float(tile_val), float(cond.value)): results.append(True)
                    else: results.append(False)
            except (ValueError, TypeError): results.append(False)
        else: results.append(False)
    if group.logical_op.upper() == "AND": return all(results)
    elif group.logical_op.upper() == "OR": return any(results)
    return False

# --- Core Query Logic (Centralized and Simplified) ---
def build_query_and_params(request_filters: List[Filter], request_sort: List[Sort] = [], select_extra_cols: str = ""):
    select_clause = f"SELECT T.*, S.json_filename{select_extra_cols}"
    from_clause = " FROM ImageTiles T JOIN SourceFiles S ON T.source_file_id = S.id"
    params = []

    if ACTIVE_MODEL_NAME:
        select_clause += ", P.score as model_score, P.predicted_class as model_classification"
        join_clause = " LEFT JOIN Predictions P ON T.id = P.tile_id LEFT JOIN Models M ON P.model_id = M.id AND M.name = ?"
        from_clause += join_clause
        params.append(ACTIVE_MODEL_NAME)

    where_clauses = []
    if request_filters:
        for f in request_filters:
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

    order_by_parts = []
    if request_sort:
        for s in request_sort:
            order = s.order.upper() if s.order.lower() in ['asc', 'desc'] else 'ASC'
            sort_column = s.key
            if s.key not in ["model_score", "model_classification", "json_filename"]: sort_column = f"T.{s.key}"
            elif s.key == "json_filename": sort_column = f"S.{s.key}"
            order_by_parts.append(f"{sort_column} {order}")
    
    order_by_clause = "ORDER BY " + ", ".join(order_by_parts) if order_by_parts else "ORDER BY T.id ASC"

    return select_clause, from_clause, where_clause_str, order_by_clause, params

# --- API Endpoints ---
@app.post("/api/tiles")
def search_tiles(request: TilesRequest) -> Dict[str, Any]:
    conn = get_db_connection()
    select, from_c, where_c, order_by_c, params = build_query_and_params(request.filters, request.sort)
    try:
        count_query = "SELECT COUNT(T.id)" + from_c + where_c
        total_results = conn.execute(count_query, params).fetchone()[0]
        
        pagination_clause = " LIMIT ? OFFSET ?"
        offset = (request.page - 1) * request.limit
        final_params = params + [request.limit, offset]
        
        data_query = select + from_c + where_c + " " + order_by_c + pagination_clause
        
        cursor = conn.execute(data_query, final_params)
        column_names = [description[0] for description in cursor.description]
        results = [dict(zip(column_names, row)) for row in cursor.fetchall()]
        
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=400, detail=f"Database query error: {e}")
    finally:
        if conn: conn.close()
    return {"page": request.page, "limit": request.limit, "total_results": total_results, "results": results}

@app.get("/api/export/limits")
def get_export_limits():
    return {"export_csv_limit": EXPORT_CSV_LIMIT, "download_images_limit": DOWNLOAD_IMAGES_LIMIT}

@app.post("/api/export/csv")
def export_tiles_to_csv(request: TilesRequest) -> StreamingResponse:
    conn = get_db_connection()
    select, from_c, where_c, _, params = build_query_and_params(request.filters, request.sort)
    try:
        count_query = "SELECT COUNT(T.id)" + from_c + where_c
        total_results = conn.execute(count_query, params).fetchone()[0]
        if total_results > EXPORT_CSV_LIMIT:
            raise HTTPException(status_code=413, detail=f"Export failed: Query returns {total_results} records, exceeding limit.")
        
        final_query = select + from_c + where_c
        df = pd.read_sql_query(final_query, conn, params=params)
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=tile_export_{datetime.now().strftime('%Y%m%d')}.csv"
        return response
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=400, detail=f"Database query error: {e}")
    finally:
        if conn: conn.close()

@app.post("/api/export/images")
def export_images_as_zip(request: ImageExportRequest):
    conn = get_db_connection()
    select, from_c, where_c, _, params = build_query_and_params(request.filters, [], ", S.image_directory")
    try:
        count_query = "SELECT COUNT(T.id)" + from_c + where_c
        total_results = conn.execute(count_query, params).fetchone()[0]
        if total_results > DOWNLOAD_IMAGES_LIMIT:
            raise HTTPException(status_code=413, detail=f"Download failed: Query returns {total_results} images, exceeding limit.")
        if total_results == 0:
            raise HTTPException(status_code=404, detail="No images found matching criteria.")

        data_query = select + from_c + where_c
        cursor = conn.execute(data_query, params)
        column_names = [desc[0] for desc in cursor.description]
        tiles_to_zip = [dict(zip(column_names, row)) for row in cursor.fetchall()]
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
            for tile in tiles_to_zip:
                tile['json_basename'] = Path(tile['json_filename']).stem
                try:
                    safe_tile = tile.copy()
                    for key in re.findall(r'\{(\w+)', request.filename_template): safe_tile.setdefault(key, 'N/A')
                    new_filename = request.filename_template.format(**safe_tile)
                except Exception: new_filename = f"error-in-template-{tile['webp_filename']}"
                
                image_path = Path(tile["image_directory"]) / tile["webp_filename"]
                if image_path.is_file(): zf.write(image_path, arcname=new_filename)

        zip_buffer.seek(0)
        zip_filename = f"image_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        return StreamingResponse(zip_buffer, media_type="application/x-zip-compressed", headers={"Content-Disposition": f"attachment; filename={zip_filename}"})
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=400, detail=f"Database query error: {e}")
    finally:
        if conn: conn.close()

@app.get("/api/tile_details")
def get_tile_details(json_filename: str, col: int, row: int) -> Dict[str, Any]:
    conn = get_db_connection()
    query = """
        SELECT T.*, P.score as model_score, P.predicted_class as model_classification
        FROM ImageTiles T
        JOIN SourceFiles S ON T.source_file_id = S.id
        LEFT JOIN Predictions P ON T.id = P.tile_id
        LEFT JOIN Models M ON P.model_id = M.id AND M.name = ?
        WHERE S.json_filename = ? AND T.col = ? AND T.row = ?
    """
    params = [ACTIVE_MODEL_NAME if ACTIVE_MODEL_NAME else None, json_filename, col, row]
    try:
        tile_data = conn.execute(query, params).fetchone()
        if not tile_data:
            raise HTTPException(status_code=404, detail=f"Tile (col={col}, row={row}) not found.")
        return dict(tile_data)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

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
        SELECT T.*, P.score as model_score, P.predicted_class as model_classification
        FROM ImageTiles T
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
    max_col = max((t['col'] for t in tiles if t['col'] is not None), default=0)
    max_row = max((t['row'] for t in tiles if t['row'] is not None), default=0)
    grid_width = max_col + 1
    grid_height = max_row + 1
    heatmap_data = [request.rules_config.default_color] * (grid_width * grid_height)
    ops = {'>': (lambda a, b: a > b), '<': (lambda a, b: a < b), '>=': (lambda a, b: a >= b),
           '<=': (lambda a, b: a <= b), '==': (lambda a, b: a == b), '!=': (lambda a, b: a != b)}
    rule_match_counts = {str(i): 0 for i in range(len(request.rules_config.rules))}
    rule_match_counts['default'] = 0
    for tile in tiles:
        if tile['row'] is None or tile['col'] is None: continue
        matched_by_rule = False
        for i, rule in enumerate(request.rules_config.rules):
            if evaluate_rule_group(tile, rule.rule_group, ops):
                index = tile['row'] * grid_width + tile['col']
                heatmap_data[index] = rule.color
                rule_match_counts[str(i)] += 1
                matched_by_rule = True
                break
        if not matched_by_rule:
            rule_match_counts['default'] += 1
    return {"grid_width": grid_width, "grid_height": grid_height, "heatmap_data": heatmap_data, "rules_config": request.rules_config, "rule_match_counts": rule_match_counts}

@app.post("/api/heatmap/rules/save")
def save_heatmap_rules(request: SaveRulesRequest):
    rule_filename = f"{request.rule_name}.json"
    file_path = SAVED_RULES_DIR / rule_filename
    if file_path.exists():
        raise HTTPException(status_code=409, detail=f"Rule set '{request.rule_name}' already exists.")
    try:
        with open(file_path, "w", encoding="utf-8") as f: json.dump(request.rules_config.model_dump(), f, indent=2)
        return {"message": f"Rule set '{request.rule_name}' saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save rule set: {e}")

@app.get("/api/heatmap/rules/list")
def list_heatmap_rules() -> List[str]:
    try:
        return sorted([p.stem for p in SAVED_RULES_DIR.iterdir() if p.suffix == ".json"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list rule sets: {e}")

@app.get("/api/heatmap/rules/load/{rule_name}")
def load_heatmap_rule(rule_name: str) -> HeatmapRulesConfig:
    file_path = SAVED_RULES_DIR / f"{rule_name}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Rule set '{rule_name}' not found.")
    try:
        with open(file_path, "r", encoding="utf-8") as f: data = json.load(f)
        return HeatmapRulesConfig(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load rule set '{rule_name}': {e}")

@app.delete("/api/heatmap/rules/delete/{rule_name}")
def delete_heatmap_rule(rule_name: str):
    file_path = SAVED_RULES_DIR / f"{rule_name}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Rule set '{rule_name}' not found.")
    try:
        os.remove(file_path)
        return {"message": f"Rule set '{rule_name}' deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete rule set: {e}")
        
@app.get("/images/{source_id}/{webp_filename}")
def get_image(source_id: int, webp_filename: str):
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT image_directory FROM SourceFiles WHERE id = ?", (source_id,))
        record = cursor.fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="Source file ID not found.")
        
        image_path = Path(record["image_directory"]) / webp_filename
        if not image_path.is_file():
            raise HTTPException(status_code=404, detail=f"Image file not found at: {image_path}")
            
        return FileResponse(image_path)
    finally:
        if conn: conn.close()
        
# Static file mounting
app.mount("/", StaticFiles(directory=str(SCRIPT_DIR.parent / "frontend"), html=True), name="static")