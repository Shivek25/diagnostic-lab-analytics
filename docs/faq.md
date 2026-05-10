# Frequently Asked Questions (FAQ)

### 1. Do I need my own database to run this?
No. The current Streamlit application is designed to ingest standard `.csv` exports directly by uploading them to the web interface. There is no cloud database or infrastructure setup required.

### 2. Is patient data secure?
The application is run entirely in memory. It does not store user data to any external server or persistent database. Furthermore, the demo mode only uses completely synthetic data with zero real patient information.

### 3. What if my Laboratory Information System (LIS) has different column names?
The application's **Upload Mode** is designed with a schema-mapping layer. If your input CSV uses names like `pickup_ts` instead of `courier_pickup_time`, the system will attempt to align them.

### 4. Can I export the charts and data?
Yes. The platform provides a native download feature. You can export underlying filtered data or summary metrics out as `.csv` files for further presentation needs.

### 5. How are SLA rules defined?
Current SLA expectations (e.g., transit times, test processing limits) are handled within the core Metrics Engine. For a specific client implementation, these values can easily be parameterized to fit exact contractual commitments.
