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
    system_prompt = """
    You are an Economic Strategy Consultant. Explain pricing using Elasticity and Left-Digit anchors.
    - $0.50 buckets test elasticity.
    - $0.99 caps respect 'Left-Digit' anchors.
    - High volume (>35/mo) is inelastic.
    - Low volume (<10/mo) tests price sensitivity.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_query}]
    )
    return response.choices[0].message.content

st.subheader("🎓 Strategic AI Consultant")
user_query = st.text_input("Ask a strategy question:")
if st.button("Ask Consultant"):
    if not api_key: st.warning("Enter API key.")
    elif user_query:
        with st.spinner("Consulting..."):
            try:
                answer = ai_strategy_consultant(user_query, api_key)
                st.markdown(f"> **Consultant's Insight:** {answer}")
            except Exception as e: st.error(f"AI Error: {e}")

st.divider()

# 4. FILE UPLOADER
uploaded_file = st.file_uploader("Upload Maven Roasters POS file", type=["csv", "xlsx"])

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
        
        # Fixed Mapping: Ensures Date is found for normalization
        name_map = {}
        for c in df.columns:
            if any(x in c for x in ['detail', 'description']): name_map[c] = 'item'
            elif 'item' not in name_map.values() and any(x in c for x in ['product', 'item']) and 'id' not in c:
                name_map[c] = 'item'
            if any(x in c for x in ['qty', 'quantity', 'sold']): name_map[c] = 'quantity'
            if any(x in c for x in ['price', 'rate']): name_map[c] = 'price'
            if any(x in c for x in ['date', 'time']): name_map[c] = 'date'
        
        df = df.rename(columns=name_map)
        df = df.loc[:, ~df.columns.duplicated(keep='last')]
        
        if all(col in df.columns for col in ['item', 'quantity', 'price']):
            for col in ['quantity', 'price']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # 🕒 TIME NORMALIZATION
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                valid_dates = df['date'].dropna()
                if not valid_dates.empty:
                    days_span = (valid_dates.max() - valid_dates.min()).days
                    months_in_data = max(1.0, days_span / 30.44)
    except Exception as e: st.error(f"File Error: {e}")

# 5. PRICING ENGINE - FIXED MATH
if df is not None:
    summary = df.groupby('item').agg({'quantity': 'sum', 'price': 'mean'}).reset_index()
    
    # 1. Force normalized units
    summary['Monthly Units Sold'] = (summary['quantity'] / months_in_data).round(0).astype(int)
    summary.rename(columns={'item': 'Item Name', 'price': 'Current Price'}, inplace=True)

    def run_optimization(row):
        p, m_units = row['Current Price'], row['Monthly Units Sold']
        dollar = math.floor(p)
        if m_units > 35:
            new_p = dollar + 0.99 if math.floor(p + 0.50) > dollar else p + 0.50
            # FIXED: Profit is (Price Change) * MONTHLY Units, not lifetime units
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

    st.subheader(f"Strategy Analysis ({months_in_data:.1f} Months Normalized)")
    # FIXED: Metric sums only the normalized monthly impacts
    st.metric("Total Projected Monthly Gain", f"+${summary['Monthly Impact'].sum():,.2f}")
    
    styled_df = summary[['Item Name', 'Monthly Units Sold', 'Current Price', 'AI Suggested Price', 'Proj. Monthly Gain', 'Strategy']].style.applymap(
        lambda x: 'background-color: #C6F4D6' if x == 'Increase' else ('background-color: #F8D7DA' if x == 'Decrease' else ''), 
        subset=['Strategy']
    )
    st.dataframe(styled_df, use_container_width=True)

# 6. BIO
st.divider()
c1, c2 = st.columns([2, 1])
with c1:
    st.header("📘 Project Documentation")
    st.write("Averaging sales over 10,000+ rows for accurate 30-day forecasting with psychological price caps.")
with c2:
    st.header("👤 About the Developer")
    st.write("**Aydan P. Celinski** | *Third Year Economics Student at the University of Colorado Boulder*")
    st.write("[LinkedIn Profile](https://www.linkedin.com/in/aydan-celinski-a35738299/)")
