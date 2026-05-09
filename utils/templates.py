"""
templates.py
------------
Generates downloadable CSV template files for first-time users who
want to upload their own data.

Provides 3 templates for different common laboratory data ingestion patterns:
1. Single Flat File
2. Sample + Results separation
3. Full Operational (Sample + Courier + Lab Processing)
"""

from __future__ import annotations
import io
import pandas as pd

def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def flat_file_template() -> bytes:
    """A template providing all information in a single row per sample."""
    df = pd.DataFrame({
        "sample_id": ["SMP001", "SMP002", "SMP003"],
        "patient_id": ["P100", "P101", "P102"],
        "test_name": ["Complete Blood Count", "Lipid Panel", "Thyroid Panel"],
        "lab_name": ["Metro Labs", "Metro Labs", "City Diagnostics"],
        "courier_name": ["QuickMed", "SafeTransit", "QuickMed"],
        "city": ["Mumbai", "Delhi", "Mumbai"],
        "priority_flag": ["Normal", "Urgent", "Normal"],
        "promised_tat_hours": [24, 12, 48],
        "sample_collected_at": ["2024-01-15 08:30:00", "2024-01-15 09:00:00", "2024-01-15 10:15:00"],
        "pickup_time": ["2024-01-15 09:15:00", "2024-01-15 09:30:00", "2024-01-15 11:00:00"],
        "delivery_time": ["2024-01-15 10:30:00", "2024-01-15 10:45:00", "2024-01-15 12:30:00"],
        "lab_received_at": ["2024-01-15 11:00:00", "2024-01-15 11:30:00", "2024-01-15 13:00:00"],
        "test_completed_at": ["2024-01-15 18:00:00", "2024-01-15 20:00:00", "2024-01-15 22:00:00"],
        "report_released_at": ["2024-01-15 19:00:00", "2024-01-15 21:00:00", "2024-01-15 23:00:00"],
        "result_status": ["Completed", "Delayed", "Completed"],
    })
    return _to_csv_bytes(df)

def basic_order_template() -> bytes:
    """Template focusing purely on order entry/sample collection."""
    df = pd.DataFrame({
        "order_no": ["ORD001", "ORD002", "ORD003"],
        "patient_no": ["P100", "P101", "P102"],
        "assay": ["CBC", "Lipid", "HbA1c"],
        "collection_time": ["2024-01-15 08:30:00", "2024-01-15 09:00:00", "2024-01-15 10:15:00"],
        "urgency": ["Routine", "Stat", "Routine"],
        "location": ["Mumbai", "Delhi", "Pune"],
    })
    return _to_csv_bytes(df)

def basic_result_template() -> bytes:
    """Template focusing purely on the laboratory results timeline."""
    df = pd.DataFrame({
        "order_no": ["ORD001", "ORD002", "ORD003"],
        "facility": ["Metro Labs", "Metro Labs", "City Diagnostics"],
        "accessioned_at": ["2024-01-15 11:00:00", "2024-01-15 11:30:00", "2024-01-15 13:00:00"],
        "analyzed_at": ["2024-01-15 18:00:00", "2024-01-15 20:00:00", "2024-01-15 22:00:00"],
        "signoff_time": ["2024-01-15 19:00:00", "2024-01-15 21:00:00", "2024-01-15 23:00:00"],
        "outcome": ["Completed", "Delayed", "Completed"],
    })
    return _to_csv_bytes(df)

def courier_tracking_template() -> bytes:
    """Template focusing on courier tracking data."""
    df = pd.DataFrame({
        "order_no": ["ORD001", "ORD002", "ORD003"],
        "logistics_vendor": ["QuickMed", "SafeTransit", "QuickMed"],
        "picked_up_at": ["2024-01-15 09:15:00", "2024-01-15 09:30:00", "2024-01-15 11:00:00"],
        "lab_receipt_time": ["2024-01-15 10:30:00", "2024-01-15 10:45:00", "2024-01-15 12:30:00"],
    })
    return _to_csv_bytes(df)
