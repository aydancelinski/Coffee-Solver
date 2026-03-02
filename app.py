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
    [data-testid="stFileUploadDropzone"] { border: 2px dashed #3E2723 !important; }
    .stDataFrame, [data-testid="stTable"], [data-testid="stTable"] * {
        background-color: #E6D5B8 !important;
        color: #000000 !important;
    }
    .stDataFrame th { background-color: #D2B48C !important; color: #000000 !important; }
    section[data-testid="stSidebar"] { background-color: #E6D5B8 !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Celinski's Coffee Solver »")

# 2. FILE UPLOADER
uploaded_file = st.file_uploader("Upload any POS CSV or Excel file", type=["csv", "xlsx"])

if uploaded_file:
    # 3. UNIVERSAL DATA REPAIR (ENHANCED)
    try:
        if uploaded_file.name.endswith('.csv'):
            raw_bytes = uploaded_file.getvalue()
            raw_text = raw_bytes.decode("utf-8-sig", errors="ignore")
            # First attempt to read normally
            df = pd.read_csv(io.StringIO(raw_text))
            
            # SPECIAL FIX: If Excel put everything in one column (A1), split it
            if len(df.columns) == 1:
                col_name = str(df.columns[0])
                if ',' in col_name:
                    headers = col_name.split(',')
                    # Re-read the file using the comma as a separator
                    df = pd.read_csv(io.StringIO(raw_text), sep=',')
        else:
            df = pd.read_excel(uploaded_file)
        
        # Ensure all column headers are strings to prevent 'int' lower() error
        df.columns = [str(c) for c in df.columns]

        cols = {c.lower().strip(): c for c in df.columns}
        name_map = {}
        for c in cols:
            if any(x in c for x in ['item', 'product', 'description']): name_map[cols[c]] = 'item'
            if any(x in c for x in ['qty', 'quantity', 'sold', 'count']): name_map[cols[c]] = 'quantity'
            if any(x in c for x in ['price', 'rate', 'amount']): name_map[cols[c]] = 'price'
            if any(x in c for x in ['date', 'time', 'day']): name_map[cols[c]] = 'date'
        
        df = df.rename(columns=name_map)
        
        # Fill missing values and ensure numeric
        for col in ['quantity', 'price']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0
        
    except Exception as e:
        st.error(f"Error processing data: {e}")
        st.stop()

    # 4. PRICING ENGINE
    if 'item' in df.columns:
        summary = df.groupby('item').agg({'quantity': 'sum', 'price': 'mean'}).reset_index()
        summary.rename(columns={'item': 'Item Name', 'quantity': 'Units Sold', 'price': 'Current Price'}, inplace=True)

        def run_optimization(row):
            current_rev = row['Current Price'] * row['Units Sold']
            current_dollar = math.floor(row['Current Price'])
            if row['Units Sold'] > 35:
                suggested = row['Current Price'] + 0.50
                new_price = current_dollar + 0.99 if math.floor(suggested) > current_dollar else suggested
                new_price = max(new_price, row['Current Price'])
                return new_price, (new_price * row['Units Sold']) - current_rev, 0
            elif row['Units Sold'] < 10:
                new_price = row['Current Price'] - 0.50
                extra_units = row['Units Sold'] * 0.20 
                forecasted_qty = row['Units Sold'] + extra_units
                new_rev = new_price * forecasted_qty
                if new_rev > current_rev:
                    return new_price, new_rev - current_rev, extra_units
            return row['Current Price'], 0, 0

        results = summary.apply(run_optimization, axis=1)
        summary['AI Suggested Price'] = [x[0] for x in results]
        summary['impact_num'] = [x[1] for x in results]
        summary['Extra Units Needed'] = [x[2] for x in results]
        summary['Proj. Monthly Gain'] = summary['impact_num'].apply(lambda x: f"+${x:,.0f}" if x > 0 else "$0")
        summary['Extra Sales Forecast'] = summary['Extra Units Needed'].apply(lambda x: f"+{x:.1f} units" if x > 0 else "—")

        # 5. DISPLAY TABS
        tab1, tab2 = st.tabs(["Pricing Recommendations", "Sales Trends"])

        with tab1:
            st.subheader("Pricing Strategy")
            def highlight_strategy(row):
                green = 'background-color: #B2D8B2; color: #000000; font-weight: bold' 
                red = 'background-color: #F2B2B2; color: #000000; font-weight: bold'   
                if row['AI Suggested Price'] > row['Current Price']: return [green] * len(row)
                elif row['AI Suggested Price'] < row['Current Price']: return [red] * len(row)
                return [''] * len(row)
            st.dataframe(summary.drop(columns=['impact_num', 'Extra Units Needed']).style.apply(highlight_strategy, axis=1), use_container_width=True)
            st.metric(label="Projected Monthly Gain Profit", value=f"+${summary['impact_num'].sum():,.2f} Profit")

        with tab2:
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df['rev'] = df['quantity'] * df['price']
                daily = df.groupby('date')['rev'].sum().reset_index()
                st.subheader("Daily Sales Trends")
                st.line_chart(daily.set_index('date'))
            else:
                st.warning("No date column detected. Ensure your 'date' column is formatted correctly.")
    else:
        st.error("Could not find an 'Item' column. Check if your data is comma-separated.")
