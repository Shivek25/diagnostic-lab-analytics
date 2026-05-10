# 🏥 Diagnostic Lab Operational Analytics & Sample Logistics Platform

An end-to-end data engineering and analytics solution designed for private diagnostic lab chains. This platform tracks the full lifecycle of medical samples; from collection and courier movement to lab processing and final report release. 

By unifying fragmented operational data, this project provides a single consolidated view to monitor delays, identify bottlenecks, measure turnaround times, and improve overall operational reliability.

---

## 🚀 Project Overview

In a typical diagnostic lab environment, tracking sample movement and operational performance is often managed through disconnected tools or manual registers. This results in poor visibility into where delays occur or which parts of the process are failing.

This project solves this by building a centralized analytics pipeline that answers critical business questions:
- How long does each sample take from collection to report release?
- Which labs are performing well, and which are creating delays?
- Which couriers are causing transport delays?
- Which test types are slower, more resource-intensive, or prone to rejection?
- Where are the rejection and SLA breach patterns?

---

## 💡 Problem Statement

Private diagnostic labs generally face several recurring operational challenges:
- Sample movement is tracked manually across fragmented systems.
- Courier delay information is not connected to lab processing data.
- **TAT (Turnaround Time)** is not measured consistently across different labs or test types.
- Rejected samples are not analyzed adequately to determine root causes.
- Management lacks a single consolidated view of sample flow and operational performance.

**The Solution:** A structured data platform with proper ingestion, modeling, quality checks, and reporting, delivering actionable business intelligence.

---

## Tech Stack

### 📊 Local Dashboard (New)
- **Streamlit** — interactive dashboard UI
- **Plotly** — charts and visualisations
- **Pandas** — data manipulation

### 🔧 Data Pipeline (Existing)
- **Python / Faker** — synthetic data generation
- **Google BigQuery** — cloud data warehouse
- **dbt** — SQL transformation and modeling
- **Power BI Desktop** — original reporting layer
- **GitHub** — version control

---

## 📊 Data Model Design

The project uses a **star-schema** style warehouse design.

### Dimension Tables

#### `dim_lab`
Stores lab master information such as:
- lab name
- lab type
- city
- zone
- capacity
- operational status
- 24x7 availability

#### `dim_courier`
Stores courier vendor details such as:
- courier name
- courier type
- service area
- average delivery time
- SLA hours
- cost per km

#### `dim_test_type`
Stores test catalog details such as:
- test name
- test category
- sample type
- expected turnaround time
- cost
- critical test flag

#### `dim_zone`
Stores geographic region information such as:
- zone name
- city
- region type
- traffic level
- priority level

### Source Tables

#### `sample_manifest`
One row per sample. Contains collection and order details.

#### `courier_events`
One row per courier event per sample. Contains pickup and delivery movement.

#### `lab_processing`
One row per sample processing journey. Contains lab receipt, testing, and report timestamps.

### Analytics Tables

#### `int_sample_journey`
Intermediate model that combines sample, courier, and lab processing data into one operational journey view.

#### `fct_sample_journey`
Main fact table containing sample-level journey metrics, flags, and durations.

#### `agg_lab_daily_performance`
Daily lab performance summary.

#### `agg_courier_sla`
Daily courier performance summary.

#### `agg_test_tat`
Daily test-level turnaround and rejection summary.

---

## 📂 Project Structure

```text
E2E_DataEngineeringProject/
│
├── app.py                                # ✅ Streamlit dashboard entry point (NEW)
├── utils/                                # ✅ Dashboard helper modules (NEW)
│   ├── data_loader.py                    #    Loads & merges all CSV files
│   └── metrics.py                        #    Core KPI calculation functions
│
├── docs/                                 # 📚 Extensive Project Documentation
│   ├── project_report.docx               #    Detailed Business & Technical Report
│   ├── client_pitch.md                   #    Client-focused presentation material
│   ├── architecture.md                   #    Application architecture details
│   ├── faq.md                            #    Frequently Asked Questions
│   └── deployment.md                     #    Application Deployment Guide
│
├── Diagnostic Lab Operational Analytics Sample Logistics Project/
│   └── data/
│       ├── raw/                          # sample_manifest, courier_events, lab_processing
│       └── reference/                    # dim_lab, dim_courier, dim_test_type, dim_zone
│
├── dbt/                                  # dbt project (pipeline, untouched)
│   └── diagnostic_lab_ops/
│       └── models/
│           ├── staging/
│           ├── intermediate/
│           └── marts/
│
├── generate_lab_data.py                  # Synthetic data generator
├── requirements.txt                      # ✅ Updated Python dependencies
├── CHECKLIST.md                          # ✅ Quick-start developer checklist (NEW)
├── Lab Ops Analytics Dashboard.pbix      # Power BI Dashboard
└── README.md                             # This file
```

