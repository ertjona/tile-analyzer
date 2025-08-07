# backend/main.py

import sqlite3
from fastapi import FastAPI, Request, HTTPException # <--- ADD HTTPException here
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

# NEW: Directory for saved heatmap rules
SAVED_RULES_DIR = SCRIPT_DIR.parent / "config" / "saved_rules" #

# Ensure the directory exists
SAVED_RULES_DIR.mkdir(parents=True, exist_ok=True) #

# backend/main.py

# ... (existing imports, ensure HTTPException is imported) ...

# NEW: In-memory caches for dashboard statistics
_distribution_cache = {} # <--- ENSURE THIS IS DEFINED GLOBALLY
_aggregate_rules_cache = {}
_per_image_rule_report_cache = {}

# NEW: Function to clear relevant caches (ensure this function is present)
def clear_dashboard_caches():
    _distribution_cache.clear()
    _aggregate_rules_cache.clear()
    _per_image_rule_report_cache.clear()
    print("Dashboard caches cleared.")

app = FastAPI()

# ... (rest of your app definition and other endpoints) ...


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

# backend/main.py

# ... (existing imports, ensure HTTPException, Dict, Any are imported from fastapi and typing) ...
# from fastapi import FastAPI, Request, HTTPException
# from typing import List, Optional, Any, Dict
# ...

