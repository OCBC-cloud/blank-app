import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="SDS Chamber 002 – Steward Console",
    page_icon="🌱",
    layout="wide"
)

# --- Supabase Credentials ---
SUPABASE_URL = "https://pcijgufnjeijqqywubpu.supabase.co"
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- App Title ---
st.title("🌱 SDS Chamber 002 – Steward Console")
st.caption("Nutrient Cycle Management | KPI Ingestion & Adaptation Binding")

# --- Sidebar Status ---
with st.sidebar:
    st.header("📊 System Status")
    st.success("✅ Connected to Supabase")
    st.info("Phase 1: Manual Mode")
    st.caption("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M"))

# --- Tabs ---
tab1, tab2, tab3 = st.tabs(["📤 Upload KPI Data", "🔗 Bind Adaptation", "📋 View Bindings"])

# ============================================================================
# TAB 1: UPLOAD KPI DATA
# ============================================================================
with tab1:
    st.header("📤 Upload KPI Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        uploaded_file = st.file_uploader(
            "Choose CSV or Excel file",
            type=["csv", "xlsx"],
            help="File must contain columns: workfront_id, kpi_name, value, recorded_at"
        )
    
    with col2:
        st.markdown("### 📋 Required Format")
        st.code("""
workfront_id | kpi_name | value | recorded_at
-------------|----------|-------|------------
uuid_here    | TRIR     | 2.5   | 2026-01-15
uuid_here    | SPI      | 1.02  | 2026-01-15
        """)
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            
            st.subheader("📄 Preview (first 5 rows)")
            st.dataframe(df.head())
            
            required_cols = ['workfront_id', 'kpi_name', 'value', 'recorded_at']
            missing = [col for col in required_cols if col not in df.columns]
            
            if missing:
                st.error(f"❌ Missing columns: {missing}")
            else:
                if st.button("🚀 Upload to Database", type="primary"):
                    with st.spinner("Uploading..."):
                        try:
                            kpi_response = supabase.table('kpi_definitions').select('id, name').execute()
                            kpi_map = {row['name']: row['id'] for row in kpi_response.data}
                            
                            inserted = 0
                            errors = []
                            
                            for _, row in df.iterrows():
                                kpi_id = kpi_map.get(row['kpi_name'])
                                if not kpi_id:
                                    errors.append(f"Unknown KPI: {row['kpi_name']}")
                                    continue
                                
                                data = {
                                    'workfront_id': row['workfront_id'],
                                    'kpi_definition_id': kpi_id,
                                    'value': float(row['value']),
                                    'recorded_at': str(row['recorded_at'])
                                }
                                
                                supabase.table('kpi_values').insert(data).execute()
                                inserted += 1
                            
                            if errors:
                                st.warning(f"⚠️ Uploaded {inserted} rows. Errors: {', '.join(errors[:5])}")
                            else:
                                st.success(f"✅ Successfully uploaded {inserted} rows!")
                                
                        except Exception as e:
                            st.error(f"❌ Upload error: {e}")
                            
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")

# ============================================================================
# TAB 2: BIND ADAPTATION TO KPI
# ============================================================================
with tab2:
    st.header("🔗 Bind Adaptation to KPI")
    
    col1, col2 = st.columns(2)
    
    with col1:
        adaptation_name = st.text_input("Adaptation Name", placeholder="e.g., Concrete Mix Optimization")
        adaptation_desc = st.text_area("Description", placeholder="Brief description of the adaptation...")
        
        kpi_response = supabase.table('kpi_definitions').select('id, name, unit, direction').execute()
        kpi_options = [f"{row['name']} ({row['unit']})" for row in kpi_response.data]
        
        selected_kpi = st.selectbox("Select KPI", kpi_options if kpi_options else ["No KPIs found"])
        
    with col2:
        st.markdown("### 📊 Baseline & Threshold")
        baseline = st.number_input("Baseline Value", value=0.0, step=0.01)
        mnm = st.number_input("MNM Threshold", value=0.0, step=0.01, help="Measurement Noise Margin")
        bound_by = st.text_input("Bound By (Your Name)", placeholder="Your name or ID")
    
    if st.button("💾 Create Binding", type="primary"):
        if not adaptation_name or not bound_by:
            st.error("❌ Please fill in Adaptation Name and Bound By fields.")
        elif selected_kpi == "No KPIs found":
            st.error("❌ No KPIs found in database. Please insert KPI definitions first.")
        else:
            try:
                kpi_name = selected_kpi.split(" (")[0]
                kpi_id = next(row['id'] for row in kpi_response.data if row['name'] == kpi_name)
                
                adapt_result = supabase.table('adaptations').insert({
                    'name': adaptation_name,
                    'description': adaptation_desc,
                    'status': 'active'
                }).execute()
                
                adaptation_id = adapt_result.data[0]['id']
                
                supabase.table('adaptation_kpi_binding').insert({
                    'adaptation_id': adaptation_id,
                    'kpi_definition_id': kpi_id,
                    'baseline_value': baseline,
                    'mnm_threshold': mnm,
                    'bound_by': bound_by
                }).execute()
                
                st.success(f"✅ Binding created successfully!")
                st.info(f"Adaptation: {adaptation_name} → {kpi_name}")
                st.caption(f"Baseline: {baseline} | MNM: {mnm}")
                
            except Exception as e:
                st.error(f"❌ Error creating binding: {e}")

# ============================================================================
# TAB 3: VIEW BINDINGS
# ============================================================================
with tab3:
    st.header("📋 Current Adaptation-KPI Bindings")
    
    try:
        result = supabase.table('adaptation_kpi_binding').select(
            'id, baseline_value, mnm_threshold, bound_at, bound_by, '
            'adaptations(name, status), '
            'kpi_definitions(name, unit)'
        ).execute()
        
        bindings = result.data
        
        if bindings:
            rows = []
            for b in bindings:
                rows.append({
                    'Adaptation': b['adaptations']['name'],
                    'KPI': b['kpi_definitions']['name'],
                    'Unit': b['kpi_definitions']['unit'],
                    'Baseline': b['baseline_value'],
                    'MNM': b['mnm_threshold'],
                    'Bound By': b['bound_by'],
                    'Bound At': b['bound_at'][:10] if b['bound_at'] else 'N/A',
                    'Status': b['adaptations']['status']
                })
            
            df_bindings = pd.DataFrame(rows)
            st.dataframe(df_bindings, use_container_width=True)
            
            st.subheader("📊 Summary")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Bindings", len(bindings))
            with col2:
                active = sum(1 for b in bindings if b['adaptations']['status'] == 'active')
                st.metric("Active Adaptations", active)
            with col3:
                unique_kpis = len(set(b['kpi_definitions']['name'] for b in bindings))
                st.metric("Unique KPIs Used", unique_kpis)
                
        else:
            st.info("No bindings found. Go to the 'Bind Adaptation' tab to create one.")
            
    except Exception as e:
        st.error(f"❌ Error fetching bindings: {e}")

# --- Footer ---
st.divider()
st.caption("🧬 Knowledge may evolve. 🌱 Identity shall remain.")
st.caption("SDS Chamber 002 – Phase 1 (Manual Mode)")
