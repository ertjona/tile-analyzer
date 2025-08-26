# lib/reporting.py

import sqlite3
from typing import List, Optional, Any, Dict
from pydantic import BaseModel

# --- 1. Pydantic Models for Rule Validation ---
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

# --- 2. The Core Report Generation Function ---
# --- CORRECTED Core Report Generation Function ---
def generate_report_data(db_conn: sqlite3.Connection, rules_config: Dict) -> List[Dict]:
    """
    Generates a report with correct, non-overlapping rule counts.
    This is the core logic, callable from any script.
    """
    # --- THIS IS THE FIX: Added model-related columns ---
    VALID_COLUMNS = {
        "status", "col", "row", "size", "laplacian", "avg_brightness",
        "avg_saturation", "entropy", "edge_density", "edge_density_3060",
        "foreground_ratio", "max_subject_area",
        "model_score", "model_classification"
    }
    
    # --- THIS IS THE FIX: Logic to conditionally join predictions table ---
    needs_prediction_join = any(
        cond['key'] in ["model_score", "model_classification"]
        for rule in rules_config['rules']
        for cond in rule['rule_group']['conditions']
    )

    from_clause = " FROM ImageTiles T JOIN SourceFiles S ON T.source_file_id = S.id"
    params = []
    
    # Get active model name directly from the database if a join is needed
    if needs_prediction_join:
        # This assumes the last registered model is the one intended for reporting,
        # or you can modify to fetch a specific one.
        model_record = db_conn.execute("SELECT name FROM Models ORDER BY id DESC LIMIT 1").fetchone()
        if model_record:
            active_model_name = model_record['name']
            join_clause = " LEFT JOIN Predictions P ON T.id = P.tile_id LEFT JOIN Models M ON P.model_id = M.id AND M.name = ?"
            from_clause += join_clause
            params.append(active_model_name)
        else:
            needs_prediction_join = False # No models registered, cannot join.

    # Build a single, prioritized CASE statement for the SQL query
    when_clauses = []
    for i, rule in enumerate(rules_config['rules']):
        conditions = []
        for cond in rule['rule_group']['conditions']:
            if cond['key'] in VALID_COLUMNS and cond['op'] in {'>', '<', '>=', '<=', '==', '!='}:
                value = cond['value']
                
                # --- THIS IS THE FIX: Map to correct DB columns ---
                if cond['key'] == "model_score": db_column = "P.score"
                elif cond['key'] == "model_classification": db_column = "P.predicted_class"
                else: db_column = f"T.{cond['key']}"

                sql_value = f"'{value}'" if isinstance(value, str) else value
                conditions.append(f"({db_column} {cond['op']} {sql_value})")

        if conditions:
            logical_op = " AND " if rule['rule_group']['logical_op'].upper() == "AND" else " OR "
            full_condition = logical_op.join(conditions)
            when_clauses.append(f"WHEN {full_condition} THEN '{i}'")

    case_statement = f"CASE {' '.join(when_clauses)} ELSE 'default' END" if when_clauses else "'default'"

    query = f"""
        SELECT
            S.json_filename,
            {case_statement} AS matched_rule_index,
            COUNT(T.id) as count
        {from_clause}
        GROUP BY S.json_filename, matched_rule_index
        ORDER BY S.json_filename;
    """

    results = db_conn.execute(query, params).fetchall()
        
    # Process results into a structured format
    report_agg = {}
    total_counts = {row['json_filename']: row[1] for row in db_conn.execute("SELECT S.json_filename, COUNT(T.id) FROM ImageTiles T JOIN SourceFiles S ON T.source_file_id = S.id GROUP BY S.json_filename")}

    for filename in total_counts.keys():
        report_agg[filename] = {str(i): 0 for i in range(len(rules_config['rules']))}
        report_agg[filename]['default'] = 0

    for row in results:
        filename, rule_index, count = row['json_filename'], str(row['matched_rule_index']), row['count']
        if filename in report_agg:
            report_agg[filename][rule_index] = count
    
    # Format the aggregated data into the final list
    report_data = []
    for filename, counts in report_agg.items():
        total_tiles = total_counts.get(filename, 0)
        matched_sum = sum(v for k, v in counts.items() if k != 'default')
        counts['default'] = total_tiles - matched_sum

        rule_details = []
        for rule_index, count in counts.items():
            rule_name = None
            if rule_index.isdigit() and int(rule_index) < len(rules_config['rules']):
                rule_name = rules_config['rules'][int(rule_index)].get('name')

            rule_details.append({
                "rule_index": rule_index,
                "rule_name": rule_name,
                "count": count,
            })

        report_data.append({
            "json_filename": filename,
            "total_tiles": total_tiles,
            "rule_match_details": rule_details
        })
        
    return sorted(report_data, key=lambda x: x['json_filename'])