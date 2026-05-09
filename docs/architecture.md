# Architecture — Diagnostic Lab Operational Analytics Platform

---

## Overview

The platform is a six-layer data stack: ingestion → schema mapping → normalization → metrics engine → insights engine → dashboard layer.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Data Sources                                  │
│   [LIS CSV Export]  [Manual Spreadsheet]  [Synthetic Demo Data]     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Ingestion Layer                                   │
│   Upload Mode: Streamlit file_uploader (CSV / XLSX / TSV)            │
│   Demo Mode: CSV files read from local data/ directory               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Schema Mapping Layer                                │
│   utils/schema_mapper.py                                             │
│   • CANONICAL_SCHEMA defines 25+ supported field names               │
│   • infer_mapping() fuzzy-matches user columns to canonical fields   │
│   • normalize_dataframe() renames and coerces columns                │
│   • merge_normalized_dfs() joins multiple files on sample_id         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Normalization Layer                                  │
│   utils/data_loader.py                                               │
│   • build_sample_journey() merges raw + dimension tables             │
│   • Computes courier_transit_hours, lab_processing_hours, total_tat  │
│   • Sets sla_breach flag (total_tat > promised_tat)                  │
│   • Unified sample_status column (Completed / Rejected / Delayed)    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Metrics Engine                                    │
│   utils/metrics.py                                                   │
│   • total_samples(), completed_samples(), rejected_samples()         │
│   • avg_tat_hours(), sla_breach_rate(), daily_volume()               │
│   • lab_summary(), courier_summary(), test_type_summary()            │
│   • get_delayed_samples_df(), get_sla_breaches_df()                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Insights Engine                                   │
│   utils/insights.py                                                  │
│   • generate_insights() — auto-text highlights from the data         │
│   • generate_executive_summary() — plain-English management snapshot │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Dashboard Layer                                  │
│   app.py (Streamlit)                                                 │
│   • 6 tabs: Alerts, Overview, Lab, Courier, Test Type, Sample Journey│
│   • Global sidebar filters: date, city, lab, courier, test, status   │
│   • Plotly charts, KPI cards, styled dataframes                      │
│   • CSV export of filtered data and summary report                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Upload Mode — How It Works

```
User uploads CSV/XLSX/TSV
          │
          ▼
        Read file (pandas)
          │
          ▼
     infer_mapping()
     ┌────────────────────────────────────────────┐
     │  For each user column:                      │
     │  • Lowercase + strip whitespace             │
     │  • Check alias dictionary (100+ aliases)    │
     │  • Fall back to fuzzy substring match       │
     └────────────────────────────────────────────┘
          │
          ▼
     Schema Mapping Wizard (Streamlit UI)
     User reviews and adjusts auto-suggestions
          │
          ▼
     normalize_dataframe()
     • Renames columns to canonical names
     • Type-coerces timestamps, numerics
          │
          ▼
     merge_normalized_dfs()
     • Outer join on sample_id
     • Deduplicates overlapping fields
          │
          ▼
     Dashboard renders analytics
```

---

## Canonical Schema

The platform uses a canonical schema of 25+ standardised field names. All user data is normalised to this schema before analytics run.

**Core fields:**
- `sample_id` — Unique sample identifier (required)
- `collection_date`, `sample_collected_at` — Collection timestamps
- `lab_name`, `lab_id` — Lab information
- `courier_name`, `courier_id` — Courier vendor
- `test_name`, `test_type_id` — Test type
- `sample_status` — Completion status
- `sla_breach` — SLA breach flag (boolean)
- `total_tat_hours`, `promised_tat_hours` — Turnaround time fields
- `courier_transit_hours`, `lab_processing_hours` — Duration components
- `rejection_reason` — Rejection classification
- `city`, `zone_id` — Geographic fields

---

## Demo Mode — Data Flow

In Demo Mode, synthetic CSV data is pre-generated and stored in:

```
Diagnostic Lab Operational Analytics Sample Logistics Project/
└── data/
    ├── raw/
    │   ├── sample_manifest.csv    ← One row per sample
    │   ├── courier_events.csv     ← PickedUp / Delivered events
    │   └── lab_processing.csv     ← Lab receipt + test timestamps
    └── reference/
        ├── dim_lab.csv
        ├── dim_courier.csv
        ├── dim_test_type.csv
        └── dim_zone.csv
```

`data_loader.py` merges these tables into a single `fct_sample_journey` flat table, which is then filtered and visualised by the dashboard.

---

## Validation Layer

`utils/validators.py` provides column type checks and null-safety for critical fields before the metrics engine runs. This prevents crashes on partial or malformed uploads.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| UI Framework | Streamlit |
| Data Processing | Pandas, NumPy |
| Visualisations | Plotly Express + Graph Objects |
| Synthetic Data | Python Faker |
| File Formats | CSV, XLSX, TSV |
| Deployment | Streamlit Community Cloud |
| Version Control | GitHub |
