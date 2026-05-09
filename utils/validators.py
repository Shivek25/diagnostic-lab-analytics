"""
validators.py
-------------
Reusable validation helpers for uploaded CSV files.

Each function returns a tuple (is_valid: bool, errors: list[str]).
The app should check is_valid and show errors to the user without crashing.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Required columns per file
# ---------------------------------------------------------------------------
REQUIRED_COLUMNS: dict[str, list[str]] = {
    "sample_manifest": [
        "sample_id",
        "lab_id",
        "zone_id",
        "test_type_id",
        "sample_collected_at",
        "priority_flag",
        "promised_tat_hours",
    ],
    "courier_events": [
        "sample_id",
        "courier_id",
        "event_type",
        "event_time",
        "status",
    ],
    "lab_processing": [
        "sample_id",
        "lab_id",
        "lab_received_at",
        "test_started_at",
        "test_completed_at",
        "report_released_at",
        "result_status",
    ],
    # Optional dimension files
    "dim_lab": ["lab_id", "lab_name", "lab_type", "city", "capacity_per_day"],
    "dim_courier": ["courier_id", "courier_name", "courier_type", "sla_hours"],
    "dim_test_type": [
        "test_type_id",
        "test_name",
        "test_category",
        "sample_type",
        "expected_tat_hours",
        "cost",
        "is_critical_test",
    ],
}

# Datetime columns per file
DATETIME_COLUMNS: dict[str, list[str]] = {
    "sample_manifest": ["sample_collected_at"],
    "courier_events": ["event_time"],
    "lab_processing": [
        "lab_received_at",
        "test_started_at",
        "test_completed_at",
        "report_released_at",
    ],
}


def validate_file(
    df: pd.DataFrame, file_key: str
) -> tuple[bool, list[str]]:
    """
    Validate a single uploaded DataFrame against the expected schema.

    Parameters
    ----------
    df       : The uploaded DataFrame.
    file_key : One of the keys in REQUIRED_COLUMNS (e.g. 'sample_manifest').

    Returns
    -------
    (is_valid, errors)
    """
    errors: list[str] = []

    # 1. Not empty
    if df.empty:
        errors.append(f"❌ The uploaded file is empty.")
        return False, errors

    # 2. Required columns present
    required = REQUIRED_COLUMNS.get(file_key, [])
    missing_cols = [c for c in required if c not in df.columns]
    for col in missing_cols:
        errors.append(f"❌ Missing required column: `{col}`")

    if missing_cols:
        return False, errors

    # 3. Key column not all-null
    key_col_map = {
        "sample_manifest": "sample_id",
        "courier_events": "sample_id",
        "lab_processing": "sample_id",
        "dim_lab": "lab_id",
        "dim_courier": "courier_id",
        "dim_test_type": "test_type_id",
    }
    key_col = key_col_map.get(file_key)
    if key_col and df[key_col].isna().all():
        errors.append(
            f"❌ Column `{key_col}` contains only null values. "
            "Please check the file content."
        )

    # 4. Datetime columns parseable
    dt_cols = DATETIME_COLUMNS.get(file_key, [])
    for col in dt_cols:
        if col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce")
            bad_pct = parsed.isna().mean()
            if bad_pct > 0.5:
                errors.append(
                    f"⚠️ Column `{col}` has {bad_pct*100:.0f}% unparseable "
                    "datetime values. Ensure format is ISO 8601 "
                    "(e.g. 2024-01-15 08:30:00)."
                )

    is_valid = len(errors) == 0
    return is_valid, errors


def validate_all_core_files(
    uploads: dict[str, pd.DataFrame | None],
) -> dict[str, tuple[bool, list[str]]]:
    """
    Validate a dict of {file_key: df_or_None} for the 3 core files.
    Returns a dict of {file_key: (is_valid, errors)}.
    """
    core_keys = ["sample_manifest", "courier_events", "lab_processing"]
    results: dict[str, tuple[bool, list[str]]] = {}
    for key in core_keys:
        df = uploads.get(key)
        if df is None:
            results[key] = (False, [f"❌ File not uploaded yet."])
        else:
            results[key] = validate_file(df, key)
    return results


def all_core_files_valid(
    validation_results: dict[str, tuple[bool, list[str]]],
) -> bool:
    """Return True only if all 3 core files passed validation."""
    return all(v for v, _ in validation_results.values())
