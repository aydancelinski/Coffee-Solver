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

# 2. SIDEBAR - API SECURITY
st.sidebar.header("🔑 AI Consultant Setup")
api_key = st.sidebar.text_input("Enter OpenAI API Key", type="password", help="Required for the Strategic Consultant.")

st.title("Celinski's Coffee Solver »")

# 3. STRATEGIC AI CONSULTANT
def ai_strategy_consultant(user_query, key):
    client = openai.OpenAI(api_key=key)
    system_prompt = """
    You are an Economic Strategy Consultant for 'Celinski Coffee Solver'. 
    Explain pricing decisions using economic theory:
    - We use $0.50 buckets to test elasticity without high churn.
    - We cap prices at $0.99 to respect 'Left-Digit' anchors.
    - High volume items (>35/mo) have inelastic demand, allowing for hikes.
    - Low volume items (<10/mo) get drops to test price sensitivity.
    Keep answers concise and professional.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_query}]
    )
    return response.choices[0].message.content

st.subheader("🎓 Strategic AI Consultant")
st.info("Ask about the economic logic behind these pricing recommendations.")
user_query = st.text_input("e.g., 'Why use a 50 cent increase?' or 'Explain the $0.99 cap'")

if st.button("Ask Consultant"):
    if not api_key:
        st.warning("Please enter your OpenAI API key in the sidebar.")
    elif user_query:
        with st.spinner("Consulting Economic Theory..."):
            try:
                answer = ai_strategy_consultant(user_query, api_key)
                st.markdown(f"> **Consultant's Insight:** {answer}")
            except Exception as e:
                st.error(f"AI Error: {e}")

st.divider()

# 4. FILE UPLOADER & THE "PIPE/TIME" REPAIR
uploaded_file = st.file_uploader("Upload Maven Roasters POS file (CSV or Excel)", type=["csv", "xlsx"])

df = None
months_in_data = 1

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            raw_bytes = uploaded_file.getvalue()
            raw_text = raw_bytes.decode("utf-8-sig", errors="ignore")
            first_line = raw_text.split('\n')[0]
            df = pd.read_csv(io.StringIO(raw_text), sep='|' if '|' in first_line else ',')
        else:
            df = pd.read_excel(uploaded_file)
        
        df.columns = [str(c).lower().strip() for c in df.columns]
        name_map = {}
        for c in df.columns:
            if any(x in c for x in ['detail', 'item', 'product']): name_map[c] = 'item'
            if any(x in c for x in ['qty', 'quantity', 'sold', 'count']): name_map[c] = 'quantity'
            if any(x in c for x in ['price', 'rate', 'unit_price']): name_map[c] = 'price'
            if any(x in c for x in ['date', 'time']): name_map[c] = 'date'
        
        df = df.rename(columns=name_map)
        df = df.loc[:, ~df.columns.duplicated()]
        
        if all(col in df.columns for col in ['item', 'quantity', 'price']):
            for col in ['quantity', 'price']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                days_span = (df['date'].max() - df['date'].min()).days
                months_in_data = max(1, days_span / 30.44) 
        else:
            st.error("Missing required columns.")
            df = None
    except Exception as e:
        st.error(f"File Error: {e}")

# 5. PRICING ENGINE WITH FORMATTING & ROUNDING
if df is not None and 'item' in df.columns:
    summary = df.groupby('item').agg({'quantity': 'sum', 'price': 'mean'}).reset_index()
    summary['Monthly Units Sold'] = (summary['quantity'] / months_in_data).round(0).astype(int)
    summary.rename(columns={'item': 'Item Name', 'price': 'Current Price'}, inplace=True)

    def run_optimization(row):
        curr_p = row['Current Price']
        units = row['Monthly Units Sold']
        curr_d = math.floor(curr_p)
        if units > 35:
            suggested = curr_p + 0.50
            new_p = curr_d + 0.99 if math.floor(suggested) > curr_d else suggested
            return new_p, (new_p - curr_p) * units, "Increase"
        elif units < 10:
            new_p = max(0.99, curr_p - 0.50)
            extra = units * 0.20
            gain = max(0, (new_p * (units + extra)) - (curr_p * units))
            return new_p, gain, "Decrease"
        return curr_p, 0, "Hold"

    results = summary.apply(run_optimization, axis=1)
    summary['AI Suggested Price'] = [x[0] for x in results]
    # Fixed AttributeError by using round() on values, not the list
    summary['Monthly Impact'] = [round(float(x[1]), 2) for x in results]
    summary['Strategy'] = [x[2] for x in results]
    summary['Proj. Monthly Gain'] = summary['Monthly Impact'].apply(lambda x: f"+${x:,.2f}" if x > 0 else "$0")

    def color_strategy(val):
        if val == "Increase": color = 'background-color: #C6F4D6; color: #1E4620'
        elif val == "Decrease": color = 'background-color: #F8D7DA; color: #721C24'
        else: color = ''
        return color

    st.subheader(f"Strategy Analysis ({months_in_data:.1f} months normalized)")
    st.metric("Total Projected Monthly Gain", f"+${summary['Monthly Impact'].sum():,.2f}")
    
    styled_df = summary[['Item Name', 'Monthly Units Sold', 'Current Price', 'AI Suggested Price', 'Proj. Monthly Gain', 'Strategy']].style.applymap(color_strategy, subset=['Strategy'])
    st.dataframe(styled_df, use_container_width=True)

# 6. DOCUMENTATION & BIO
st.divider()
doc_col1, doc_col2 = st.columns([2, 1])
with doc_col1:
    st.header("📘 Project Documentation")
    st.write("""
    ### Objective
    Developed by an Economics student to automate price elasticity analysis for small businesses.
    ### Key Features
    * **Temporal Normalization**: Averages sales over time (10,000+ rows) for accurate 30-day forecasting.
    * **Psychological Pricing**: Capping hikes at $0.99 to respect 'Left-Digit' consumer anchors.
    * **Universal Repair**: Automatically handles Pipe (|) and Comma (,) delimited POS exports.
    """)
with doc_col2:
    st.header("👤 About the Developer")
    st.write("""
    **Aydan P. Celinski** | *CU Boulder Economics*
    * **Google Data Analytics candidate.**
    * **Specialization**: Price Optimization & Business Automation.
    [LinkedIn](#) | [GitHub](#)
    """)