# --- NEW: Endpoint to get details for a specific image tile ---
@app.get("/api/tile_details")
def get_tile_details(json_filename: str, col: int, row: int) -> Dict[str, Any]:
    """
    Retrieves the full metadata for a specific image tile based on its source JSON filename, column, and row.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # First, find the source_file_id from the json_filename
        cursor.execute("SELECT id FROM SourceFiles WHERE json_filename = ?", (json_filename,))
        source_file_record = cursor.fetchone()

        if not source_file_record:
            raise HTTPException(status_code=404, detail=f"Source file '{json_filename}' not found.")
        
        source_file_id = source_file_record['id']

        # Now, query ImageTiles using source_file_id, col, and row
        query = """
            SELECT * FROM ImageTiles
            WHERE source_file_id = ? AND col = ? AND row = ?
        """
        cursor.execute(query, (source_file_id, col, row))
        tile = cursor.fetchone()

        if not tile:
            raise HTTPException(status_code=404, detail=f"Tile (col={col}, row={row}) not found for '{json_filename}'.")
        
        return dict(tile) # Return as a dictionary
        
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()
    
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

# backend/main.py

# ... (your existing get_summary_stats endpoint) ...

# --- MODIFIED: Endpoint for detailed distribution stats of a column (with caching) ---
@app.get("/api/stats/distribution/{column_name}") # <--- ENSURE THIS DECORATOR IS CORRECT
def get_distribution_stats(column_name: str):
    """
    Calculates and returns descriptive statistics for a given numeric column.
    Results are cached.
    """
    # Validate column name to prevent SQL injection
    # MODIFIED: Expanded allowed_columns based on scripts/measure_med_tiles.py
    allowed_columns = ["laplacian", "avg_brightness", "avg_saturation", "entropy", "edge_density", "size", "foreground_ratio", "max_subject_area"]
    if column_name not in allowed_columns:
        raise HTTPException(status_code=400, detail="Invalid column name for statistics.")

    # NEW: Check cache first
    if column_name in _distribution_cache:
        print(f"Serving {column_name} distribution from cache.")
        return _distribution_cache[column_name]

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch all non-null values from the column
    query = f"SELECT {column_name} FROM ImageTiles WHERE {column_name} IS NOT NULL"
    values = [row[0] for row in cursor.execute(query).fetchall()]
    conn.close()
    
    if not values:
        result = {"column": column_name, "count": 0}
        _distribution_cache[column_name] = result # Cache empty result
        return result

    # Use NumPy to calculate statistics
    np_values = np.array(values)
    
    result = {
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
    
    _distribution_cache[column_name] = result # NEW: Store in cache
    print(f"Calculated and cached {column_name} distribution.")
    return result

# backend/main.py

# ... (your existing get_aggregate_heatmap_rules endpoint) ...

# --- MODIFIED: Endpoint to get aggregate rule match statistics (with caching) ---
@app.get("/api/stats/aggregate_heatmap_rules/{rule_name}")
def get_aggregate_heatmap_rules(rule_name: str) -> Dict[str, Any]:
    """
    Calculates aggregate rule match statistics for a given rule set
    across all image tiles in the database. Results are cached.
    """
    # NEW: Check cache first
    if rule_name in _aggregate_rules_cache:
        print(f"Serving aggregate rules for '{rule_name}' from cache.")
        return _aggregate_rules_cache[rule_name]

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        rules_config_model = load_heatmap_rule(rule_name)
        rules_config = rules_config_model.dict() 

        # Get ALL tiles from the database
        query = "SELECT T.* FROM ImageTiles T"
        all_tiles = [dict(row) for row in cursor.execute(query).fetchall()]

        if not all_tiles:
            result = {"rule_match_counts": {}, "total_tiles_evaluated": 0, "rules_config": rules_config}
            _aggregate_rules_cache[rule_name] = result # Cache empty result
            print(f"Calculated and cached (empty) aggregate rules for '{rule_name}'.")
            return result

        # Dictionary of operators for easy lookup (copied from generate_heatmap)
        ops = {'>': (lambda a, b: a > b), '<': (lambda a, b: a < b), '>=': (lambda a, b: a >= b),
               '<=': (lambda a, b: a <= b), '==': (lambda a, b: a == b), '!=': (lambda a, b: a != b)}

        # Initialize aggregate rule match counters
        aggregate_rule_match_counts = {str(i): 0 for i in range(len(rules_config['rules']))}
        aggregate_rule_match_counts['default'] = 0

        # Process each tile against the loaded rules
        for tile in all_tiles:
            matched_by_rule = False
            for i, rule in enumerate(rules_config['rules']):
                # Ensure rule['rule_group'] is passed correctly as RuleGroup model
                is_match = evaluate_rule_group(tile, RuleGroup(**rule['rule_group']), ops)
                if is_match:
                    aggregate_rule_match_counts[str(i)] += 1
                    matched_by_rule = True
                    break
            
            if not matched_by_rule:
                aggregate_rule_match_counts['default'] += 1

        result = {
            "rule_match_counts": aggregate_rule_match_counts,
            "total_tiles_evaluated": len(all_tiles),
            "rules_config": rules_config
        }

        _aggregate_rules_cache[rule_name] = result # Store in cache
        print(f"Calculated and cached aggregate rules for '{rule_name}'.")
        return result

    except HTTPException:
        raise # Re-raise if load_heatmap_rule already raised it
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get aggregate heatmap rules: {e}")
    finally:
        conn.close()

# ... (rest of your backend/main.py code below this section) ...

# ... (your existing get_aggregate_heatmap_rules endpoint) ...

# NEW: In-memory cache for per-image rule reports
_per_image_rule_report_cache = {}

# In main.py

# --- ACTION: Replace the entire "get_per_image_rule_report" function with this ---

@app.get("/api/stats/per_image_rule_report/{rule_name}")
def get_per_image_rule_report(rule_name: str) -> Dict[str, Any]:
    """
    Generates a report with correct, non-overlapping rule counts by replicating
    prioritized rule logic directly in the database. (Version 4 - Correct Logic)
    """
    if rule_name in _per_image_rule_report_cache:
        print(f"Serving per-image rule report for '{rule_name}' from cache.")
        return _per_image_rule_report_cache[rule_name]

    try:
        rules_config_model = load_heatmap_rule(rule_name)
    except HTTPException:
        raise

    rules_config = rules_config_model.dict()
    
    VALID_COLUMNS = {
        "status", "col", "row", "size", "laplacian", "avg_brightness",
        "avg_saturation", "entropy", "edge_density", "edge_density_3060",
        "foreground_ratio", "max_subject_area"
    }

    # --- FIX: Build a single, prioritized CASE statement ---
    when_clauses = []
    for i, rule in enumerate(rules_config['rules']):
        conditions = []
        for cond in rule['rule_group']['conditions']:
            if cond['key'] in VALID_COLUMNS and cond['op'] in {'>', '<', '>=', '<=', '==', '!='}:
                value = cond['value']
                sql_value = f"'{value}'" if isinstance(value, str) else value
                conditions.append(f"(T.{cond['key']} {cond['op']} {sql_value})")

        if conditions:
            logical_op = " AND " if rule['rule_group']['logical_op'].upper() == "AND" else " OR "
            full_condition = logical_op.join(conditions)
            # This creates "WHEN (condition) THEN 'rule_0'"
            when_clauses.append(f"WHEN {full_condition} THEN '{i}'")

    # The final CASE statement finds the first matching rule for each tile
    if when_clauses:
        case_statement = f"CASE {' '.join(when_clauses)} ELSE 'default' END"
    else:
        # If no rules are valid, every tile is 'default'
        case_statement = "'default'"

    query = f"""
        SELECT
            S.json_filename,
            {case_statement} AS matched_rule_index,
            COUNT(T.id) as count
        FROM ImageTiles T
        JOIN SourceFiles S ON T.source_file_id = S.id
        GROUP BY S.json_filename, matched_rule_index
        ORDER BY S.json_filename;
    """

    conn = get_db_connection()
    try:
        results = conn.execute(query).fetchall()
        
        # --- FIX: Process the new query result format ---
        # The results are now pre-grouped by the database, e.g., ('file1.json', 'rule_0', 50)
        
        # Intermediate structure to hold aggregated data
        report_agg = {}

        # Get total tile counts for each file first
        total_counts = {}
        for row in conn.execute("SELECT S.json_filename, COUNT(T.id) FROM ImageTiles T JOIN SourceFiles S ON T.source_file_id = S.id GROUP BY S.json_filename"):
            total_counts[row['json_filename']] = row[1]

        # Initialize report for all files, even those with no matches
        for filename in total_counts.keys():
            report_agg[filename] = {str(i): 0 for i in range(len(rules_config['rules']))}
            report_agg[filename]['default'] = 0

        # Populate the aggregation with actual counts from the database
        for row in results:
            filename = row['json_filename']
            rule_index = str(row['matched_rule_index'])
            count = row['count']
            if filename in report_agg:
                report_agg[filename][rule_index] = count
        
        # Now, format the aggregated data into the final JSON structure
        report_data = []
        for filename, counts in report_agg.items():
            total_tiles = total_counts.get(filename, 0)
            
            # Calculate the default count correctly
            matched_sum = sum(v for k, v in counts.items() if k != 'default')
            counts['default'] = total_tiles - matched_sum

            rule_details = []
            for rule_index, count in counts.items():
                percentage = (count / total_tiles * 100) if total_tiles > 0 else 0
                rule_details.append({"rule_index": rule_index, "count": count, "percentage": percentage})

            report_data.append({
                "json_filename": filename,
                "total_tiles_evaluated_for_file": total_tiles,
                "rule_match_details": sorted(rule_details, key=lambda x: str(x['rule_index'])) # Sort for consistent order
            })
        
        final_result = {"report_data": sorted(report_data, key=lambda x: x['json_filename']), "rules_config": rules_config}
        _per_image_rule_report_cache[rule_name] = final_result
        return final_result

    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")
    finally:
        conn.close()

# backend/main.py

# ... (existing cache variables, e.g., _distribution_cache, _aggregate_rules_cache) ...

# NEW: In-memory cache for per-image rule reports
_per_image_rule_report_cache = {} # Ensure this line is present if it wasn't before

# NEW: Function to clear relevant caches
def clear_dashboard_caches():
    _distribution_cache.clear()
    _aggregate_rules_cache.clear()
    _per_image_rule_report_cache.clear() # NEW: Clear this cache too
    print("Dashboard caches cleared.")

# ... (rest of your backend/main.py code) ...

# NEW: Define Pydantic models for the heatmap request
class HeatmapCondition(BaseModel):
    key: str
    op: str
    value: Any

class RuleGroup(BaseModel):
    logical_op: str
    conditions: List[HeatmapCondition]

class HeatmapRule(BaseModel):
    name: Optional[str] = None # NEW: Optional meaningful name for the rule
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
    rules_config: HeatmapRulesConfig #

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
        # MODIFIED: Return empty counts if no tiles
        return {
            "grid_width": 0,
            "grid_height": 0,
            "heatmap_data": [],
            "rules_config": request.rules_config,
            "rule_match_counts": {} # NEW
        }


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

    # NEW: Initialize rule match counters
    rule_match_counts = {str(i): 0 for i in range(len(request.rules_config.rules))} # For indexed rules
    rule_match_counts['default'] = 0 # For default unmatched tiles

    # Process each tile against the rules
    for tile in tiles:
        matched_by_rule = False
        for i, rule in enumerate(request.rules_config.rules): # Enumerate to get index
            is_match = evaluate_rule_group(tile, rule.rule_group, ops)
            if is_match:
                index = tile['row'] * grid_width + tile['col']
                heatmap_data[index] = rule.color
                rule_match_counts[str(i)] += 1 # Increment counter for this rule
                matched_by_rule = True
                break # Break to next tile (rule priority)
        
        if not matched_by_rule:
            rule_match_counts['default'] += 1 # Increment default counter if no rule matched
    
    return {
        "grid_width": grid_width,
        "grid_height": grid_height,
        "heatmap_data": heatmap_data,
        "rules_config": request.rules_config,
        "rule_match_counts": rule_match_counts # NEW: Include counts in response
    }


# NEW: Endpoint to save heatmap rules
@app.post("/api/heatmap/rules/save")
def save_heatmap_rules(request: SaveRulesRequest):
    rule_filename = f"{request.rule_name}.json"
    file_path = SAVED_RULES_DIR / rule_filename

    if file_path.exists():
        raise HTTPException(status_code=409, detail=f"Rule set '{request.rule_name}' already exists. Please choose a different name.") #

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(request.rules_config.dict(), f, indent=2) # Use .dict() to convert Pydantic model to dict #
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
