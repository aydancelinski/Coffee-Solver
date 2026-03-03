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

# 4. UNIVERSAL FILE UPLOADER & DEEP DATA SCAN
uploaded_file = st.file_uploader("Upload Coffee POS File (CSV or Excel)", type=["csv", "xlsx"])

df = None
months_in_data = 1.0 

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            raw_bytes = uploaded_file.getvalue()
            raw_text = raw_bytes.decode("utf-8-sig", errors="ignore")
            df = pd.read_csv(io.StringIO(raw_text), sep='|' if '|' in raw_text else ',')
        else:
            df = pd.read_excel(uploaded_file)
        
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # 🕵️ DEEP SCAN MAPPING
        name_map = {}
        found_mapped_types = set()
        
        # 1. Find Date FIRST (Fixes the 79k error)
        for c in df.columns:
            if any(x in c for x in ['date', 'time', 'transaction', 'sale']):
                # Try to force conversion to confirm it's a date
                temp_dates = pd.to_datetime(df[c], errors='coerce')
                if temp_dates.dropna().shape[0] > 0:
                    df['detected_date'] = temp_dates
                    found_mapped_types.add('date')
                    break

        # 2. Map Item, Quantity, and Price
        for c in df.columns:
            if 'item' not in found_mapped_types and any(x in c for x in ['detail', 'description', 'category', 'product']):
                if 'id' not in c:
                    name_map[c] = 'item'
                    found_mapped_types.add('item')
            elif 'quantity' not in found_mapped_types and any(x in c for x in ['qty', 'quantity', 'sold', 'units']):
                name_map[c] = 'quantity'
                found_mapped_types.add('quantity')
            elif 'price' not in found_mapped_types and any(x in c for x in ['price', 'rate', 'unit']):
                name_map[c] = 'price'
                found_mapped_types.add('price')
        
        df = df.rename(columns=name_map)
        
        if all(col in df.columns for col in ['item', 'quantity', 'price']):
            for col in ['quantity', 'price']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # 🕒 THE NORMALIZATION ANCHOR
            if 'detected_date' in df.columns:
                valid_dates = df['detected_date'].dropna()
                days_span = (valid_dates.max() - valid_dates.min()).days
                # Correctly normalizes to ~3.0 for your test file or ~5.9 for Maven
                months_in_data = max(1.0, days_span / 30.44)
        else:
            st.error(f"Could not map columns. Found: {list(df.columns)}")
            df = None
            
    except Exception as e: st.error(f"File Error: {e}")

# 5. PRICING ENGINE (NORMALIZED MATH)
if df is not None:
    summary = df.groupby('item').agg({'quantity': 'sum', 'price': 'mean'}).reset_index()
    # Average lifetime volume over the months collected
    summary['Monthly Units Sold'] = (summary['quantity'] / months_in_data).round(0).astype(int)
    summary.rename(columns={'item': 'Item Name', 'price': 'Current Price'}, inplace=True)

    def run_optimization(row):
        p, m_units = row['Current Price'], row['Monthly Units Sold']
        dollar = math.floor(p)
        if m_units > 35:
            new_p = dollar + 0.99 if math.floor(p + 0.50) > dollar else p + 0.50
            return new_p, (new_p - p) * m_units, "Increase"
        elif m_units < 10:
            new_p = max(0.99, p - 0.50)
            extra_m = m_units * 0.20
            gain = max(0, (new_p * (m_units + extra_m)) - (p * m_units))
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

# 6. RESTORED EXACT DOCUMENTATION & BIO LAYOUT
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
    st.write(f"**Aydan P. Celinski** *Third Year Economics Student at the University of Colorado Boulder*")
    st.write(f"*Economics Major | Business & Spanish Minors*")
    st.write("""
    I am a data-focused analyst passionate about using Python and Machine Learning to solve real-world 
    financial problems. My background combines economic theory with technical execution, including:
    """)
    st.write("* **Technical Skills**: Python (Pandas, Streamlit), SQL, and API Integration.")
    st.write("* **Focus**: Price Optimization, Market Analysis, and Business Automation.")
    st.markdown(f"[LinkedIn Profile](https://www.linkedin.com/in/aydan-celinski-a35738299/)")
