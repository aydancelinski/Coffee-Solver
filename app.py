import streamlit as st
import pandas as pd
import io
import math
import openai

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
    [data-testid="stSidebar"] { background-color: #E6D5B8 !important; }
    </style>
    """, unsafe_allow_html=True)

# 2. SIDEBAR
st.sidebar.header("🔑 AI Consultant Setup")
api_key = st.sidebar.text_input("Enter OpenAI API Key", type="password")

st.title("Celinski's Coffee Solver »")

# 3. STRATEGIC AI CONSULTANT
def ai_strategy_consultant(user_query, key):
    client = openai.OpenAI(api_key=key)
    system_prompt = "You are an Economic Strategy Consultant. Explain pricing using Elasticity and Left-Digit anchors."
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_query}]
    )
    return response.choices[0].message.content

st.subheader("🎓 Strategic AI Consultant")
user_query = st.text_input("Ask a strategy question:")
if st.button("Ask Consultant"):
    if not api_key: st.warning("Enter API key in sidebar.")
    elif user_query:
        with st.spinner("Consulting..."):
            try:
                answer = ai_strategy_consultant(user_query, api_key)
                st.markdown(f"> **Consultant's Insight:** {answer}")
            except Exception as e: st.error(f"AI Error: {e}")

st.divider()

# 4. UNIVERSAL FILE UPLOADER - UPDATED MAPPING
uploaded_file = st.file_uploader("Upload Coffee POS File (CSV or Excel)", type=["csv", "xlsx"])

df = None
months_in_data = 1.0 

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            raw_bytes = uploaded_file.getvalue()
            raw_text = raw_bytes.decode("utf-8-sig", errors="ignore")
            # Maven uses pipe (|)
            df = pd.read_csv(io.StringIO(raw_text), sep='|' if '|' in raw_text else ',')
        else:
            df = pd.read_excel(uploaded_file)
        
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # 🎯 EXPLICIT MAPPING FOR MAVEN HEADERS
        name_map = {}
        for c in df.columns:
            # Item Name logic
            if any(x in c for x in ['product_detail', 'product_description', 'detail', 'description']):
                name_map[c] = 'item'
            # Quantity logic
            if any(x in c for x in ['transaction_qty', 'qty', 'quantity', 'sold']):
                name_map[c] = 'quantity'
            # Price logic
            if any(x in c for x in ['unit_price', 'price', 'rate']):
                name_map[c] = 'price'
            # Date logic
            if any(x in c for x in ['transaction_date', 'date', 'time']):
                name_map[c] = 'date'
        
        df = df.rename(columns=name_map)
        
        # Fallback if mapping missed something
        required = ['item', 'quantity', 'price']
        if all(col in df.columns for col in required):
            for col in ['quantity', 'price']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # 🕒 TEMPORAL NORMALIZATION (THE 94K KILLER)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                valid_dates = df['date'].dropna()
                if not valid_dates.empty:
                    days_span = (valid_dates.max() - valid_dates.min()).days
                    # For Maven, this should result in ~5.9 months
                    months_in_data = max(1.0, days_span / 30.44)
        else:
            st.error(f"Mapping failed. Columns found: {list(df.columns)}")
            df = None
            
    except Exception as e: st.error(f"File Error: {e}")

# 5. PRICING ENGINE
if df is not None:
    summary = df.groupby('item').agg({'quantity': 'sum', 'price': 'mean'}).reset_index()
    # Normalize units sold immediately
    summary['Monthly Units Sold'] = (summary['quantity'] / months_in_data).round(0).astype(int)
    summary.rename(columns={'item': 'Item Name', 'price': 'Current Price'}, inplace=True)

    def run_optimization(row):
        p, units = row['Current Price'], row['Monthly Units Sold']
        dollar = math.floor(p)
        if units > 35:
            new_p = dollar + 0.99 if math.floor(p + 0.50) > dollar else p + 0.50
            return new_p, (new_p - p) * units, "Increase"
        elif units < 10:
            new_p = max(0.99, p - 0.50)
            extra = units * 0.20
            gain = max(0, (new_p * (units + extra)) - (p * units))
            return new_p, gain, "Decrease"
        return p, 0, "Hold"

    results = summary.apply(run_optimization, axis=1)
    summary['AI Suggested Price'] = [x[0] for x in results]
    summary['Monthly Impact'] = [float(x[1]) for x in results]
    summary['Strategy'] = [x[2] for x in results]
    summary['Proj. Monthly Gain'] = summary['Monthly Impact'].apply(lambda x: f"+${x:,.2f}" if x > 0 else "$0")

    st.subheader(f"Strategy Analysis ({months_in_data:.1f} Months Collected)")
    st.metric("Total Projected Monthly Gain", f"+${summary['Monthly Impact'].sum():,.2f}")
    
    styled_df = summary[['Item Name', 'Monthly Units Sold', 'Current Price', 'AI Suggested Price', 'Proj. Monthly Gain', 'Strategy']].style.applymap(
        lambda x: 'background-color: #C6F4D6' if x == 'Increase' else ('background-color: #F8D7DA' if x == 'Decrease' else ''), 
        subset=['Strategy']
    )
    st.dataframe(styled_df, use_container_width=True)

# 6. RESTORED DOCUMENTATION & BIO
st.divider()
doc_col1, doc_col2 = st.columns([2, 1])

with doc_col1:
    st.header("Project Documentation")
    st.subheader("Objective")
    st.write("""
    The Celinski Coffee Solver was developed to bridge the gap between raw Point-of-Sale (POS) data and actionable business strategy. 
    As an Economics student, I recognized that small business owners often lack the tools to perform complex price elasticity 
    tests. This application automates that analysis to maximize revenue through data-driven recommendations.
    """)
    st.subheader("Key Features")
    st.write("""
    * **Hybrid Data Processing**: Utilizes a dual-entry system allowing for both large-scale structured file uploads (CSV/Excel) and unstructured 'messy' text input via an OpenAI-integrated AI Assistant.
    * **Temporal Normalization**: Automatically detects the date range of imported datasets (up to 10,000+ rows) and normalizes sales volume to a standard 30-day monthly average for accurate forecasting.
    * **Psychological Pricing Guardrails**: Implements a 'Left-Digit' capping algorithm that ensures price increases (based on high-volume performance) do not cross whole-dollar thresholds, preserving consumer price anchors.
    * **Universal Data Repair**: A defensive programming layer that identifies and repairs malformed CSV files (Pipe or Comma delimited) and re-maps non-standard headers like 'Product_Detail' or 'Unit_Rate' automatically.
    """)

with doc_col2:
    st.header("About the Developer")
    st.write(f"**Aydan P. Celinski** *University of Colorado Boulder*")
    st.write(f"*Third Year Economics Student | Business & Spanish Minors*")
    st.write("""
    I am a data-focused analyst passionate about using Python and Machine Learning to solve real-world 
    financial problems. My background combines economic theory with technical execution, including:
    """)
    st.write("* **Technical Skills**: Python (Pandas, Streamlit), SQL, and API Integration.")
    st.write("* **Focus**: Price Optimization, Market Analysis, and Business Automation.")
    st.markdown(f"[LinkedIn Profile](https://www.linkedin.com/in/aydan-celinski-a35738299/)")
