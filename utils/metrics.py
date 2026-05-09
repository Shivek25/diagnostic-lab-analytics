"""
metrics.py
----------
Pure helper functions for computing the core KPIs displayed across all
dashboard sections.  Every function accepts a (possibly filtered) sample
journey DataFrame and returns a scalar or aggregated DataFrame.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Scalar KPIs
# ---------------------------------------------------------------------------

def total_samples(df: pd.DataFrame) -> int:
    return len(df)


def completed_samples(df: pd.DataFrame) -> int:
    return int((df["sample_status"] == "Completed").sum())


def rejected_samples(df: pd.DataFrame) -> int:
    return int((df["sample_status"] == "Rejected").sum())


def delayed_samples(df: pd.DataFrame) -> int:
    return int((df["sample_status"] == "Delayed").sum())


def rejection_rate(df: pd.DataFrame) -> float:
    """Rejection rate as a percentage (0–100)."""
    n = len(df)
    if n == 0:
        return 0.0
    return round(rejected_samples(df) / n * 100, 2)


def sla_breach_rate(df: pd.DataFrame) -> float:
    """
    Percentage of *non-rejected* samples that breached the SLA.
    Rejected samples cannot be meaningfully classified on SLA.
    """
    if "sla_breach" not in df.columns:
        return 0.0
    active = df[df["sample_status"] != "Rejected"]
    n = len(active)
    if n == 0:
        return 0.0
    breached = active["sla_breach"].sum()
    return round(breached / n * 100, 2)


def avg_tat_hours(df: pd.DataFrame) -> float:
    """Average end-to-end TAT for completed samples (hours)."""
    completed = df[df["sample_status"] == "Completed"]
    vals = completed["total_tat_hours"].dropna()
    return round(float(vals.mean()), 2) if len(vals) > 0 else 0.0


def avg_courier_transit_hours(df: pd.DataFrame) -> float:
    """Average courier transit time (pickup → delivery) in hours."""
    vals = df["courier_transit_hours"].dropna()
    return round(float(vals.mean()), 2) if len(vals) > 0 else 0.0


def avg_lab_processing_hours(df: pd.DataFrame) -> float:
    """Average lab processing time (receipt → test completion) in hours."""
    vals = df["lab_processing_hours"].dropna()
    return round(float(vals.mean()), 2) if len(vals) > 0 else 0.0


# ---------------------------------------------------------------------------
# Filtered subsets for Alerts
# ---------------------------------------------------------------------------

def get_delayed_samples_df(df: pd.DataFrame) -> pd.DataFrame:
    """Returns samples that are delayed based on expected TAT or already marked as delayed."""
    # A sample is delayed if its status is Delayed OR total_tat_hours > expected_tat_hours
    # We'll use expected_tat_hours for a stricter check
    if "expected_tat_hours" in df.columns:
        return df[(df["sample_status"] == "Delayed") | (df["total_tat_hours"] > df["expected_tat_hours"])]
    return df[df["sample_status"] == "Delayed"]


def get_sla_breaches_df(df: pd.DataFrame) -> pd.DataFrame:
    """Returns samples that breached their promised SLA."""
    if "sla_breach" in df.columns:
        return df[df["sla_breach"] == True]
    return df.iloc[0:0] # empty fallback


def get_critical_delays_df(df: pd.DataFrame) -> pd.DataFrame:
    """Returns samples delayed beyond 2x their expected TAT."""
    if "expected_tat_hours" in df.columns and "total_tat_hours" in df.columns:
        return df[df["total_tat_hours"] > (2 * df["expected_tat_hours"])]
    return df.iloc[0:0]


# ---------------------------------------------------------------------------
# Lab-level aggregations
# ---------------------------------------------------------------------------

def lab_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per lab with:
      - sample_count
      - avg_tat_hours
      - rejection_rate_pct
      - sla_breach_rate_pct
    """
    if "lab_name" not in df.columns or df["lab_name"].isnull().all():
        return pd.DataFrame()
        
    g = df.groupby("lab_name", as_index=False)

    counts = g["sample_id"].count().rename(columns={"sample_id": "sample_count"})

    tat = (
        df[df["sample_status"] == "Completed"]
        .groupby("lab_name", as_index=False)["total_tat_hours"]
        .mean()
        .rename(columns={"total_tat_hours": "avg_tat_hours"})
    )

    def _rej_rate(sub):
        n = len(sub)
        return round((sub["sample_status"] == "Rejected").sum() / n * 100, 2) if n else 0.0

    def _sla_rate(sub):
        active = sub[sub["sample_status"] != "Rejected"]
        n = len(active)
        if "sla_breach" in sub.columns:
            return round(active["sla_breach"].sum() / n * 100, 2) if n else 0.0
        return 0.0

    rejections = (
        df.groupby("lab_name")
        .apply(_rej_rate, include_groups=False)
        .reset_index(name="rejection_rate_pct")
    )
    sla = (
        df.groupby("lab_name")
        .apply(_sla_rate, include_groups=False)
        .reset_index(name="sla_breach_rate_pct")
    )

    result = counts.merge(tat, on="lab_name", how="left")
    result = result.merge(rejections, on="lab_name", how="left")
    result = result.merge(sla, on="lab_name", how="left")
    result["avg_tat_hours"] = result["avg_tat_hours"].fillna(0.0).round(2)
    return result.sort_values("sample_count", ascending=False)