---

## 📚 Documentation

Detailed documentation and presentations have been prepared for this project:
- 📄 **[Project Report](./docs/project_report.docx):** Complete end-to-end breakdown of the business problem, solution, features, and technical architecture.
- 💬 **[Client Pitch](./docs/client_pitch.md):** Pitch material outlining value proposition and business outcomes.
- 🏗️ **[Architecture](./docs/architecture.md):** Application architecture and data workflows.
- ❓ **[FAQ](./docs/faq.md):** Common questions regarding data ingestion, security, and schema matching.

---

## 🔑 Key Metrics

This platform measures:
- Total samples processed
- Completed samples
- Rejected samples
- SLA breach rate
- Average total turnaround time
- Average delivery to lab time
- Courier transit time
- Lab processing time
- Rejection rate by lab and test type
- Delay rate by courier
- TAT by test category

---

## 📈 Power BI Dashboard Highlights

<p align="center"> <img width="600" height="400" alt="image" src="https://github.com/user-attachments/assets/401b472b-42e7-49c9-bd6b-d4ae583a36f6" /> </p>

The final Power BI report acts as a interactive operational monitoring dashboard, divided into key areas:
1. **Executive Overview:** Top-level metrics on total samples, completion rates, SLA breach rates, and overall TAT trends.
2. **Lab Performance:** Focuses on lab efficiency, highlighting overloaded labs, rejection rates, and average processing times.
3. **Courier Performance:** Tracks vendor efficiency, average transit times, and delivery completion rates.
4. **Test Analytics:** Identifies operationally heavy tests, critical test volume, and expected vs. actual TAT.
5. **Sample Journey Detail:** A drill-through view detailing the exact lifecycle and timestamp trace of individual samples.

<p align="center"> <img width="600" height="400" alt="image" src="https://github.com/user-attachments/assets/e01102e7-7131-459f-a42e-e56172ce16ca" /> </p>



---

## ⚙️ How to Run the Project

### 🚀 Quick Start — Local Streamlit Dashboard (No Cloud Required)

**Step 1 — Install dependencies**
```bash
pip install -r requirements.txt
```

**Step 2 — Generate synthetic data** *(skip if CSVs already exist)*
```bash
python generate_lab_data.py
```

**Step 3 — Launch the dashboard**
```bash
streamlit run app.py
```
Browser opens at `http://localhost:8501` with 5 dashboard sections:
- 📊 **Executive Overview** — KPI cards, status donut chart, daily trend
- 🏥 **Lab Performance** — TAT, rejection rate, SLA breach by lab
- 🚚 **Courier Performance** — transit time, delay rate, SLA compliance
- 🔬 **Test Type Analytics** — volume, TAT, rejection rate per test
- 🗺 **Sample Journey** — drillable table of each sample's full lifecycle

See [CHECKLIST.md](./CHECKLIST.md) for the full verification checklist.

---

### ☁️ Full Cloud Pipeline (Advanced — BigQuery + dbt + Power BI)

**Step 1:** Generate CSV files with `python generate_lab_data.py`  
**Step 2:** Load CSVs into BigQuery raw tables  
**Step 3:** Run dbt to build staging → intermediate → mart models  
**Step 4:** Open Power BI and connect to the BigQuery mart layer

---

## 💼 Business Value

This platform helps diagnostic labs:
- improve sample visibility
- identify delay bottlenecks
- track courier SLA performance
- analyze lab productivity
- reduce rejections
- monitor turnaround time
- make data-driven operational decisions

It provides a single source of truth for sample logistics and lab operations.

---

## 🔮 Future Enhancements

Possible next steps include:
- real-time ingestion with Cloud Functions
- automated alerts for SLA breaches
- route optimization for couriers
- hospital or collection-center level drilldowns
- forecasting sample volume by city or zone
- Power BI Service deployment and scheduled refresh

---

## 🔒 Data Privacy

All data in this project is synthetic and de-identified.  
No real patient names, phone numbers, or personal medical data are used.  
This makes the project safe for portfolio, demo, and client discussion purposes.

---

**Author**  
Shivek
