import streamlit as st
import pandas as pd
import io
import math

# 1. SETUP & STYLE
st.set_page_config(page_title="Celinski Coffee Solver", layout="wide")

# Custom CSS for the mocha-themed UI
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
                # Fallback for "all-in-one-column" comma issues
                if len(df.columns) == 1 and ',' in str(df.columns[0]):
                    df = pd.read_csv(io.StringIO(raw_text), sep=',')
        else:
            df = pd.read_excel(uploaded_file)
        
        # Standardize headers to lower case strings for matching
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # STRICT MAPPING - Specifically built for your "product_detail" file
        name_map = {}
        for c in df.columns:
            if 'product_detail' in c or 'item' in c or 'product_description' in c: 
                name_map[c] = 'item'
            elif 'transaction_qty' in c or 'quantity' in c or 'qty' in c: 
                name_map[c] = 'quantity'
            elif 'unit_price' in c or 'price' in c or 'unit_rate' in c: 
                name_map[c] = 'price'
            elif 'transaction_date' in c or 'date' in c or 'sale_date' in c: 
                name_map[c] = 'date'
        
        df = df.rename(columns=name_map)
        
        # Deduplicate columns if multiple headers matched the same keyword
        df = df.loc[:, ~df.columns.duplicated()]
        
        # Check for required columns
        needed = ['item', 'quantity', 'price']
        if all(col in df.columns for col in needed):
            for col in ['quantity', 'price']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            st.error(f"Missing required columns. Found: {list(df.columns)}")
            df = None
                
    except Exception as e:
        st.error(f"File Processing Error: {e}")

# 3. PRICING ENGINE WITH PSYCHOLOGICAL GUARDRAILS
if df is not None and 'item' in df.columns:
    summary = df.groupby('item').agg({'quantity': 'sum', 'price': 'mean'}).reset_index()
    summary.rename(columns={'item': 'Item Name', 'quantity': 'Units Sold', 'price': 'Current Price'}, inplace=True)

    def run_optimization(row):
        current_price = row['Current Price']
        units_sold = row['Units Sold']
        current_rev = current_price * units_sold
        current_dollar = math.floor(current_price)
        
        # SCENARIO A: HIGH VOLUME (Increase price)
        if units_sold > 35:
            suggested = current_price + 0.50
            # Guardrail: Don't flip the first digit (e.g., stay at $3.99 instead of $4.05)
            if math.floor(suggested) > current_dollar:
                new_price = current_dollar + 0.99
            else:
                new_price = suggested
            
            # Ensure we never suggest lower than current for high volume
            new_price = max(new_price, current_price)
            return new_price, (new_price * units_sold) - current_rev
        
        # SCENARIO B: LOW VOLUME (Price Drop to test elasticity)
        elif units_sold < 10:
            new_price = max(0.99, current_price - 0.50)
            extra_units = units_sold * 0.20 # Assume 20% volume increase from drop
            new_rev = new_price * (units_sold + extra_units)
            # Only return gain if the new revenue is actually higher
            gain = max(0, new_rev - current_rev)
            return new_price, gain
            
        return current_price, 0

    results = summary.apply(run_optimization, axis=1)
    summary['AI Suggested Price'] = [x[0] for x in results]
    summary['impact_num'] = [x[1] for x in results]
    summary['Proj. Monthly Gain'] = summary['impact_num'].apply(lambda x: f"+${x:,.2f}" if x > 0 else "$0")

    # Display Results
    tab1, tab2 = st.tabs(["Pricing Strategy", "Sales Volume"])
    
    with tab1:
        st.subheader("Optimization Recommendations")
        st.dataframe(summary[['Item Name', 'Units Sold', 'Current Price', 'AI Suggested Price', 'Proj. Monthly Gain']], use_container_width=True)
        st.metric(label="Total Projected Monthly Profit Increase", value=f"+${summary['impact_num'].sum():,.2f}")
    
    with tab2:
        st.subheader("Units Sold by Product")
        st.bar_chart(summary.set_index('Item Name')['Units Sold'])
