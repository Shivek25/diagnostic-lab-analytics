"""
app.py — Diagnostic Lab Operational Analytics Dashboard
=========================================================
A locally-runnable Streamlit app that visualises sample logistics and
lab operations metrics for diagnostic labs.

Supports two data source modes:
  1. Demo Mode   — uses synthetic local CSV data (existing behaviour)
  2. Upload Mode — users upload their own CSV files for live analysis

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Make sure utils/ is importable regardless of CWD ──────────────────────
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.data_loader import get_journey_df, get_journey_df_from_uploads
from utils import metrics as m
from utils.insights import generate_insights, generate_executive_summary
from utils import validators as v
from utils import templates as tmpl
from utils.schema_mapper import CANONICAL_SCHEMA, infer_mapping, normalize_dataframe, merge_normalized_dfs

# ═══════════════════════════════════════════════════════════════════════════
# Page config
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Lab Ops Analytics Dashboard",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════
# Global CSS — clean B2B look
# ═══════════════════════════════════════════════════════════════════════════
st.markdown(
    """
    <style>
        /* Import Google Font */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

        /* Sidebar branding strip */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        }
        section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
        section[data-testid="stSidebar"] .stMarkdown h2 {
            color: #38bdf8 !important; font-size: 1.05rem; letter-spacing: 0.05em;
        }
        section[data-testid="stSidebar"] .stMarkdown h3 {
            color: #7dd3fc !important; font-size: 0.95rem; letter-spacing: 0.03em;
        }

        /* Hide default top margin */
        .block-container { padding-top: 1.5rem; }

        /* KPI card style */
        .kpi-card {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 18px 22px;
            text-align: center;
            color: #f1f5f9;
        }
        .kpi-label  { font-size: 0.78rem; color: #94a3b8; text-transform: uppercase;
                      letter-spacing: 0.06em; margin-bottom: 6px; }
        .kpi-value  { font-size: 2rem; font-weight: 700; color: #00F2FE; line-height: 1.1; }
        .kpi-sub    { font-size: 0.75rem; color: #64748b; margin-top: 4px; }

        /* Section headers */
        .section-title {
            font-size: 1.1rem; font-weight: 600; color: #E0E7FF;
            border-left: 4px solid #00F2FE; padding-left: 10px;
            margin: 24px 0 12px 0;
        }

        /* Tab styling override */
        .stTabs [data-baseweb="tab-list"] { gap: 6px; }
        .stTabs [data-baseweb="tab"] {
            font-size: 0.85rem; font-weight: 500;
            padding: 8px 18px; border-radius: 8px 8px 0 0;
            color: #94a3b8;
        }

        /* Executive summary card */
        .exec-row {
            display: flex; align-items: flex-start;
            padding: 8px 0; border-bottom: 1px solid #1e293b;
        }
        .exec-label {
            min-width: 200px; font-size: 0.82rem; color: #94a3b8;
            text-transform: uppercase; letter-spacing: 0.05em; padding-top: 2px;
        }
        .exec-value { font-size: 0.95rem; font-weight: 600; color: #f1f5f9; }

        /* Upload status badges */
        .badge-ok   { background:#064e3b; color:#34d399; border-radius:6px;
                      padding:3px 10px; font-size:0.78rem; font-weight:600; }
        .badge-warn { background:#451a03; color:#fb923c; border-radius:6px;
                      padding:3px 10px; font-size:0.78rem; font-weight:600; }
        .badge-err  { background:#450a0a; color:#f87171; border-radius:6px;
                      padding:3px 10px; font-size:0.78rem; font-weight:600; }

        /* Empty state */
        .empty-state {
            text-align:center; padding: 60px 20px;
            color:#64748b;
        }
        .empty-state h3 { color:#94a3b8; margin-bottom:8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════
BRAND_BLUE = "#00F2FE"
CHART_COLORS = ["#00F2FE", "#4FACFE", "#43E97B", "#38F9D7", "#FA709A", "#FEE140"]
CHART_BG = "rgba(0,0,0,0)"
AXIS_COLOR = "#475569"
GRID_COLOR = "#0F172A"


def apply_chart_style(fig: go.Figure, height: int = 340) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        font=dict(family="Inter", color="#e2e8f0", size=12),
        margin=dict(l=12, r=12, t=36, b=12),
        legend=dict(bgcolor="rgba(0,0,0,0)", font_size=11),
        xaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, color=AXIS_COLOR),
        yaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, color=AXIS_COLOR),
    )
    return fig


def kpi(label: str, value, sub: str = "") -> str:
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f"</div>"
    )


