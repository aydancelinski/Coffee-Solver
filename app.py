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
                # TYPO FIXED HERE: Removed extra space between f's
                st.markdown(f"> **Consultant's Insight:** {answer}")
            except Exception as e: st.error(f"AI Error: {e}")

st.divider()

# 4. UNIVERSAL FILE UPLOADER & ADAPTIVE MAPPING
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
        
        name_map = {}
        found_types = set()
        
        # 1. Date Scan
        for c in df.columns:
            if any(x in c for x in ['date', 'transaction_date', 'sale_date']):
                temp_date = pd.to_datetime(df[c], errors='coerce')
                if temp_date.dropna().shape[0] > 0:
                    df['normalized_date'] = temp_date
                    found_types.add('date')
                    break

        # 2. Item Detail Search (Priority over Category)
        for c in df.columns:
            if 'item' not in found_types:
                if any(x in c for x in ['coffee_name', 'product_detail', 'item_detail', 'description']):
                    name_map[c] = 'item'
                    found_types.add('item')
                    break
        
        # 3. Price & Qty Scan
        for c in df.columns:
            if 'price' not in found_types and any(x in c for x in ['money', 'unit_price', 'price']):
                name_map[c] = 'price'
                found_types.add('price')
            elif 'quantity' not in found_types and any(x in c for x in ['qty', 'quantity', 'units', 'sold', 'transaction_qty']):
                name_map[c] = 'quantity'
                found_types.add('quantity')

        if 'quantity' not in found_types: df['quantity'] = 1
        
        df = df.rename(columns=name_map)
        
        if 'item' in df.columns and 'price' in df.columns:
            df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)
            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(1)
            
            if 'date' in found_types:
                valid_dates = df['normalized_date'].dropna()
                days_span = (valid_dates.max() - valid_dates.min()).days
                months_in_data = max(1.0, days_span / 30.44)
        else:
            st.error(f"Incomplete mapping. Columns recognized: {list(df.columns)}")
            df = None
            
    except Exception as e: st.error(f"File Error: {e}")

# 5. DYNAMIC PRICING ENGINE
if df is not None:
    summary = df.groupby('item').agg({'quantity': 'sum', 'price': 'mean'}).reset_index()
    summary['Monthly Units Sold'] = (summary['quantity'] / months_in_data).round(0).astype(int)
    
    # 📈 ADAPTIVE THRESHOLDS: Real-world logic for high-volume shops
    avg_volume = summary['Monthly Units Sold'].mean()
    high_volume_trigger = avg_volume * 1.5
    low_volume_trigger = avg_volume * 0.3
    
    summary.rename(columns={'item': 'Item Name', 'price': 'Current Price'}, inplace=True)

    def run_dynamic_optimization(row):
        p, units = row['Current Price'], row['Monthly Units Sold']
        dollar = math.floor(p)
        if units > high_volume_trigger:
            new_p = dollar + 0.99 if math.floor(p + 0.50) > dollar else p + 0.50
            return new_p, (new_p - p) * units, "Increase"
        elif units < low_volume_trigger:
            new_p = max(0.99, p - 0.50)
            extra = units * 0.20
            gain = max(0, (new_p * (units + extra)) - (p * units))
            return new_p, gain, "Decrease"
        return p, 0, "Hold"

    results = summary.apply(run_dynamic_optimization, axis=1)
    summary['AI Suggested Price'] = [x[0] for x in results]
    summary['Monthly Impact'] = [float(x[1]) for x in results]
    summary['Strategy'] = [x[2] for x in results]
    summary['Proj. Monthly Gain'] = summary['Monthly Impact'].apply(lambda x: f"+${x:,.2f}" if x > 0 else "$0")

    st.subheader(f"Strategy Analysis ({months_in_data:.1f} Months Collected)")
    st.info(f"📊 Shop Benchmark: High Volume > {int(high_volume_trigger)} units/mo")
    
    st.metric("Total Projected Monthly Gain", f"+${summary['Monthly Impact'].sum():,.2f}")
    
    styled_df = summary[['Item Name', 'Monthly Units Sold', 'Current Price', 'AI Suggested Price', 'Proj. Monthly Gain', 'Strategy']].style.applymap(
        lambda x: 'background-color: #C6F4D6' if x == 'Increase' else ('background-color: #F8D7DA' if x == 'Decrease' else ''), 
        subset=['Strategy']
    )
    st.dataframe(styled_df, use_container_width=True)

# 6. OBJECTIVE & BIO
st.divider()
doc_col1, doc_col2 = st.columns([2, 1])
with doc_col1:
    st.header("Objective")
    st.write("Bridging raw POS data and actionable economic strategy.")
    st.subheader("Key Features")
    st.write("* **Adaptive Elasticity**: Scaling triggers to the business's actual volume.")
    st.write("* **Temporal Normalization**: 30-day standardized forecasting.")

with doc_col2:
    st.header("About the Developer")
    st.write(f"**Aydan P. Celinski** *University of Colorado Boulder*")
    st.write(f"*Third Year Economics Student | Business & Spanish Minors*")
