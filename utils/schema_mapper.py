"""
schema_mapper.py
----------------
Provides utilities for the schema-agnostic Upload Mode.
Detects column mappings using synonyms, standardises field names,
and merges multiple custom files into the canonical journey dataframe format.
"""

from __future__ import annotations
import pandas as pd

# The exact fields expected by the dashboard's internal logic and metrics.
# If these exist, the dashboard will work nicely.
CANONICAL_SCHEMA = {
    "sample_id": {"required": True, "type": "string", "label": "Sample ID / Order ID", "group": "Identity"},
    "patient_id": {"required": False, "type": "string", "label": "Patient ID", "group": "Identity"},
    "test_name": {"required": False, "type": "string", "label": "Test Name", "group": "Operational"},
    "lab_name": {"required": False, "type": "string", "label": "Lab Name", "group": "Operational"},
    "courier_name": {"required": False, "type": "string", "label": "Courier Name", "group": "Operational"},
    "city": {"required": False, "type": "string", "label": "City", "group": "Operational"},
    "priority_flag": {"required": False, "type": "string", "label": "Priority", "group": "Operational"},
    "promised_tat_hours": {"required": False, "type": "numeric", "label": "Promised TAT (hrs)", "group": "Operational"},
    "capacity_per_day": {"required": False, "type": "numeric", "label": "Lab Capacity/Day", "group": "Operational"},
    "sample_status": {"required": False, "type": "string", "label": "Final Status", "group": "Operational"},
    "result_status": {"required": False, "type": "string", "label": "Result Status", "group": "Operational"},
    
    "sample_collected_at": {"required": False, "type": "datetime", "label": "Collection Time", "group": "Timestamps"},
    "pickup_time": {"required": False, "type": "datetime", "label": "Courier Pickup Time", "group": "Timestamps"},
    "delivery_time": {"required": False, "type": "datetime", "label": "Lab Receipt / Delivery Time", "group": "Timestamps"},
    "lab_received_at": {"required": False, "type": "datetime", "label": "Lab Registration / Accession Time", "group": "Timestamps"},
    "test_completed_at": {"required": False, "type": "datetime", "label": "Testing Completed Time", "group": "Timestamps"},
    "report_released_at": {"required": False, "type": "datetime", "label": "Report Released Time", "group": "Timestamps"},
}

COLUMN_SYNONYMS = {
    "sample_id": ["sample_id", "specimen_id", "accession_no", "accession_id", "barcode", "case_id", "order_no", "order_id"],
    "patient_id": ["patient_id", "mrn", "patient_no", "pid"],
    "test_name": ["test_name", "test", "analyte", "assay", "procedure", "test_code", "test_type"],
    "lab_name": ["lab_name", "lab", "facility", "center", "laboratory", "lab_id"],
    "courier_name": ["courier_name", "courier", "logistics_vendor", "transporter", "courier_id"],
    "city": ["city", "location", "region", "zone"],
    "priority_flag": ["priority_flag", "priority", "urgency", "stat_flag"],
    "promised_tat_hours": ["promised_tat_hours", "expected_tat_hours", "sla_hours", "tat_target"],
    "capacity_per_day": ["capacity_per_day", "daily_capacity"],
    "sample_status": ["sample_status", "status", "state", "current_status"],
    "result_status": ["result_status", "outcome", "result"],
    
    "sample_collected_at": ["sample_collected_at", "collection_time", "collected_at", "draw_time", "collection_date"],
    "pickup_time": ["pickup_time", "picked_up_at", "courier_pickup"],
    "delivery_time": ["delivery_time", "lab_received_at", "received_at", "accessioned_at", "lab_receipt_time"],
    "lab_received_at": ["lab_received_at", "accessioned_at", "registration_time", "received_at", "delivery_time"], # Often same as delivery
    "test_completed_at": ["test_completed_at", "completed_at", "result_time", "analyzed_at"],
    "report_released_at": ["report_released_at", "released_at", "report_time", "published_at", "auth_time", "signoff_time"],
}

def infer_mapping(source_columns: list[str]) -> dict[str, str | None]:
    """
    Given a list of column names from an uploaded file, infer matching canonical fields.
    Returns a dict of {source_column: canonical_field_or_None}.
    """
    mapping = {col: None for col in source_columns}
    assigned_canonical = set()
    
    for src_col in source_columns:
        src_clean = str(src_col).lower().strip().replace(" ", "_").replace("-", "_")
        
        # 1. Exact match first
        for canonical in CANONICAL_SCHEMA:
            if src_clean == canonical and canonical not in assigned_canonical:
                mapping[src_col] = canonical
                assigned_canonical.add(canonical)
                break
        
        if mapping[src_col]:
            continue
            
        # 2. Synonym match
        best_match = None
        for canonical, synonyms in COLUMN_SYNONYMS.items():
            if canonical in assigned_canonical:
                continue
            for syn in synonyms:
                if syn == src_clean or syn in src_clean:
                    best_match = canonical
                    break
            if best_match:
                break
                
        if best_match:
            mapping[src_col] = best_match
            assigned_canonical.add(best_match)

    return mapping

