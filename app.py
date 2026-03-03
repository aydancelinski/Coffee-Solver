# 5. PRICING ENGINE WITH FORCED NORMALIZATION
if df is not None and 'item' in df.columns:
    summary = df.groupby('item').agg({'quantity': 'sum', 'price': 'mean'}).reset_index()
    
    # 1. Normalize units immediately
    summary['Monthly Units Sold'] = (summary['quantity'] / months_in_data).round(0).astype(int)
    summary.rename(columns={'item': 'Item Name', 'price': 'Current Price'}, inplace=True)

    def run_optimization(row):
        curr_p = row['Current Price']
        m_units = row['Monthly Units Sold']
        curr_d = math.floor(curr_p)
        
        if m_units > 35:
            suggested = curr_p + 0.50
            new_p = curr_d + 0.99 if math.floor(suggested) > curr_d else suggested
            # IMPACT IS ONLY THE MONTHLY GAIN
            return new_p, (new_p - curr_p) * m_units, "Increase"
        
        elif m_units < 10:
            new_p = max(0.99, curr_p - 0.50)
            extra_m = m_units * 0.20
            # IMPACT IS ONLY THE MONTHLY GAIN
            gain = max(0, (new_p * (m_units + extra_m)) - (curr_p * m_units))
            return new_p, gain, "Decrease"
            
        return curr_p, 0, "Hold"

    results = summary.apply(run_optimization, axis=1)
    summary['AI Suggested Price'] = [x[0] for x in results]
    summary['Monthly Impact'] = [round(float(x[1]), 2) for x in results]
    summary['Strategy'] = [x[2] for x in results]
    
    # Display logic
    st.subheader(f"Strategy Analysis ({months_in_data:.1f} Months Found)")
    
    # CALCULATE TOTAL FROM THE NORMALIZED LIST
    total_gain = summary['Monthly Impact'].sum()
    st.metric("Total Projected Monthly Gain", f"+${total_gain:,.2f}")
    
    # Apply color and show table
    styled_df = summary[['Item Name', 'Monthly Units Sold', 'Current Price', 'AI Suggested Price', 'Monthly Impact', 'Strategy']].style.applymap(
        lambda x: 'background-color: #C6F4D6' if x == 'Increase' else ('background-color: #F8D7DA' if x == 'Decrease' else ''), 
        subset=['Strategy']
    )
    st.dataframe(styled_df, use_container_width=True)
