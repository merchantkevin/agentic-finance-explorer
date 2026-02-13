import streamlit as st
import yfinance as yf
import requests
import time
from datetime import datetime

# --- 1. PAGE CONFIGURATION ---
# This sets the browser tab title and ensures the sidebar is visible/responsive.
st.set_page_config(
    page_title="FinAI | Advisor", 
    page_icon="🏦", 
    layout="wide",
    initial_sidebar_state="auto"
)

# --- 2. CUSTOM STYLING (The "Make it Pretty" Section) ---
# We use CSS to fix the metric text wrapping and style our Risk Audit cards.
st.markdown("""
    <style>
    /* Metric Value: Forces text to wrap so it doesn't get cut off on mobile */
    [data-testid="stMetricValue"] > div { 
        font-size: 1.2rem !important; 
        font-weight: 700 !important;
        white-space: normal !important; 
        word-break: break-word !important; 
    }
    /* Risk Bullets: Custom red-bordered boxes for the Agent's risk audit */
    .risk-bullet { 
        background-color: #fff5f5; padding: 12px; border-radius: 8px; 
        border-left: 4px solid #9b2c2c; margin-bottom: 10px; 
        font-size: 0.85rem; color: #9b2c2c; line-height: 1.4; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. THE PRICE ENGINE ---
# This function talks to Yahoo Finance. It's used by the sidebar to get live data.
def get_current_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        # Use fast_info - it is much more stable and avoids the 'currentTradingPeriod' bug
        price = stock.fast_info['last_price']
        currency = stock.fast_info['currency']
        
        # Instead of .info['previousClose'], we use .history to get the last closing price
        # This is slightly slower but 100% stable
        hist = stock.history(period="2d")
        if len(hist) > 1:
            prev_close = hist['Close'].iloc[-2]
            change = price - prev_close
        else:
            change = 0.0
            
        return price, currency, change
    except Exception as e:
        print(f"YFinance Error: {e}")
        return None, None, None

# --- 4. THE LIVE HEARTBEAT (Fragment) ---
# This is a "mini-app" that runs every 5 seconds without refreshing the whole page.
@st.fragment(run_every=5)
def live_price_sidebar(ticker_symbol):
    price, currency, change = get_current_price(ticker_symbol)
    if price:
        # st.metric automatically handles the green/red coloring for 'delta'
        st.metric(
            label=f"Live Price: {ticker_symbol}", 
            value=f"{currency} {price:.2f}",
            delta=f"{change:.2f} Today"
        )

# --- 5. MAIN UI LOGIC ---
def main():
    st.title("🏦 AI Financial Committee")
    st.subheader("Multi-Agent Equity Research & Risk Audit")

    # --- SIDEBAR CONFIGURATION ---
    with st.sidebar:
        st.header("⚙️ Settings")
        ticker = st.text_input("Stock Ticker", value="RELIANCE.NS").upper()
        
        # This button triggers the FastAPI backend
        analyze_btn = st.button("🔍 Execute Analysis", use_container_width=True)
        
        # Spacing to push the live price to the very bottom
        st.markdown("---")
        if ticker:
            # We call our "Heartbeat" fragment here
            live_price_sidebar(ticker)

    # --- ANALYSIS EXECUTION ---
    if analyze_btn:
        with st.status(f"Waking up agents for {ticker}...", expanded=True) as status:
            try:
                # 1. Send request to our FastAPI Backend (Render)
                # Ensure this URL matches your Render deployment URL!
                backend_url = "https://agentic-finance-explorer.onrender.com" 
                response = requests.post(f"{backend_url}/analyze", json={"ticker": ticker})
                
                if response.status_code == 200:
                    data = response.json()

                    # Check if it was served instantly from SQL
                    if data.get("status") == "completed":
                        result = data.get("result")
                        source = data.get("source")
                        # Jump straight to display
                    else:
                        job_id = data.get("job_id")
                        status_placeholder = st.empty() # The single slot for messages
                        
                        # --- THE LOOP FIX ---
                        max_attempts = 20 # 20 attempts * 5 seconds = 100 seconds (max wait)
                        attempts = 0
                        
                        while attempts < max_attempts:
                            poll_res = requests.get(f"{backend_url}/status/{job_id}")
                            
                            # If the backend is down or errors out
                            if poll_res.status_code != 200:
                                status_placeholder.error("Backend lost connection.")
                                break
                                
                            poll_data = poll_res.json()
                            current_status = poll_data.get("status")
    
                            if current_status == "completed":
                                result = poll_data.get("result")
                                source = "Live Agent Analysis"
                                status_placeholder.empty()
                                break # Success!
                            
                            elif current_status == "failed":
                                status_placeholder.error(f"Analysis failed: {poll_data.get('error')}")
                                return
                            
                            elif current_status == "not_found":
                                status_placeholder.warning("Job lost by server. Restarting...")
                                break # Break and let the user try again
    
                            # If it's still "pending" or "started"
                            status_placeholder.info(f"🕵️ Committee is debating... (Step {attempts+1}/{max_attempts})")
                            
                            time.sleep(5)
                            attempts += 1
                        
                        if attempts >= max_attempts:
                            status_placeholder.error("The committee is taking too long. Please try again.")
                            return

                    # --- DISPLAY RESULTS ---
                    # Show the Intelligence Source (Live vs SQL Cache)
                    if "Intelligence" in source:
                        st.info(f"📁 Source: {source} (Price Stable)")
                    else:
                        st.success(f"🟢 Source: {source}")

                    # Layout: 3 Columns for the Main Metrics
                    m1, m2, m3 = st.columns(3)
                    with m1:
                        st.metric("Technical Signal", result.get('technical_signal', 'N/A'))
                    with m2:
                        st.metric("Sentiment Score", f"{result.get('sentiment_score', 0)}/10")
                    with m3:
                        st.metric("Recommendation", result.get('recommendation', 'N/A'))

                    # Layout: 2 Columns for detailed Summary and Risk Audit
                    col_main, col_side = st.columns([2, 1])
                    
                    with col_main:
                        st.markdown("### 📝 Executive Summary")
                        st.write(result.get('risk_summary', 'No summary available.'))
                        
                    with col_side:
                        st.markdown("### 🛡️ Risk Audit")
                        # Split the risk text into individual bullets (using '.' as a separator)
                        raw_risks = result.get('risk_summary', '').split('.')
                        # Show only the first 4 significant points
                        clean_risks = [r.strip() for r in raw_risks if len(r) > 10][:4]
                        for r in clean_risks:
                            st.markdown(f'<div class="risk-bullet">⚠️ {r}</div>', unsafe_allow_html=True)
                
                else:
                    st.error("Backend Handshake Failed. Check Render URL.")
            except Exception as e:
                st.error(f"System Error: {str(e)}")

if __name__ == "__main__":
    main()