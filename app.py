import streamlit as st
import pandas as pd
import io
import math

# 1. SETUP & STYLE
st.set_page_config(page_title="Celinski Coffee Solver", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@700&display=swap');
    .stApp { background-color: #D2B48C; }
    html, body, [class*="st-"], div, p, h1, h2, h3, label, span {
        font-family: 'Quicksand', sans-serif !important;
        color: #000000 !important;
        font-weight: 700 !important;
    }
    [data-testid="stFileUploader"], [data-testid="stSidebar"], .stButton>button, 
    [data-testid="stMetric"], .stTabs, [data-baseweb="tab-panel"], 
    [data-testid="stHeader"], .stTabs [data-baseweb="tab-list"],
    [data-testid="stFileUploadDropzone"] {
        background-color: #E6D5B8 !important; 
        border-radius: 10px;
        color: #000000 !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("Celinski's Coffee Solver »")

# 2. FILE UPLOADER & THE "PIPE" REPAIR
uploaded_file = st.file_uploader("Upload your full POS CSV or Excel file", type=["csv", "xlsx"])

df = None
if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            raw_bytes = uploaded_file.getvalue()
            raw_text = raw_bytes.decode("utf-8-sig", errors="ignore")
            
            # Detect Delimiter (Pipe or Comma)
            first_line = raw_text.split('\n')[0]
            if '|' in first_line:
                df = pd.read_csv(io.StringIO(raw_text), sep='|')
            else:
                df = pd.read_csv(io.StringIO(raw_text))
        else:
            df = pd.read_excel(uploaded_file)
        
        # Standardize headers to lower case strings
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # STRICT MAPPING - This prevents the "not 1-dimensional" error
        name_map = {}
        for c in df.columns:
            if 'product_detail' in c or 'item' in c: name_map[c] = 'item'
            elif 'transaction_qty' in c or 'quantity' in c: name_map[c] = 'quantity'
            elif 'unit_price' in c or 'price' in c: name_map[c] = 'price'
            elif 'transaction_date' in c or 'date' in c: name_map[c] = 'date'
        
        # If the map only has some keys, we rename what we found
        df = df.rename(columns=name_map)
        
        # Ensure we ONLY have the renamed columns to avoid duplicates
        needed = ['item', 'quantity', 'price']
        if all(col in df.columns for col in needed):
            # If multiple columns were renamed to 'item', just take the first one
            df = df.loc[:, ~df.columns.duplicated()]
            
            for col in ['quantity', 'price']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            st.error(f"Missing columns. Found: {list(df.columns)}")
            df = None
                
    except Exception as e:
        st.error(f"File Processing Error: {e}")

# 3. PRICING ENGINE
if df is not None and 'item' in df.columns:
    # Aggregation
    summary = df.groupby('item').agg({'quantity': 'sum', 'price': 'mean'}).reset_index()
    summary.rename(columns={'item': 'Item Name', 'quantity': 'Units Sold', 'price': 'Current Price'}, inplace=True)

    def run_optimization(row):
        current_rev = row['Current Price'] * row['Units Sold']
        if row['Units Sold'] > 35:
            new_price = row['Current Price'] + 0.50
            return new_price, (new_price * row['Units Sold']) - current_rev, 0
        elif row['Units Sold'] < 10:
            new_price = max(0.50, row['Current Price'] - 0.50)
            extra_units = row['Units Sold'] * 0.20 
            new_rev = new_price * (row['Units Sold'] + extra_units)
            return new_price, max(0, new_rev - current_rev), extra_units
        return row['Current Price'], 0, 0

    results = summary.apply(run_optimization, axis=1)
    summary['AI Suggested Price'] = [x[0] for x in results]
    summary['impact_num'] = [x[1] for x in results]
    summary['Proj. Monthly Gain'] = summary['impact_num'].apply(lambda x: f"+${x:,.2f}" if x > 0 else "$0")

    st.subheader("Pricing Strategy")
    st.dataframe(summary[['Item Name', 'Units Sold', 'Current Price', 'AI Suggested Price', 'Proj. Monthly Gain']], use_container_width=True)
    st.metric(label="Projected Monthly Gain Profit", value=f"+${summary['impact_num'].sum():,.2f} Profit")
