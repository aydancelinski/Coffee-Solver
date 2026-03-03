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
uploaded_file = st.file_uploader("Upload your Maven Roasters POS file", type=["csv", "xlsx"])

df = None
if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            raw_bytes = uploaded_file.getvalue()
            raw_text = raw_bytes.decode("utf-8-sig", errors="ignore")
            
            # Detect Delimiter
            first_line = raw_text.split('\n')[0]
            df = pd.read_csv(io.StringIO(raw_text), sep='|' if '|' in first_line else ',')
        else:
            df = pd.read_excel(uploaded_file)
        
        # Standardize headers
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        name_map = {}
        for c in df.columns:
            if any(x in c for x in ['detail', 'item', 'product']): name_map[c] = 'item'
            if any(x in c for x in ['qty', 'quantity', 'sold']): name_map[c] = 'quantity'
            if any(x in c for x in ['price', 'rate']): name_map[c] = 'price'
            if any(x in c for x in ['date', 'time']): name_map[c] = 'date'
        
        df = df.rename(columns=name_map)
        df = df.loc[:, ~df.columns.duplicated()]
        
        # Check for required columns
        needed = ['item', 'quantity', 'price']
        if all(col in df.columns for col in needed):
            for col in ['quantity', 'price']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # 🕒 TIME NORMALIZATION LOGIC
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                days_span = (df['date'].max() - df['date'].min()).days
                # If data is less than a day, default to 1 to avoid division by zero
                months_in_data = max(1, days_span / 30.44) 
            else:
                months_in_data = 1 # Fallback if no date found
        else:
            st.error("Missing columns (Item, Price, or Quantity).")
            df = None
                
    except Exception as e:
        st.error(f"File Error: {e}")

# 3. PRICING ENGINE WITH MONTHLY NORMALIZATION
if df is not None and 'item' in df.columns:
    summary = df.groupby('item').agg({'quantity': 'sum', 'price': 'mean'}).reset_index()
    
    # Divide total quantity by number of months to get "Monthly Units Sold"
    summary['Monthly Units Sold'] = summary['quantity'] / months_in_data
    summary.rename(columns={'item': 'Item Name', 'price': 'Current Price'}, inplace=True)

    def run_optimization(row):
        current_price = row['Current Price']
        monthly_units = row['Monthly Units Sold']
        current_dollar = math.floor(current_price)
        
        # SCENARIO A: HIGH VOLUME (> 35 units per month)
        if monthly_units > 35:
            suggested = current_price + 0.50
            if math.floor(suggested) > current_dollar:
                new_price = current_dollar + 0.99
            else:
                new_price = suggested
            
            gain = (new_price - current_price) * monthly_units
            return new_price, max(0, gain)
        
        # SCENARIO B: LOW VOLUME (< 10 units per month)
        elif monthly_units < 10:
            new_price = max(0.99, current_price - 0.50)
            extra_units = monthly_units * 0.20 
            new_rev = new_price * (monthly_units + extra_units)
            current_rev = current_price * monthly_units
            return new_price, max(0, new_rev - current_rev)
            
        return current_price, 0

    results = summary.apply(run_optimization, axis=1)
    summary['AI Suggested Price'] = [x[0] for x in results]
    summary['Monthly Impact'] = [x[1] for x in results]

    # UI Display
    st.subheader(f"Strategy for Maven Roasters (Averaged over {months_in_data:.1f} months)")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Projected Monthly Gain", f"+${summary['Monthly Impact'].sum():,.2f}")
    with col2:
        st.metric("Total Items Analyzed", f"{len(summary)}")

    st.dataframe(summary[['Item Name', 'Monthly Units Sold', 'Current Price', 'AI Suggested Price', 'Monthly Impact']], use_container_width=True)
    # 6. DETAILED PROJECT DOCUMENTATION & BIO
st.divider()
doc_col1, doc_col2 = st.columns([2, 1])

with doc_col1:
    st.header("📘 Project Documentation")
    st.write("""
    ### Objective
    The **Celinski Coffee Solver** was developed to bridge the gap between raw Point-of-Sale (POS) data and actionable business strategy. 
    As an Economics student, I recognized that small business owners often lack the tools to perform complex price elasticity 
    tests. This application automates that analysis to maximize revenue through data-driven recommendations.
    
    ### Key Features
    * **Hybrid Data Processing**: Utilizes a dual-entry system allowing for both large-scale structured file uploads (CSV/Excel) and unstructured 'messy' text input via an OpenAI-integrated AI Assistant.
    * **Temporal Normalization**: Automatically detects the date range of imported datasets (up to 10,000+ rows) and normalizes sales volume to a standard 30-day monthly average for accurate forecasting.
    * **Psychological Pricing Guardrails**: Implements a 'Left-Digit' capping algorithm that ensures price increases (based on high-volume performance) do not cross whole-dollar thresholds, preserving consumer price anchors.
    * **Universal Data Repair**: A defensive programming layer that identifies and repairs malformed CSV files (Pipe or Comma delimited) and re-maps non-standard headers like 'Product_Detail' or 'Unit_Rate' automatically.
    """)

with doc_col2:
    st.header("👤 About the Developer")
    st.write("""
    **Aydan P. Celinski** *University of Colorado Boulder* *Economics Major | Business & Spanish Minors*
    
    I am a data-focused analyst passionate about using Python and Machine Learning to solve real-world financial problems. 
    My background combines economic theory with technical execution, including:
    * **Data Analytics**: Google Data Analytics Professional Certificate candidate.
    * **Technical Skills**: Python (Pandas, Streamlit), SQL, and API Integration.
    * **Focus**: Price Optimization, Market Analysis, and Business Automation.
    
    [LinkedIn Profile](#) | [GitHub Repository](#)
    """)
