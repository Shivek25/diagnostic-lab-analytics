"""
insights.py
-----------
Generates dynamic text insights and executive operational summaries
based on current dashboard data.
"""

import pandas as pd
from utils import metrics as m


def generate_insights(df: pd.DataFrame) -> list[str]:
    """Analyze the dataframe and return a list of actionable insights."""
    if df.empty:
        return ["No data available for insights."]

    insights = []

    # 1. Lab with highest rejection rate
    lab_df = m.lab_summary(df)
    if not lab_df.empty:
        # Filter to labs with at least 10 samples to avoid noise
        valid_labs = lab_df[lab_df["sample_count"] >= 10]
        if valid_labs.empty:
            valid_labs = lab_df  # fallback

        worst_lab = valid_labs.sort_values("rejection_rate_pct", ascending=False).iloc[0]
        if worst_lab["rejection_rate_pct"] > 0:
            insights.append(
                f"🚨 **{worst_lab['lab_name']}** has the highest rejection rate at "
                f"**{worst_lab['rejection_rate_pct']:.1f}%** (based on {worst_lab['sample_count']} samples)."
            )

    # 2. Courier with highest delay rate
    cou_df = m.courier_summary(df)
    if not cou_df.empty:
        valid_cou = cou_df[cou_df["sample_count"] >= 10]
        if valid_cou.empty:
            valid_cou = cou_df

        worst_cou = valid_cou.sort_values("delay_rate_pct", ascending=False).iloc[0]
        if worst_cou["delay_rate_pct"] > 0:
            insights.append(
                f"🚚 **{worst_cou['courier_name']}** has the highest delay rate at "
                f"**{worst_cou['delay_rate_pct']:.1f}%**."
            )

    # 3. Test with longest TAT
    test_df = m.test_type_summary(df)
    if not test_df.empty:
        longest_test = test_df.sort_values("avg_tat_hours", ascending=False).iloc[0]
        if pd.notna(longest_test["avg_tat_hours"]) and longest_test["avg_tat_hours"] > 0:
            insights.append(
                f"⏳ **{longest_test['test_name']}** has the longest average turnaround time "
                f"(**{longest_test['avg_tat_hours']:.1f} hrs**)."
            )

    # 4. City with most delays
    delays_df = m.get_delayed_samples_df(df)
    if not delays_df.empty and "city" in delays_df.columns:
        city_delays = delays_df["city"].value_counts()
        if not city_delays.empty:
            worst_city = city_delays.index[0]
            count = city_delays.iloc[0]
            insights.append(
                f"🏙️ **{worst_city}** leads in delayed samples (**{count}** delayed samples)."
            )

    # General fallback if everything is perfect
    if not insights:
        insights.append("✅ All systems operating normally within selected filters.")

    return insights


def generate_executive_summary(df: pd.DataFrame) -> dict:
    """
    Generate a plain-English operational summary for management.

    Returns a dict with keys mapping to human-readable strings:
      - total_samples
      - delay_rate
      - rejection_rate
      - sla_breach_rate
      - avg_tat
      - highest_rejection_lab
      - slowest_courier
      - most_delayed_test
      - top_delayed_city
    """
    if df.empty:
        return {}

    total = m.total_samples(df)
    delayed = m.delayed_samples(df)
    rejected = m.rejected_samples(df)
    sla_br = m.sla_breach_rate(df)
    avg_tat = m.avg_tat_hours(df)

    delay_rate = round(delayed / total * 100, 1) if total else 0.0
    rej_rate = round(rejected / total * 100, 1) if total else 0.0

    summary: dict = {
        "total_samples": f"{total:,}",
        "delay_rate": f"{delay_rate}%",
        "rejection_rate": f"{rej_rate}%",
        "sla_breach_rate": f"{sla_br}%",
        "avg_tat": f"{avg_tat} hrs",
    }

    # Highest rejection lab
    lab_df = m.lab_summary(df)
    if not lab_df.empty:
        worst = lab_df.sort_values("rejection_rate_pct", ascending=False).iloc[0]
        summary["highest_rejection_lab"] = (
            f"{worst['lab_name']} ({worst['rejection_rate_pct']:.1f}%)"
        )
    else:
        summary["highest_rejection_lab"] = "N/A"

    # Slowest courier (by avg transit time)
    cou_df = m.courier_summary(df)
    if not cou_df.empty:
        slowest = cou_df.dropna(subset=["avg_transit_hours"]).sort_values(
            "avg_transit_hours", ascending=False
        )
        if not slowest.empty:
            row = slowest.iloc[0]
            summary["slowest_courier"] = (
                f"{row['courier_name']} ({row['avg_transit_hours']:.1f} hrs avg transit)"
            )
        else:
            summary["slowest_courier"] = "N/A"
    else:
        summary["slowest_courier"] = "N/A"

    # Most delayed test type
    test_df = m.test_type_summary(df)
    if not test_df.empty:
        worst_test = test_df.dropna(subset=["avg_tat_hours"]).sort_values(
            "avg_tat_hours", ascending=False
        )
        if not worst_test.empty:
            trow = worst_test.iloc[0]
            summary["most_delayed_test"] = (
                f"{trow['test_name']} ({trow['avg_tat_hours']:.1f} hrs avg TAT)"
            )
        else:
            summary["most_delayed_test"] = "N/A"
    else:
        summary["most_delayed_test"] = "N/A"

    # Top city by delayed samples
    delays_df = m.get_delayed_samples_df(df)
    if not delays_df.empty and "city" in delays_df.columns:
        city_counts = delays_df["city"].value_counts()
        if not city_counts.empty:
            summary["top_delayed_city"] = (
                f"{city_counts.index[0]} ({city_counts.iloc[0]} delayed samples)"
            )
        else:
            summary["top_delayed_city"] = "N/A"
    else:
        summary["top_delayed_city"] = "N/A"

    return summary
