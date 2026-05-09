"""
data_loader.py
--------------
Loads all synthetic CSV files from the project data directory and
merges them into a single `fct_sample_journey` dataframe used throughout
the Streamlit dashboard.

Falls back to running generate_lab_data.py if the CSV files are missing.

Supports two modes:
  - Demo Mode   : get_journey_df()               — uses synthetic local CSVs
  - Upload Mode : get_journey_df_from_uploads()  — uses user-uploaded DataFrames
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Path resolution — works regardless of where the user runs Streamlit from.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # E2E_DataEngineeringProject/
DATA_BASE = (
    PROJECT_ROOT
    / "Diagnostic Lab Operational Analytics Sample Logistics Project"
    / "data"
)

RAW_DIR = DATA_BASE / "raw"
REF_DIR = DATA_BASE / "reference"

# File map
_FILES = {
    # raw
    "sample_manifest": RAW_DIR / "sample_manifest.csv",
    "courier_events": RAW_DIR / "courier_events.csv",
    "lab_processing": RAW_DIR / "lab_processing.csv",
    # reference / dimensions
    "dim_lab": REF_DIR / "dim_lab.csv",
    "dim_courier": REF_DIR / "dim_courier.csv",
    "dim_test_type": REF_DIR / "dim_test_type.csv",
    "dim_zone": REF_DIR / "dim_zone.csv",
}


def _ensure_data() -> None:
    """Run generate_lab_data.py if any required CSV is missing."""
    missing = [k for k, p in _FILES.items() if not p.exists()]
    if not missing:
        return
    print(f"[data_loader] Missing files: {missing}. Running generate_lab_data.py …")
    gen_script = PROJECT_ROOT / "generate_lab_data.py"
    if not gen_script.exists():
        raise FileNotFoundError(
            "generate_lab_data.py not found. Please generate the data manually."
        )
    subprocess.run([sys.executable, str(gen_script)], check=True, cwd=str(PROJECT_ROOT))


def _parse_dt(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Parse datetime columns coercively."""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _safe_cols(df: pd.DataFrame, wanted: list[str]) -> list[str]:
    """Return only the columns from *wanted* that actually exist in *df*."""
    return [c for c in wanted if c in df.columns]


def load_raw_tables() -> dict[str, pd.DataFrame]:
    """
    Load all raw and reference CSV files.

    Returns
    -------
    dict[str, pd.DataFrame]
        Keys match _FILES keys.
    """
    _ensure_data()
    tables: dict[str, pd.DataFrame] = {}
    for key, path in _FILES.items():
        tables[key] = pd.read_csv(path)

    # Parse datetime columns
    tables["sample_manifest"] = _parse_dt(
        tables["sample_manifest"], ["sample_collected_at"]
    )
    tables["courier_events"] = _parse_dt(tables["courier_events"], ["event_time"])
    tables["lab_processing"] = _parse_dt(
        tables["lab_processing"],
        [
            "lab_received_at",
            "test_started_at",
            "test_completed_at",
            "report_released_at",
        ],
    )
    return tables