def empty_state(title: str, message: str) -> None:
    st.markdown(
        f"""
        <div class="empty-state">
            <h3>{title}</h3>
            <p>{message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def file_badge(label: str, ok: bool | None) -> str:
    if ok is None:
        return f'<span class="badge-warn">⏳ {label}: Awaiting Upload</span>'
    if ok:
        return f'<span class="badge-ok">✅ {label}: Valid</span>'
    return f'<span class="badge-err">❌ {label}: Invalid</span>'


# ═══════════════════════════════════════════════════════════════════════════
# Sidebar — Data Source Mode Selection
# ═══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🧪 Lab Ops Dashboard")
    st.caption("Diagnostic Lab Operational Analytics")
    st.divider()

    # ── Data Source Selection ────────────────────────────────────────────
    st.markdown("### 📂 Data Source")
    data_mode = st.radio(
        label="Select data source",
        options=["🔬 Demo Mode", "📤 Upload Your Own Data"],
        index=0,
        label_visibility="collapsed",
    )
    IS_UPLOAD_MODE = data_mode == "📤 Upload Your Own Data"

    st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# Upload Mode — Universal Schema Mapper
# ═══════════════════════════════════════════════════════════════════════════
df_full: pd.DataFrame = pd.DataFrame()

if IS_UPLOAD_MODE:
    with st.sidebar:
        st.markdown("### 📤 Upload Your Data")
        st.caption("Provide one or multiple files from your LIS or system.")
        
        ufs = st.file_uploader(
            "Drop CSV files here", 
            type=["csv", "xlsx", "tsv"], 
            accept_multiple_files=True
        )

        st.divider()
        st.markdown("### 📥 Example Templates")
        st.caption("Not sure how to structure data? Try these:")

        st.download_button("Single Flat File", data=tmpl.flat_file_template(), file_name="flat_template.csv", mime="text/csv", use_container_width=True)
        st.download_button("Orders File", data=tmpl.basic_order_template(), file_name="orders_template.csv", mime="text/csv", use_container_width=True)
        st.download_button("Results File", data=tmpl.basic_result_template(), file_name="results_template.csv", mime="text/csv", use_container_width=True)
        st.download_button("Courier File", data=tmpl.courier_tracking_template(), file_name="courier_template.csv", mime="text/csv", use_container_width=True)

    if not ufs:
        st.info("👋 **Welcome to the Universal Upload Mode!**\\n\\n"
                "Upload one or more CSV/XLSX files from your lab. We'll help you map your columns into the dashboard automatically. You can upload flat files, separate order/result files, or any export from your system.")
        st.stop()

    # Read all files
    raw_dfs = {}
    for uf in ufs:
        try:
            if uf.name.endswith(".xlsx"):
                raw_dfs[uf.name] = pd.read_excel(uf)
            elif uf.name.endswith(".tsv"):
                raw_dfs[uf.name] = pd.read_csv(uf, sep='	')
            else:
                raw_dfs[uf.name] = pd.read_csv(uf)
        except Exception:
            st.error(f"Failed to read {uf.name}")
            st.stop()

    # Step-by-step mapping UI
    st.markdown("### 🗺️ Schema Mapping Wizard")
    st.markdown("Please confirm or adjust how your file columns map to the dashboard's internal fields.")
    
    if "mappings" not in st.session_state:
        st.session_state["mappings"] = {}

    all_normalized_dfs = []
    
    for fname, df_raw in raw_dfs.items():
        with st.expander(f"📄 Mapping for **{fname}** ({len(df_raw)} rows)", expanded=True):
            st.dataframe(df_raw.head(3), use_container_width=True)
            
            # Infer if not found in session state for this exact config
            if fname not in st.session_state["mappings"]:
                st.session_state["mappings"][fname] = infer_mapping(df_raw.columns.tolist())
            
            c_map = st.session_state["mappings"][fname]
            
            cols = st.columns(4)
            updated_map = {}
            for idx, src_col in enumerate(df_raw.columns):
                # We present a selectbox for each source column
                col_container = cols[idx % 4]
                
                # Options are empty (Ignore) + all Canonical labels
                options = ["-- Ignore --"] + list(CANONICAL_SCHEMA.keys())
                
                curr_val = c_map.get(src_col)
                try:
                    def_idx = options.index(curr_val) if curr_val in options else 0
                except ValueError:
                    def_idx = 0
                    
                chosen = col_container.selectbox(
                    f"`{src_col}` maps to:",
                    options=options,
                    index=def_idx,
                    key=f"map_{fname}_{src_col}"
                )
                if chosen != "-- Ignore --":
                    updated_map[src_col] = chosen
            
            st.session_state["mappings"][fname] = updated_map
            
            # Show required field check
            has_id = any(v == "sample_id" for v in updated_map.values())
            if not has_id:
                st.warning("⚠️ No column mapped to `sample_id`. This file cannot be joined.")
            else:
                all_normalized_dfs.append(normalize_dataframe(df_raw, updated_map))
                
    st.divider()
    
    if st.button("🚀 Confirm Mapping & Build Dashboard", type="primary", use_container_width=True):
        if not all_normalized_dfs:
            st.error("No valid datatables mapped with `sample_id`.")
            st.stop()
        
        df_full = merge_normalized_dfs(all_normalized_dfs)
        
        # We need validation. Update validators.py if needed, or simply let df_full pass directly.
        st.success(f"✅ Dashboard generated successfully from {len(df_full):,} combined records!")
    else:
        st.stop()  # Wait for user to confirm

else:
    # ── Demo Mode — load synthetic data ─────────────────────────────────
    @st.cache_data(show_spinner="Loading demo data …")
    def _load_demo() -> pd.DataFrame:
        return get_journey_df()

    df_full = _load_demo()

# ═══════════════════════════════════════════════════════════════════════════
# Sidebar — Global Filters (shown only when we have data)
# ═══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    if not df_full.empty:
        st.markdown("### 🔍 Dashboard Filters")

        # Date range
        try:
            min_date = pd.to_datetime(df_full["collection_date"]).dt.date.min()
            max_date = pd.to_datetime(df_full["collection_date"]).dt.date.max()
        except Exception:
            min_date, max_date = None, None

        date_range = st.date_input(
            "📅 Date Range",
            value=[],  # Empty list means no range selected by default
            min_value=min_date if pd.notna(min_date) else None,
            max_value=max_date if pd.notna(max_date) else None,
        )

        st.divider()

        # City
        cities = sorted(df_full["city"].dropna().unique().tolist())
        sel_cities = st.multiselect("🏙 City", cities, default=[])

        # Lab
        labs = sorted(df_full["lab_name"].dropna().unique().tolist())
        sel_labs = st.multiselect("🏥 Lab", labs, default=[])

        # Courier
        couriers = sorted(df_full["courier_name"].dropna().unique().tolist())
        sel_couriers = st.multiselect("🚚 Courier", couriers, default=[])

        # Test type
        tests = sorted(df_full["test_name"].dropna().unique().tolist())
        sel_tests = st.multiselect("🔬 Test Type", tests, default=[])

        # Sample status
        statuses = sorted(df_full["sample_status"].dropna().unique().tolist())
        sel_statuses = st.multiselect("📊 Sample Status", statuses, default=[])

        st.divider()

        # ── Apply filters ────────────────────────────────────────────────
        try:
            d_start, d_end = date_range[0], date_range[1]
        except (IndexError, TypeError):
            d_start, d_end = min_date, max_date

        mask = pd.Series(True, index=df_full.index)
        if pd.notna(d_start) and pd.notna(d_end):
            col_date = pd.to_datetime(df_full["collection_date"]).dt.date
            mask &= (col_date >= d_start) & (col_date <= d_end)
            
        if sel_cities:
            mask &= df_full["city"].isin(sel_cities)
        if sel_labs:
            mask &= df_full["lab_name"].isin(sel_labs)
        if sel_couriers:
            mask &= df_full["courier_name"].isin(sel_couriers)
        if sel_tests:
            mask &= df_full["test_name"].isin(sel_tests)
        if sel_statuses:
            mask &= df_full["sample_status"].isin(sel_statuses)
        
        df = df_full[mask].copy()

        # Export buttons
        st.markdown("### 📥 Export Data")
        if not df.empty:
            csv_full = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Filtered Data (CSV)",
                data=csv_full,
                file_name="lab_ops_filtered_data.csv",
                mime="text/csv",
            )
            lab_summary_csv = m.lab_summary(df).to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Summary Report (CSV)",
                data=lab_summary_csv,
                file_name="lab_ops_summary_report.csv",
                mime="text/csv",
            )
    else:
        df = pd.DataFrame()
        d_start = d_end = None

    if IS_UPLOAD_MODE:
        st.divider()
        st.caption("Mode: Upload · No cloud required")
    else:
        st.divider()
        st.caption("Mode: Demo · Synthetic data · No cloud required")

# ═══════════════════════════════════════════════════════════════════════════
# Header
# ═══════════════════════════════════════════════════════════════════════════
mode_badge = (
    '<span style="background:#0c4a6e;color:#38bdf8;border-radius:6px;'
    'padding:3px 10px;font-size:0.78rem;font-weight:600;margin-left:12px;">📤 Upload Mode</span>'
    if IS_UPLOAD_MODE
    else '<span style="background:#14532d;color:#34d399;border-radius:6px;'
    'padding:3px 10px;font-size:0.78rem;font-weight:600;margin-left:12px;">🔬 Demo Mode</span>'
)

st.markdown(
    f"""
    <div style="background:linear-gradient(90deg,#0f172a,#1e3a5f);
                border-radius:14px;padding:24px 32px;margin-bottom:24px;">
        <h1 style="color:#38bdf8;margin:0;font-size:1.8rem;font-weight:700;letter-spacing:-0.02em;">
            🏥 Lab Ops Analytics Dashboard {mode_badge}
        </h1>
        <p style="color:#94a3b8;margin:6px 0 0 0;font-size:0.92rem;">
            Operational Intelligence for Diagnostic Labs
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════════════════
# Tabs
# ═══════════════════════════════════════════════════════════════════════════
tab_alerts, tab_overview, tab_lab, tab_courier, tab_test, tab_journey = st.tabs([
    "🚨 Alerts & Insights",
    "📊 Executive Overview",
    "🏥 Lab Performance",
    "🚚 Courier Performance",
    "🔬 Test Type Analytics",
    "🗺 Sample Journey",
])

# ┌───────────────────────────────────────────────────────────────────────┐
# │ 0. ALERTS & INSIGHTS                                                  │
# └───────────────────────────────────────────────────────────────────────┘
with tab_alerts:
    if df.empty:
        empty_state(
            "📭 No Data to Show",
            "No data matches the current filters. Try expanding the date range or filter selection.",
        )
    else:
        st.markdown('<div class="section-title">Critical Alerts</div>', unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        num_delayed = len(m.get_delayed_samples_df(df))
        num_sla_breach = len(m.get_sla_breaches_df(df))
        num_critical = len(m.get_critical_delays_df(df))

        with c1:
            st.markdown(kpi("Delayed Samples", f"{num_delayed:,}", "Past expected TAT"), unsafe_allow_html=True)
        with c2:
            st.markdown(kpi("SLA Breaches", f"{num_sla_breach:,}", "Past promised TAT"), unsafe_allow_html=True)
        with c3:
            st.markdown(kpi("Critical Delays", f"{num_critical:,}", "> 2x expected TAT"), unsafe_allow_html=True)

        # ── Automated Insights ───────────────────────────────────────────
        st.markdown('<div class="section-title">Automated Insights</div>', unsafe_allow_html=True)
        insights = generate_insights(df)
        for insight in insights:
            st.info(insight)

        # ── Executive Operational Summary ────────────────────────────────
        st.markdown('<div class="section-title">Operational Summary</div>', unsafe_allow_html=True)
        st.caption("Management snapshot — plain-English business metrics")

        exec_summary = generate_executive_summary(df)
        if exec_summary:
            rows = [
                ("Total Samples Analyzed", exec_summary.get("total_samples", "—")),
                ("Overall Delay Rate", exec_summary.get("delay_rate", "—")),
                ("Overall Rejection Rate", exec_summary.get("rejection_rate", "—")),
                ("SLA Breach Rate", exec_summary.get("sla_breach_rate", "—")),
                ("Avg End-to-End TAT", exec_summary.get("avg_tat", "—")),
                ("Highest Rejection Lab", exec_summary.get("highest_rejection_lab", "—")),
                ("Slowest Courier", exec_summary.get("slowest_courier", "—")),
                ("Most Delayed Test Type", exec_summary.get("most_delayed_test", "—")),
                ("Top City by Delays", exec_summary.get("top_delayed_city", "—")),
            ]
            summary_html = (
                '<div style="background:#0f172a;border:1px solid #1e293b;'
                'border-radius:12px;padding:20px 24px;">'
            )
            for label, val in rows:
                summary_html += (
                    f'<div class="exec-row">'
                    f'<span class="exec-label">{label}</span>'
                    f'<span class="exec-value">{val}</span>'
                    f"</div>"
                )
            summary_html += "</div>"
            st.markdown(summary_html, unsafe_allow_html=True)


# ┌───────────────────────────────────────────────────────────────────────┐
# │ A. EXECUTIVE OVERVIEW                                                 │
# └───────────────────────────────────────────────────────────────────────┘
with tab_overview:
    if df.empty:
        empty_state(
            "📭 No Data to Show",
            "No data matches the current filters. Adjust the sidebar filters.",
        )
    else:
        # ── KPI Cards ──────────────────────────────────────────────────────
        st.markdown('<div class="section-title">Key Performance Indicators</div>', unsafe_allow_html=True)

        total = m.total_samples(df)
        done = m.completed_samples(df)
        rej = m.rejected_samples(df)
        delayed = m.delayed_samples(df)
        sla_br = m.sla_breach_rate(df)
        avg_tat = m.avg_tat_hours(df)
        avg_cou = m.avg_courier_transit_hours(df)
        avg_lab = m.avg_lab_processing_hours(df)

        _rej_rate_pct = round(rej / total * 100, 1) if total else 0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(kpi("Total Samples", f"{total:,}", "All time in selection"), unsafe_allow_html=True)
        with c2:
            st.markdown(kpi("Completed", f"{done:,}", f"{done/total*100:.1f}% of total" if total else "—"), unsafe_allow_html=True)
        with c3:
            st.markdown(kpi("Rejected", f"{rej:,}", f"{_rej_rate_pct}% rejection rate"), unsafe_allow_html=True)
        with c4:
            st.markdown(kpi("SLA Breach Rate", f"{sla_br}%", "Excl. rejected samples"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        c5, c6, c7, c8 = st.columns(4)
        with c5:
            st.markdown(kpi("Avg Total TAT", f"{avg_tat} hrs", "Collection → Report release"), unsafe_allow_html=True)
        with c6:
            st.markdown(kpi("Avg Courier Transit", f"{avg_cou} hrs", "Pickup → Lab delivery"), unsafe_allow_html=True)
        with c7:
            st.markdown(kpi("Avg Lab Processing", f"{avg_lab} hrs", "Receipt → Test completion"), unsafe_allow_html=True)
        with c8:
            st.markdown(kpi("Delayed Samples", f"{delayed:,}", f"{delayed/total*100:.1f}% of total" if total else "—"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Charts row ─────────────────────────────────────────────────────
        col_donut, col_trend = st.columns([1, 2])

        with col_donut:
            st.markdown('<div class="section-title">Sample Status Split</div>', unsafe_allow_html=True)
            status_counts = df["sample_status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            fig_donut = px.pie(
                status_counts, names="Status", values="Count",
                hole=0.55, color_discrete_sequence=CHART_COLORS,
            )
            fig_donut.update_traces(textinfo="percent+label", pull=[0.03] * len(status_counts))
            fig_donut = apply_chart_style(fig_donut, height=320)
            fig_donut.update_layout(showlegend=False)
            st.plotly_chart(fig_donut, use_container_width=True)

        with col_trend:
            st.markdown('<div class="section-title">Daily Sample Volume Trend</div>', unsafe_allow_html=True)
            daily = m.daily_volume(df)
            fig_trend = px.line(
                daily, x="collection_date", y="count", color="sample_status",
                markers=True, color_discrete_sequence=CHART_COLORS,
                labels={"collection_date": "Date", "count": "Sample Count", "sample_status": "Status"},
            )
            fig_trend = apply_chart_style(fig_trend, height=320)
            st.plotly_chart(fig_trend, use_container_width=True)

        # ── Priority split ─────────────────────────────────────────────────
        if "priority_flag" in df.columns:
            st.markdown('<div class="section-title">Sample Priority Distribution</div>', unsafe_allow_html=True)
            priority_df = df["priority_flag"].value_counts().reset_index()
            priority_df.columns = ["Priority", "Count"]
            fig_priority = px.bar(
                priority_df, x="Priority", y="Count",
                color="Priority", color_discrete_sequence=CHART_COLORS,
                labels={"Count": "Number of Samples"},
                text="Count",
            )
            fig_priority.update_traces(textposition="outside")
            fig_priority = apply_chart_style(fig_priority, height=280)
            fig_priority.update_layout(showlegend=False)
            st.plotly_chart(fig_priority, use_container_width=True)


# ┌───────────────────────────────────────────────────────────────────────┐
# │ B. LAB PERFORMANCE                                                    │
# └───────────────────────────────────────────────────────────────────────┘
with tab_lab:
    if df.empty:
        empty_state("📭 No Data to Show", "No data matches the current filters.")
    elif "lab_name" not in df.columns or df["lab_name"].isnull().all():
        empty_state("⚠️ Lab data unavailable", "Lab information is incomplete or missing. Upload lab data or map the lab column.")
    else:
        lab_df = m.lab_summary(df)

        st.markdown('<div class="section-title">Samples Handled by Lab</div>', unsafe_allow_html=True)
        fig_lab_vol = px.bar(
            lab_df, x="lab_name", y="sample_count",
            color="sample_count", color_continuous_scale="Blues",
            labels={"lab_name": "Lab", "sample_count": "Sample Count"},
            text="sample_count",
        )
        fig_lab_vol.update_traces(textposition="outside")
        fig_lab_vol = apply_chart_style(fig_lab_vol)
        fig_lab_vol.update_coloraxes(showscale=False)
        st.plotly_chart(fig_lab_vol, use_container_width=True)

        col_tat, col_rej = st.columns(2)

        with col_tat:
            st.markdown('<div class="section-title">Avg TAT by Lab (hrs)</div>', unsafe_allow_html=True)
            fig_tat = px.bar(
                lab_df.dropna(subset=["avg_tat_hours"]),
                x="avg_tat_hours", y="lab_name", orientation="h",
                color="avg_tat_hours", color_continuous_scale="Blues",
                labels={"avg_tat_hours": "Avg TAT (hrs)", "lab_name": "Lab"},
                text="avg_tat_hours",
            )
            fig_tat.update_traces(texttemplate="%{text:.1f}h", textposition="outside")
            fig_tat = apply_chart_style(fig_tat)
            fig_tat.update_coloraxes(showscale=False)
            st.plotly_chart(fig_tat, use_container_width=True)

        with col_rej:
            st.markdown('<div class="section-title">Rejection Rate by Lab (%)</div>', unsafe_allow_html=True)
            lab_df["rej_status"] = lab_df["rejection_rate_pct"].apply(
                lambda x: "Poor (>10%)" if x > 10 else ("Warning (>5%)" if x > 5 else "Good (≤5%)")
            )
            fig_rej = px.bar(
                lab_df,
                x="rejection_rate_pct", y="lab_name", orientation="h",
                color="rej_status",
                color_discrete_map={"Poor (>10%)": "#ef4444", "Warning (>5%)": "#f59e0b", "Good (≤5%)": "#10b981"},
                labels={"rejection_rate_pct": "Rejection Rate (%)", "lab_name": "Lab"},
                text="rejection_rate_pct",
            )
            fig_rej.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_rej = apply_chart_style(fig_rej)
            fig_rej.update_layout(showlegend=False)
            st.plotly_chart(fig_rej, use_container_width=True)

        st.markdown('<div class="section-title">SLA Breach Rate by Lab (%)</div>', unsafe_allow_html=True)
        lab_df["sla_status"] = lab_df["sla_breach_rate_pct"].apply(
            lambda x: "Poor (>10%)" if x > 10 else ("Warning (>5%)" if x > 5 else "Good (≤5%)")
        )
        fig_sla = px.bar(
            lab_df,
            x="lab_name", y="sla_breach_rate_pct",
            color="sla_status",
            color_discrete_map={"Poor (>10%)": "#ef4444", "Warning (>5%)": "#f59e0b", "Good (≤5%)": "#10b981"},
            labels={"lab_name": "Lab", "sla_breach_rate_pct": "SLA Breach Rate (%)"},
            text="sla_breach_rate_pct",
        )
        fig_sla.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_sla = apply_chart_style(fig_sla)
        fig_sla.update_layout(showlegend=False)
        st.plotly_chart(fig_sla, use_container_width=True)

        if "capacity_per_day" in df.columns and not df["capacity_per_day"].isnull().all():
            st.markdown('<div class="section-title">Lab Load Summary</div>', unsafe_allow_html=True)
            cap_df = df.groupby("lab_name", as_index=False).agg(
                total_samples=("sample_id", "count"),
                capacity_per_day=("capacity_per_day", "first"),
            )
            cap_df["capacity_per_day"] = pd.to_numeric(cap_df["capacity_per_day"], errors='coerce')
            try:
                days = max(1, (d_end - d_start).days + 1) if d_start and d_end else 21
            except Exception:
                days = 21
            cap_df["avg_daily_samples"] = (cap_df["total_samples"] / days).round(1)
            cap_df["load_pct"] = (cap_df["avg_daily_samples"] / cap_df["capacity_per_day"] * 100).astype(float).round(1)
            cap_df["status"] = cap_df["load_pct"].apply(
                lambda x: "🔴 Overloaded" if x > 80 else ("🟡 Near Capacity" if x > 60 else "🟢 Normal")
            )
            st.dataframe(
                cap_df[["lab_name", "total_samples", "capacity_per_day", "avg_daily_samples", "load_pct", "status"]]
                .rename(columns={
                    "lab_name": "Lab", "total_samples": "Total Samples",
                    "capacity_per_day": "Daily Capacity", "avg_daily_samples": "Avg Daily Samples",
                    "load_pct": "Load %", "status": "Status",
                }),
                width="stretch", hide_index=True,
            )


# ┌───────────────────────────────────────────────────────────────────────┐
# │ C. COURIER PERFORMANCE                                                │
# └───────────────────────────────────────────────────────────────────────┘
with tab_courier:
    if df.empty:
        empty_state("📭 No Data to Show", "No data matches the current filters.")
    elif "courier_name" not in df.columns or df["courier_name"].isnull().all():
        empty_state("⚠️ Courier data unavailable", "Courier information is incomplete or missing. Upload tracking data or map the courier column.")
    else:
        cou_df = m.courier_summary(df)

        st.markdown('<div class="section-title">Samples Transported by Courier</div>', unsafe_allow_html=True)
        fig_cou_vol = px.bar(
            cou_df, x="courier_name", y="sample_count",
            color="sample_count", color_continuous_scale="Blues",
            labels={"courier_name": "Courier", "sample_count": "Samples"},
            text="sample_count",
        )
        fig_cou_vol.update_traces(textposition="outside")
        fig_cou_vol = apply_chart_style(fig_cou_vol)
        fig_cou_vol.update_coloraxes(showscale=False)
        st.plotly_chart(fig_cou_vol, use_container_width=True)

        col_transit, col_delay = st.columns(2)

        with col_transit:
            st.markdown('<div class="section-title">Avg Transit Time by Courier (hrs)</div>', unsafe_allow_html=True)
            fig_transit = px.bar(
                cou_df.dropna(subset=["avg_transit_hours"]),
                x="avg_transit_hours", y="courier_name", orientation="h",
                color="avg_transit_hours", color_continuous_scale="Blues",
                labels={"avg_transit_hours": "Avg Transit (hrs)", "courier_name": "Courier"},
                text="avg_transit_hours",
            )
            fig_transit.update_traces(texttemplate="%{text:.2f}h", textposition="outside")
            fig_transit = apply_chart_style(fig_transit)
            fig_transit.update_coloraxes(showscale=False)
            st.plotly_chart(fig_transit, use_container_width=True)

        with col_delay:
            st.markdown('<div class="section-title">Delay Rate by Courier (%)</div>', unsafe_allow_html=True)
            cou_df["delay_status"] = cou_df["delay_rate_pct"].apply(
                lambda x: "Poor (>10%)" if x > 10 else ("Warning (>5%)" if x > 5 else "Good (≤5%)")
            )
            fig_delay = px.bar(
                cou_df,
                x="delay_rate_pct", y="courier_name", orientation="h",
                color="delay_status",
                color_discrete_map={"Poor (>10%)": "#ef4444", "Warning (>5%)": "#f59e0b", "Good (≤5%)": "#10b981"},
                labels={"delay_rate_pct": "Delay Rate (%)", "courier_name": "Courier"},
                text="delay_rate_pct",
            )
            fig_delay.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_delay = apply_chart_style(fig_delay)
            fig_delay.update_layout(showlegend=False)
            st.plotly_chart(fig_delay, use_container_width=True)

        st.markdown('<div class="section-title">SLA Compliance by Courier (%)</div>', unsafe_allow_html=True)
        fig_on_time = px.bar(
            cou_df,
            x="courier_name", y="on_time_rate_pct",
            color="on_time_rate_pct", color_continuous_scale="Greens",
            labels={"courier_name": "Courier", "on_time_rate_pct": "On-Time Rate (%)"},
            text="on_time_rate_pct",
        )
        fig_on_time.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_on_time = apply_chart_style(fig_on_time)
        fig_on_time.update_coloraxes(showscale=False)
        st.plotly_chart(fig_on_time, use_container_width=True)

        st.markdown('<div class="section-title">Courier Summary Table</div>', unsafe_allow_html=True)
        st.dataframe(
            cou_df.rename(columns={
                "courier_name": "Courier", "sample_count": "Samples",
                "avg_transit_hours": "Avg Transit (hrs)",
                "delay_rate_pct": "Delay Rate (%)", "on_time_rate_pct": "On-Time Rate (%)",
            }),
            width="stretch", hide_index=True,
        )


# ┌───────────────────────────────────────────────────────────────────────┐
# │ D. TEST TYPE ANALYTICS                                                │
# └───────────────────────────────────────────────────────────────────────┘
with tab_test:
    if df.empty:
        empty_state("📭 No Data to Show", "No data matches the current filters.")
    elif "test_name" not in df.columns or df["test_name"].isnull().all():
        empty_state("⚠️ Test type data unavailable", "Test type information is incomplete or missing. Upload test data or map the test column.")
    else:
        test_df = m.test_type_summary(df)

        st.markdown('<div class="section-title">Volume by Test Type</div>', unsafe_allow_html=True)

        color_kw: dict = {}
        if "is_critical_test" in test_df.columns:
            color_kw = {
                "color": "is_critical_test",
                "color_discrete_map": {True: "#f472b6", False: "#38bdf8"},
            }
        fig_tvol = px.bar(
            test_df, x="test_name", y="sample_count",
            labels={"test_name": "Test", "sample_count": "Samples", "is_critical_test": "Critical?"},
            text="sample_count",
            **color_kw,
        )
        fig_tvol.update_traces(textposition="outside")
        fig_tvol = apply_chart_style(fig_tvol)
        st.plotly_chart(fig_tvol, use_container_width=True)

        col_tat2, col_rej2 = st.columns(2)

        with col_tat2:
            st.markdown('<div class="section-title">Avg TAT by Test Type (hrs)</div>', unsafe_allow_html=True)
            fig_ttat = px.bar(
                test_df.dropna(subset=["avg_tat_hours"]).sort_values("avg_tat_hours", ascending=False),
                x="avg_tat_hours", y="test_name", orientation="h",
                color="avg_tat_hours", color_continuous_scale="Blues",
                labels={"avg_tat_hours": "Avg TAT (hrs)", "test_name": "Test"},
                text="avg_tat_hours",
            )
            fig_ttat.update_traces(texttemplate="%{text:.1f}h", textposition="outside")
            fig_ttat = apply_chart_style(fig_ttat, height=380)
            fig_ttat.update_coloraxes(showscale=False)
            st.plotly_chart(fig_ttat, use_container_width=True)

        with col_rej2:
            st.markdown('<div class="section-title">Rejection Rate by Test Type (%)</div>', unsafe_allow_html=True)
            test_df["rej_status"] = test_df["rejection_rate_pct"].apply(
                lambda x: "Poor (>10%)" if x > 10 else ("Warning (>5%)" if x > 5 else "Good (≤5%)")
            )
            fig_trej = px.bar(
                test_df.sort_values("rejection_rate_pct", ascending=False),
                x="rejection_rate_pct", y="test_name", orientation="h",
                color="rej_status",
                color_discrete_map={"Poor (>10%)": "#ef4444", "Warning (>5%)": "#f59e0b", "Good (≤5%)": "#10b981"},
                labels={"rejection_rate_pct": "Rejection Rate (%)", "test_name": "Test"},
                text="rejection_rate_pct",
            )
            fig_trej.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_trej = apply_chart_style(fig_trej, height=380)
            fig_trej.update_layout(showlegend=False)
            st.plotly_chart(fig_trej, use_container_width=True)

        if "is_critical_test" in test_df.columns:
            st.markdown('<div class="section-title">Critical vs Normal Tests</div>', unsafe_allow_html=True)
            crit_df = test_df.copy()
            crit_df["type"] = crit_df["is_critical_test"].map({True: "Critical", False: "Normal"})
            crit_sum = crit_df.groupby("type", as_index=False)["sample_count"].sum()
            fig_crit = px.bar(
                crit_sum, x="type", y="sample_count",
                color="type", color_discrete_map={"Critical": "#f472b6", "Normal": "#38bdf8"},
                labels={"type": "Test Category", "sample_count": "Sample Count"},
                text="sample_count",
            )
            fig_crit.update_traces(textposition="outside")
            fig_crit = apply_chart_style(fig_crit, height=280)
            fig_crit.update_layout(showlegend=False)
            st.plotly_chart(fig_crit, use_container_width=True)


# ┌───────────────────────────────────────────────────────────────────────┐
# │ E. SAMPLE JOURNEY DETAIL                                              │
# └───────────────────────────────────────────────────────────────────────┘
with tab_journey:
    if df.empty:
        empty_state("📭 No Data to Show", "No data matches the current filters.")
    else:
        st.markdown('<div class="section-title">Full Sample Journey — Filterable Detail Table</div>', unsafe_allow_html=True)
        st.caption(
            "Each row represents one sample's complete lifecycle: "
            "collection → pickup → delivery → lab receipt → testing → report release."
        )

        search_id = st.text_input("🔍 Search by Sample ID (e.g. SMP000042)", value="")

        journey_cols = [
            "sample_id", "test_name", "city", "lab_name", "courier_name",
            "sample_status", "priority_flag",
            "sample_collected_at", "pickup_time", "delivery_time",
            "lab_received_at", "test_started_at", "test_completed_at", "report_released_at",
            "courier_transit_hours", "lab_processing_hours", "total_tat_hours",
            "promised_tat_hours", "sla_breach", "rejection_reason",
        ]
        available_cols = [c for c in journey_cols if c in df.columns]
        jdf = df[available_cols].copy()

        if search_id.strip():
            jdf = jdf[jdf["sample_id"].str.contains(search_id.strip(), case=False, na=False)]

        for col in ["courier_transit_hours", "lab_processing_hours", "total_tat_hours"]:
            if col in jdf.columns:
                jdf[col] = jdf[col].round(2)

        rename_map = {
            "sample_id": "Sample ID", "test_name": "Test", "city": "City",
            "lab_name": "Lab", "courier_name": "Courier",
            "sample_status": "Status", "priority_flag": "Priority",
            "sample_collected_at": "Collected At", "pickup_time": "Pickup Time",
            "delivery_time": "Delivery Time", "lab_received_at": "Lab Received At",
            "test_started_at": "Test Started", "test_completed_at": "Test Completed",
            "report_released_at": "Report Released",
            "courier_transit_hours": "Transit (hrs)", "lab_processing_hours": "Lab Processing (hrs)",
            "total_tat_hours": "Total TAT (hrs)", "promised_tat_hours": "Promised TAT (hrs)",
            "sla_breach": "SLA Breach", "rejection_reason": "Rejection Reason",
        }
        jdf = jdf.rename(columns={k: v for k, v in rename_map.items() if k in jdf.columns})

        def _style_status(val):
            if val == "Rejected":
                return "color: #ef4444; font-weight: 600"
            elif val == "Delayed":
                return "color: #f59e0b; font-weight: 500"
            elif val == "Completed":
                return "color: #10b981"
            return ""

        if "Status" in jdf.columns:
            styled_jdf = jdf.style.map(_style_status, subset=["Status"])
        else:
            styled_jdf = jdf.style

        st.dataframe(styled_jdf, width="stretch", hide_index=True, height=480)
        st.caption(
            f"Showing **{len(jdf):,}** records. "
            "Use the sidebar filters or the search box above to narrow down."
        )

# ═══════════════════════════════════════════════════════════════════════════
# Footer
# ═══════════════════════════════════════════════════════════════════════════
mode_str = "Upload Mode — Your Data" if IS_UPLOAD_MODE else "Demo Mode — Synthetic Data"
st.markdown(
    f"""
    <div style="text-align:center;color:#475569;font-size:0.78rem;margin-top:40px;padding-top:16px;
                border-top:1px solid #1e293b;">
        Diagnostic Lab Operational Analytics · Powered by Streamlit &amp; Plotly ·
        {mode_str} · <strong>No cloud dependencies</strong>
    </div>
    """,
    unsafe_allow_html=True,
)
