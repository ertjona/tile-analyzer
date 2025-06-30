# backend/main.py

import sqlite3
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse # <--- IMPORT THIS
from fastapi.staticfiles import StaticFiles
from typing import List, Optional, Dict, Any
from pathlib import Path

# --- Configuration ---
SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR.parent / "database" / "analysis.db"

app = FastAPI()


# --- Helper Functions ---

def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DB_PATH)
    # This allows you to access columns by name
    conn.row_factory = sqlite3.Row 
    return conn

# --- API Endpoint ---

@app.get("/api/tiles")
def get_tiles(
    # ... (all your existing parameters are correct) ...
    filter_key: Optional[str] = None,
    filter_op: Optional[str] = None,
    filter_value: Optional[str] = None,
    sort: Optional[str] = Query(None, description="Sort order, e.g., 'edge_density:desc,entropy:asc'"),
    page: int = 1,
    limit: int = 50
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()

    base_query = "SELECT * FROM ImageTiles"
    count_query = "SELECT COUNT(*) FROM ImageTiles" # <-- NEW: Query to get the total count
    where_clauses = []
    params = []

    if filter_key and filter_op and filter_value:
        valid_operators = {">", "<", ">=", "<=", "==", "!="}
        if filter_op in valid_operators:
            where_clauses.append(f"{filter_key} {filter_op} ?")
            params.append(filter_value)
        else:
            raise HTTPException(status_code=400, detail="Invalid filter operator.")

    order_by_clause = "ORDER BY id"
    if sort:
        sort_parts = []
        for part in sort.split(','):
            key, __, order = part.partition(':')
            order = order.upper() if order in ['asc', 'desc'] else 'ASC'
            sort_parts.append(f"{key} {order}")
        if sort_parts:
            order_by_clause = "ORDER BY " + ", ".join(sort_parts)

    pagination_clause = "LIMIT ? OFFSET ?"
    offset = (page - 1) * limit
    
    # Build the full query for fetching data
    if where_clauses:
        final_query = f"{base_query} WHERE {' AND '.join(where_clauses)} {order_by_clause} {pagination_clause}"
        count_query = f"{count_query} WHERE {' AND '.join(where_clauses)}"
    else:
        final_query = f"{base_query} {order_by_clause} {pagination_clause}"

    try:
        # --- NEW: Execute the count query first ---
        # Note: The parameters for the count query do not include limit/offset
        cursor.execute(count_query, params)
        total_results = cursor.fetchone()[0]

        # --- Execute the main data query ---
        cursor.execute(final_query, params + [limit, offset])
        tiles = cursor.fetchall()
        results = [dict(row) for row in tiles]
        
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=400, detail=f"Database query error: {e}")
    finally:
        conn.close()

    # --- NEW: Return the total_results in the response ---
    return {"page": page, "limit": limit, "total_results": total_results, "results": results}

# --- NEW: Endpoint to serve a single image file ---
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
   
# --- NEW: Mount the static files directory ---
# This line tells FastAPI to serve all files from the '../frontend' directory
# when a request is made to the root URL ("/").
# The html=True argument makes it serve index.html for the root path.
app.mount("/", StaticFiles(directory=str(SCRIPT_DIR.parent / "frontend"), html=True), name="static")