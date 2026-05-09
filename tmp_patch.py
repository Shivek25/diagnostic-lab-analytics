import re

with open("d:/College_Work/E2E_DataEngineeringProject/app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add schema_mapper import
if "schema_mapper" not in content:
    content = content.replace(
        "from utils import templates as tmpl",
        "from utils import templates as tmpl\nfrom utils.schema_mapper import CANONICAL_SCHEMA, infer_mapping, normalize_dataframe, merge_normalized_dfs"
    )

# 2. Replace the upload mode section
old_block_start = r"# ═══════════════════════════════════════════════════════════════════════════\n# Upload Mode — File Uploaders \(rendered in sidebar\)"
old_block_end = r"else:\n    # ── Demo Mode — load synthetic data"

# We use regex to find this entire block
pattern = re.compile(old_block_start + r".*?(?=else:\n    # ── Demo Mode)", re.DOTALL)

new_block = """# ═══════════════════════════════════════════════════════════════════════════
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
                raw_dfs[uf.name] = pd.read_csv(uf, sep='\\t')
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

"""

content = pattern.sub(new_block, content)

# Remove the old status validation panels since we do it inside mapping wizard now.
validation_panel_start = r"# ═══════════════════════════════════════════════════════════════════════════\n# Upload Mode — validation status panel"
validation_panel_end = r"# ═══════════════════════════════════════════════════════════════════════════\n# Tabs"

pattern2 = re.compile(validation_panel_start + r".*?(?=" + validation_panel_end + ")", re.DOTALL)
content = pattern2.sub("", content)

with open("d:/College_Work/E2E_DataEngineeringProject/app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patched app.py")
