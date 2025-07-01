# backend/main.py

import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import numpy as np
from typing import List, Optional, Any, Dict

## NEW: Import Pydantic's BaseModel to define the request structure
from pydantic import BaseModel

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

   
# --- NEW: Mount the static files directory ---
# This line tells FastAPI to serve all files from the '../frontend' directory
# when a request is made to the root URL ("/").
# The html=True argument makes it serve index.html for the root path.
app.mount("/", StaticFiles(directory=str(SCRIPT_DIR.parent / "frontend"), html=True), name="static")