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
st.sidebar.header("🔑 API Configuration")
api_key = st.sidebar.text_input("Enter OpenAI API Key", type="password", help="Needed for AI snippets.")

st.title("Celinski's Coffee Solver »")

# 3. AI CHAT ASSISTANT (Limited to small snippets to avoid 429 errors)
def ai_data_translator(user_input, key):
    client = openai.OpenAI(api_key=key)
    system_prompt = "Convert messy text into a CSV with headers: item, quantity, price, date. Only return CSV text."
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}]
    )
    return response.choices[0].message.content

st.subheader("💬 AI Data Assistant")
user_chat = st.text_area("Paste small snippets of messy data here (limit 20 rows):")

ai_df = None
if st.button("Process with AI"):
    if not api_key:
        st.warning("Enter your OpenAI key in the sidebar.")
    elif user_chat:
        with st.spinner("AI is translating..."):
            try:
                cleaned_csv = ai_data_translator(user_chat, api_key)
                ai_df = pd.read_csv(io.StringIO(cleaned_csv))
                st.success("AI successfully translated your snippet!")
            except Exception as e:
                st.error(f"AI Error: {e}")

st.divider()

# 4. FILE UPLOADER & UNIVERSAL REPAIR (FOR FULL 10,000 ROW FILES)
uploaded_file = st.file_uploader("OR Upload your full POS CSV or Excel file", type=["csv", "xlsx"])

df = None
if ai_df is not None:
    df = ai_df
elif uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            raw_bytes = uploaded_file.getvalue()
            raw_text = raw_bytes.decode("utf-8-sig", errors="ignore")
            df = pd.read_csv(io.StringIO(raw_text))
            
            # --- THE FORCE SPLITTER FIX ---
            # Automatically detect if Excel put everything in Column A and split it
            if len(df.columns) == 1:
                col_name = str(df.columns[0])
                if ',' in col_name:
                    df = pd.read_csv(io.StringIO(raw_text), sep=',')
        else:
            df = pd.read_excel(uploaded_file)
        
        # Standardize all headers as strings
        df.columns = [str(c) for c in df.columns]
        cols = {c.lower().strip(): c for c in df.columns}
        name_map = {}
        for c in cols:
            if any(x in c for x in ['item', 'product', 'description']): name_map[cols[c]] = 'item'
            if any(x in c for x in ['qty', 'quantity', 'sold', 'count']): name_map[cols[c]] = 'quantity'
            if any(x in c for x in ['price', 'rate', 'amount']): name_map[cols[c]] = 'price'
            if any(x in c for x in ['date', 'time', 'day']): name_map[cols[c]] = 'date'
        
        df = df.rename(columns=name_map)
        
        # Cleanup numbers
        for col in ['quantity', 'price']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
    except Exception as e:
        st.error(f"File Processing Error: {e}")

# 5. PRICING ENGINE
if df is not None and 'item' in df.columns:
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

    tab1, tab2 = st.tabs(["Pricing Recommendations", "Sales Trends"])
    with tab1:
        st.subheader("Pricing Strategy")
        st.dataframe(summary.drop(columns=['impact_num', 'Extra Units Needed']), use_container_width=True)
        st.metric(label="Projected Monthly Gain Profit", value=f"+${summary['impact_num'].sum():,.2f} Profit")
    
    with tab2:
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df['rev'] = df['quantity'] * df['price']
            daily = df.groupby('date')['rev'].sum().reset_index()
            st.subheader("Daily Sales Trends")
            st.line_chart(daily.set_index('date'))
        else:
            st.warning("No date column detected for trends.")
else:
    if uploaded_file or ai_df is not None:
        st.error("Could not find required columns. Ensure your data has headers for Item, Price, and Quantity.")