def normalize_dataframe(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """
    Apply a mapping dict {source_col: canonical_field} to a DataFrame.
    Unmapped source columns are dropped. 
    It returns a DataFrame containing all Canonical fields (missing ones are created as NaN).
    """
    norm_df = df.copy()
    
    # Rename columns based on mapping
    rename_dict = {src: can for src, can in mapping.items() if can is not None}
    norm_df = norm_df.rename(columns=rename_dict)
    
    # Keep only canonical columns
    canonical_cols_present = [c for c in norm_df.columns if c in CANONICAL_SCHEMA]
    norm_df = norm_df[canonical_cols_present].copy()
    
    # Ensure datetime columns are actually datetimes
    for col in CANONICAL_SCHEMA:
        if col in norm_df.columns and CANONICAL_SCHEMA[col]["type"] == "datetime":
            norm_df[col] = pd.to_datetime(norm_df[col], errors="coerce")
            
    return norm_df

def merge_normalized_dfs(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Merges multiple normalized DataFrames into one monolithic master DataFrame.
    Tries to merge all on `sample_id` (outer join) and forward-fills overlapping columns.
    Adds any canonical fields that are completely missing across all files as NaN.
    """
    if not dfs:
        return pd.DataFrame()
        
    master_df = dfs[0].copy()
    
    for df in dfs[1:]:
        if "sample_id" not in master_df.columns or "sample_id" not in df.columns:
            # Fallback simple concat if no key
            master_df = pd.concat([master_df, df], ignore_index=True)
        else:
            # Outer merge on sample_id
            df = df.dropna(subset=["sample_id"]).drop_duplicates(subset=["sample_id"], keep="last")
            master_df = master_df.dropna(subset=["sample_id"]).drop_duplicates(subset=["sample_id"], keep="last")
            
            # Find overlapping columns (excluding sample_id)
            overlap = [c for c in master_df.columns if c in df.columns and c != "sample_id"]
            
            master_df = pd.merge(master_df, df, on="sample_id", how="outer", suffixes=("", "_y"))
            
            # Coalesce overlapping columns
            for col in overlap:
                master_df[col] = master_df[col].combine_first(master_df[f"{col}_y"])
                master_df = master_df.drop(columns=[f"{col}_y"])
                
    # Ensure all canonical columns exist in master_df to prevent dashboard crashes
    for col in CANONICAL_SCHEMA:
        if col not in master_df.columns:
            master_df[col] = None
            
    # Re-compute total_tat_hours explicitly if we have timestamps, because
    # insights and metrics depend heavily on it.
    if "total_tat_hours" not in master_df.columns:
        if pd.notna(master_df["report_released_at"]).any() and pd.notna(master_df["sample_collected_at"]).any():
            master_df["total_tat_hours"] = (
                (master_df["report_released_at"] - master_df["sample_collected_at"]).dt.total_seconds() / 3600
            )
        else:
            master_df["total_tat_hours"] = None
            
    if "courier_transit_hours" not in master_df.columns:
        if pd.notna(master_df["delivery_time"]).any() and pd.notna(master_df["pickup_time"]).any():
            master_df["courier_transit_hours"] = (
                (master_df["delivery_time"] - master_df["pickup_time"]).dt.total_seconds() / 3600
            )
        else:
            master_df["courier_transit_hours"] = None

    if "lab_processing_hours" not in master_df.columns:
        if pd.notna(master_df["test_completed_at"]).any() and pd.notna(master_df["lab_received_at"]).any():
            master_df["lab_processing_hours"] = (
                (master_df["test_completed_at"] - master_df["lab_received_at"]).dt.total_seconds() / 3600
            )
        else:
            master_df["lab_processing_hours"] = None
            
    # Compute generic sample_status if missing or completely null
    if master_df["sample_status"].isnull().all():
        def _unified_status(row):
            if row.get("result_status") == "Rejected":
                return "Rejected"
            if pd.notna(row.get("report_released_at")):
                return "Completed"
            return "In Progress"
        master_df["sample_status"] = master_df.apply(_unified_status, axis=1)

    # Date column for time series
    if "collection_date" not in master_df.columns and not master_df["sample_collected_at"].isnull().all():
        master_df["collection_date"] = master_df["sample_collected_at"].dt.date
    elif "collection_date" not in master_df.columns:
        master_df["collection_date"] = None
            
    return master_df
