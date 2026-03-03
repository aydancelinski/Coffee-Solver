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
st.sidebar.header("🔑 AI Assistant Setup")
api_key = st.sidebar.text_input("Enter OpenAI API Key", type="password", help="Needed for the Chat Assistant.")

st.title("Celinski's Coffee Solver »")

# 3. AI CHAT ASSISTANT (For small snippets)
def ai_data_translator(user_input, key):
    client = openai.OpenAI(api_key=key)
    system_prompt = "Convert messy text into a CSV with headers: item, quantity, price, date. Only return CSV text."
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}]
    )
    return response.choices[0].message.content

st.subheader("💬 AI Data Assistant")
st.info("Best for small snippets (max 20 rows). For full reports (10,000+ rows), use the uploader below.")
user_chat = st.text_area("Paste messy notes here (e.g., 'Sold 10 lattes at $5'):")

ai_df = None
if st.button("Process Snippet with AI"):
    if not api_key:
        st.warning("Please enter your OpenAI API key in the sidebar.")
    elif user_chat:
        with st.spinner("AI is translating..."):
            try:
                cleaned_csv = ai_data_translator(user_chat, api_key)
                ai_df = pd.read_csv(io.StringIO(cleaned_csv))
                st.success("AI successfully translated your snippet!")
            except Exception as e:
                st.error(f"AI Error: {e}")

st.divider()

# 4. FILE UPLOADER & THE "PIPE/TIME" REPAIR
uploaded_file = st.file_uploader("Upload full POS CSV or Excel file (e.g., Maven Roasters)", type=["csv", "xlsx"])

df = None
months_in_data = 1 # Default

if ai_df is not None:
    df = ai_df
elif uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            raw_bytes = uploaded_file.getvalue()
            raw_text = raw_bytes.decode("utf-8-sig", errors="ignore")
            first_line = raw_text.split('\n')[0]
            df = pd.read_csv(io.StringIO(raw_text), sep='|' if '|' in first_line else ',')
        else:
            df = pd.read_excel(uploaded_file)
        
        # Standardize headers to lower case strings
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # Strict mapping logic
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
            
            # 🕒 TIME NORMALIZATION
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                days_span = (df['date'].max() - df['date'].min()).days
                months_in_data = max(1, days_span / 30.44) 
        else:
            st.error("Could not find required columns. Please check your file headers.")
            df = None
    except Exception as e:
        st.error(f"File processing error: {e}")

# 5. PRICING ENGINE WITH FORMATTING & ROUNDING
if df is not None and 'item' in df.columns:
    summary = df.groupby('item').agg({'quantity': 'sum', 'price': 'mean'}).reset_index()
    
    # Rounding units to the nearest whole number
    summary['Monthly Units Sold'] = (summary['quantity'] / months_in_data).round(0).astype(int)
    summary.rename(columns={'item': 'Item Name', 'price': 'Current Price'}, inplace=True)

    def run_optimization(row):
        curr_p = row['Current Price']
        units = row['Monthly Units Sold']
        curr_d = math.floor(curr_p)
        
        # Scenario A: High Volume (Increase Price)
        if units > 35:
            suggested = curr_p + 0.50
            # Guardrail: Don't cross the dollar threshold
            new_p = curr_d + 0.99 if math.floor(suggested) > curr_d else suggested
            return new_p, (new_p - curr_p) * units, "Increase"
        
        # Scenario B: Low Volume (Decrease Price)
        elif units < 10:
            new_p = max(0.99, curr_p - 0.50)
            extra = units * 0.20
            gain = max(0, (new_p * (units + extra)) - (curr_p * units))
            return new_p, gain, "Decrease"
            
        return curr_p, 0, "Hold"

    results = summary.apply(run_optimization, axis=1)
    summary['AI Suggested Price'] = [x[0] for x in results]
    summary['Monthly Impact'] = [x[1].round(2) for x in results]
    summary['Strategy'] = [x[2] for x in results]
    summary['Proj. Monthly Gain'] = summary['Monthly Impact'].apply(lambda x: f"+${x:,.2f}" if x > 0 else "$0")

    # RESTORE COLOR HIGHLIGHTING
    def color_strategy(val):
        if val == "Increase": color = 'background-color: #C6F4D6; color: #1E4620' # Light Green
        elif val == "Decrease": color = 'background-color: #F8D7DA; color: #721C24' # Light Red
        else: color = ''
        return color

    st.subheader(f"Strategy Analysis (Averaged over {months_in_data:.1f} months)")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Projected Monthly Gain", f"+${summary['Monthly Impact'].sum():,.2f}")
    with col2:
        st.metric("Total Items Analyzed", f"{len(summary)}")

    # Apply the highlighting
    styled_df = summary[['Item Name', 'Monthly Units Sold', 'Current Price', 'AI Suggested Price', 'Proj. Monthly Gain', 'Strategy']].style.applymap(color_strategy, subset=['Strategy'])
    st.dataframe(styled_df, use_container_width=True)

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
    * **Temporal Normalization**: Automatically detects the date range of imported datasets (up to 10,000+ rows) and normalizes sales volume to a standard 30-day monthly average.
    * **Psychological Pricing Guardrails**: Implements a 'Left-Digit' capping algorithm that ensures price increases do not cross whole-dollar thresholds, preserving consumer price anchors.
    * **Universal Data Repair**: A defensive programming layer that identifies and repairs malformed CSV files (Pipe or Comma delimited) and re-maps non-standard headers automatically.
    * **Hybrid Data Processing**: Uses a dual-entry system for both large-scale structured file uploads and unstructured 'messy' text input via an OpenAI-integrated API.
    """)

with doc_col2:
    st.header("👤 About the Developer")
    st.write("""
    **Aydan P. Celinski** *University of Colorado Boulder* *Economics Major | Business & Spanish Minors*
    
    I am a data-focused analyst passionate about using Python to solve real-world financial problems. 
    My background combines economic theory with technical execution, including:
    * **Data Analytics**: Google Data Analytics Professional Certificate candidate.
    * **Technical Skills**: Python (Pandas, Streamlit), SQL, and API Integration.
    * **Focus**: Price Optimization, Market Analysis, and Business Automation.
    
    [LinkedIn Profile](#) | [GitHub Repository](#)
    """)