def build_sample_journey(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Merge raw tables into one flat fact table that mirrors the dbt
    `fct_sample_journey` model.  Includes all timestamps and computed
    duration columns.

    Returns
    -------
    pd.DataFrame
        One row per sample, with full journey, courier, lab, and test info.
    """
    sm = tables["sample_manifest"].copy()
    lp = tables["lab_processing"].copy()

    # ---- Courier events: split PickedUp vs Delivered ----
    ce = tables["courier_events"].copy()
    pickup = (
        ce[ce["event_type"] == "PickedUp"]
        .groupby("sample_id", as_index=False)
        .agg(
            pickup_time=("event_time", "first"),
            courier_id=("courier_id", "first"),
        )
    )

    delivery_agg: dict = {
        "delivery_time": ("event_time", "first"),
        "courier_delivery_status": ("status", "first"),
    }
    if "transit_minutes" in ce.columns:
        delivery_agg["transit_minutes"] = ("transit_minutes", "first")
    if "distance_km" in ce.columns:
        delivery_agg["distance_km"] = ("distance_km", "first")

    delivery = (
        ce[ce["event_type"] == "Delivered"]
        .groupby("sample_id", as_index=False)
        .agg(**delivery_agg)
    )

    # ---- Join: sample + courier + lab processing ----
    df = (
        sm.merge(pickup, on="sample_id", how="left")
        .merge(delivery, on="sample_id", how="left")
        .merge(lp, on=["sample_id", "lab_id"], how="left")
    )

    # ---- Dimension enrichment ----
    dim_lab_want = ["lab_id", "lab_name", "lab_type", "city", "capacity_per_day"]
    dim_lab = tables["dim_lab"][_safe_cols(tables["dim_lab"], dim_lab_want)]

    dim_courier_want = ["courier_id", "courier_name", "courier_type", "sla_hours"]
    dim_courier = tables["dim_courier"][
        _safe_cols(tables["dim_courier"], dim_courier_want)
    ]

    dim_test_want = [
        "test_type_id",
        "test_name",
        "test_category",
        "sample_type",
        "expected_tat_hours",
        "cost",
        "is_critical_test",
    ]
    dim_test = tables["dim_test_type"][
        _safe_cols(tables["dim_test_type"], dim_test_want)
    ]

    df = df.merge(dim_lab, on="lab_id", how="left", suffixes=("", "_lab"))
    df = df.merge(dim_courier, on="courier_id", how="left")
    df = df.merge(dim_test, on="test_type_id", how="left")

    if "dim_zone" in tables and not tables["dim_zone"].empty:
        dim_zone_want = ["zone_id", "zone_name", "city"]
        dim_zone = tables["dim_zone"][_safe_cols(tables["dim_zone"], dim_zone_want)]
        df = df.merge(dim_zone, on="zone_id", how="left", suffixes=("", "_zone"))

    # ---- Computed duration columns (hours) ----
    df["courier_transit_hours"] = (
        (df["delivery_time"] - df["pickup_time"]).dt.total_seconds() / 3600
    )
    df["lab_processing_hours"] = (
        (df["test_completed_at"] - df["lab_received_at"]).dt.total_seconds() / 3600
    )
    df["total_tat_hours"] = (
        (df["report_released_at"] - df["sample_collected_at"]).dt.total_seconds()
        / 3600
    )

    # ---- SLA breach flag ----
    df["sla_breach"] = df["total_tat_hours"] > df["promised_tat_hours"]

    # ---- Clean up city column ambiguity ----
    if "city_lab" in df.columns:
        df["city"] = df["city_lab"].combine_first(df["city"])
        df.drop(columns=["city_lab"], inplace=True, errors="ignore")

    # ---- Unified sample status ----
    def _unified_status(row) -> str:
        if row.get("result_status") == "Rejected":
            return "Rejected"
        if row.get("result_status") == "Delayed" or row.get("sla_breach"):
            return "Delayed"
        if pd.notna(row.get("report_released_at")):
            return "Completed"
        return "In Progress"

    df["sample_status"] = df.apply(_unified_status, axis=1)

    # ---- date column for time series ----
    df["collection_date"] = df["sample_collected_at"].dt.date

    return df


# ---------------------------------------------------------------------------
# Public API — Demo Mode (cached in memory)
# ---------------------------------------------------------------------------
_DEMO_CACHE: pd.DataFrame | None = None


def get_journey_df(force_reload: bool = False) -> pd.DataFrame:
    """
    Return the merged sample journey dataframe from synthetic demo data.
    Caches the result in memory across Streamlit reruns.
    """
    global _DEMO_CACHE
    if _DEMO_CACHE is None or force_reload:
        tables = load_raw_tables()
        _DEMO_CACHE = build_sample_journey(tables)
    return _DEMO_CACHE


# ---------------------------------------------------------------------------
# Public API — Upload Mode (always fresh; no caching)
# ---------------------------------------------------------------------------


def get_journey_df_from_uploads(
    sample_manifest: pd.DataFrame,
    courier_events: pd.DataFrame,
    lab_processing: pd.DataFrame,
    dim_lab: pd.DataFrame | None = None,
    dim_courier: pd.DataFrame | None = None,
    dim_test_type: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Build the journey DataFrame from user-uploaded CSVs.

    The three core files are required.  Dimension tables are optional —
    if not provided, the function falls back to the synthetic reference
    tables already on disk.

    Parameters
    ----------
    sample_manifest : Uploaded sample manifest DataFrame.
    courier_events  : Uploaded courier events DataFrame.
    lab_processing  : Uploaded lab processing DataFrame.
    dim_lab         : Optional lab dimension table.
    dim_courier     : Optional courier dimension table.
    dim_test_type   : Optional test-type dimension table.
    """
    _ensure_data()  # make sure reference dims exist on disk as fallback

    sm = _parse_dt(sample_manifest.copy(), ["sample_collected_at"])
    ce = _parse_dt(courier_events.copy(), ["event_time"])
    lp = _parse_dt(
        lab_processing.copy(),
        [
            "lab_received_at",
            "test_started_at",
            "test_completed_at",
            "report_released_at",
        ],
    )

    def _load_ref(key: str) -> pd.DataFrame:
        return pd.read_csv(_FILES[key])

    tables: dict[str, pd.DataFrame] = {
        "sample_manifest": sm,
        "courier_events": ce,
        "lab_processing": lp,
        "dim_lab": dim_lab if dim_lab is not None else _load_ref("dim_lab"),
        "dim_courier": (
            dim_courier if dim_courier is not None else _load_ref("dim_courier")
        ),
        "dim_test_type": (
            dim_test_type if dim_test_type is not None else _load_ref("dim_test_type")
        ),
        "dim_zone": _load_ref("dim_zone"),  # always from reference
    }

    return build_sample_journey(tables)