# ---------------------------------------------------------------------------
# Courier-level aggregations
# ---------------------------------------------------------------------------

def courier_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per courier with:
      - sample_count
      - avg_transit_hours
      - delay_rate_pct  (transit > courier SLA)
      - on_time_rate_pct
    """
    if "courier_name" not in df.columns or df["courier_name"].isnull().all():
        return pd.DataFrame()
        
    g = df.groupby("courier_name", as_index=False)

    counts = g["sample_id"].count().rename(columns={"sample_id": "sample_count"})
    
    if "courier_transit_hours" in df.columns:
        transit = g["courier_transit_hours"].mean().rename(
            columns={"courier_transit_hours": "avg_transit_hours"}
        )
    else:
        transit = pd.DataFrame({"courier_name": counts["courier_name"], "avg_transit_hours": 0.0})

    # Courier delay: transit_hours > sla_hours
    df = df.copy()
    if "courier_transit_hours" in df.columns and "sla_hours" in df.columns:
        df["courier_delayed"] = df["courier_transit_hours"] > df["sla_hours"]
    else:
        df["courier_delayed"] = False

    def _delay_rate(sub):
        n = len(sub)
        return round(sub["courier_delayed"].sum() / n * 100, 2) if n else 0.0

    delays = (
        df.groupby("courier_name")
        .apply(_delay_rate, include_groups=False)
        .reset_index(name="delay_rate_pct")
    )

    result = counts.merge(transit, on="courier_name", how="left")
    result = result.merge(delays, on="courier_name", how="left")
    result["avg_transit_hours"] = result["avg_transit_hours"].fillna(0.0).round(2)
    result["on_time_rate_pct"] = (100 - result["delay_rate_pct"]).round(2)
    return result.sort_values("sample_count", ascending=False)


# ---------------------------------------------------------------------------
# Test type aggregations
# ---------------------------------------------------------------------------

def test_type_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per test with:
      - sample_count
      - avg_tat_hours
      - rejection_rate_pct
      - is_critical_test
    """
    if "test_name" not in df.columns or df["test_name"].isnull().all():
        return pd.DataFrame()
        
    g = df.groupby("test_name", as_index=False)
    counts = g["sample_id"].count().rename(columns={"sample_id": "sample_count"})

    tat = (
        df[df["sample_status"] == "Completed"]
        .groupby("test_name", as_index=False)["total_tat_hours"]
        .mean()
        .rename(columns={"total_tat_hours": "avg_tat_hours"})
    )

    def _rej_rate(sub):
        n = len(sub)
        return round((sub["sample_status"] == "Rejected").sum() / n * 100, 2) if n else 0.0

    rejections = (
        df.groupby("test_name")
        .apply(_rej_rate, include_groups=False)
        .reset_index(name="rejection_rate_pct")
    )

    result = counts.merge(tat, on="test_name", how="left")
    result = result.merge(rejections, on="test_name", how="left")
    
    # Critical flag — take first value since it's static per test
    if "is_critical_test" in df.columns:
        critical = (
            df.groupby("test_name", as_index=False)["is_critical_test"]
            .first()
        )
        result = result.merge(critical, on="test_name", how="left")
    else:
        result["is_critical_test"] = False
        
    result["avg_tat_hours"] = result["avg_tat_hours"].fillna(0.0).round(2)
    return result.sort_values("sample_count", ascending=False)


# ---------------------------------------------------------------------------
# Daily trend
# ---------------------------------------------------------------------------

def daily_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Daily sample volume with status breakdown."""
    df = df.copy()
    df["collection_date"] = pd.to_datetime(df["collection_date"]).dt.date
    daily = (
        df.groupby(["collection_date", "sample_status"], as_index=False)["sample_id"]
        .count()
        .rename(columns={"sample_id": "count"})
    )
    return daily.sort_values("collection_date")
