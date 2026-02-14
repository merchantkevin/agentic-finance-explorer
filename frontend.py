import streamlit as st
import yfinance as yf
import requests
import time
from datetime import datetime

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="FinAI | Advisor", 
    page_icon="🏦", 
    layout="wide",
    initial_sidebar_state="auto"
)

# --- 2. CUSTOM STYLING ---
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
def get_current_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        price = stock.fast_info['last_price']
        currency = stock.fast_info['currency']
        
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
@st.fragment(run_every=5)
def live_price_sidebar(ticker_symbol):
    price, currency, change = get_current_price(ticker_symbol)
    if price:
        st.metric(
            label=f"Live Price: {ticker_symbol}", 
            value=f"{currency} {price:.2f}",
            delta=f"{change:.2f} Today"
        )

# --- 5. SESSION STATE INITIALIZATION ---
# [CHANGE] Added Session State to prevent the sidebar and results from disappearing on reruns
if "is_analyzing" not in st.session_state:
    st.session_state.is_analyzing = False
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "analysis_source" not in st.session_state:
    st.session_state.analysis_source = None
if "current_ticker" not in st.session_state:
    st.session_state.current_ticker = None

# --- 6. MAIN UI LOGIC ---
def main():
    st.title("🏦 AI Financial Committee")
    st.subheader("Multi-Agent Equity Research & Risk Audit")

    # --- SIDEBAR CONFIGURATION ---
    with st.sidebar:
        st.header("⚙️ Settings")
        ticker = st.text_input("Stock Ticker", value="RELIANCE.NS").upper()
        
        # [CHANGE] Button now updates session state instead of executing directly within the block
        if st.button("🔍 Execute Analysis", use_container_width=True):
            st.session_state.is_analyzing = True
            st.session_state.analysis_results = None # Clear old data
            st.session_state.current_ticker = ticker
        
        st.markdown("---")
        # [CHANGE] Ensuring the sidebar fragment stays active regardless of app state
        if ticker:
            live_price_sidebar(ticker)

    # --- ANALYSIS EXECUTION ---
    # [CHANGE] Logic now relies on session state to persist through fragment reruns
    if st.session_state.is_analyzing and st.session_state.current_ticker:
        # [CHANGE] Used status box that can be updated to "complete" later
        with st.status(f"Waking up agents for {st.session_state.current_ticker}...", expanded=True) as status_box:
            
            # Only run the API call if we haven't already saved the results
            if st.session_state.analysis_results is None:
                try:
                    # [ACTION REQUIRED] Verify this URL is correct for your Render backend
                    backend_url = "https://agentic-finance-explorer.onrender.com" 
                    response = requests.post(f"{backend_url}/analyze", json={"ticker": st.session_state.current_ticker})
                    
                    if response.status_code == 200:
                        data = response.json()

                        if data.get("status") == "completed":
                            # Save to state and jump to display
                            st.session_state.analysis_results = data.get("result")
                            st.session_state.analysis_source = data.get("source")
                            status_box.update(label="Analysis Retrieved from Cache!", state="complete", expanded=False)
                        else:
                            job_id = data.get("job_id")
                            
                            max_attempts = 20
                            attempts = 0
                            
                            while attempts < max_attempts:
                                poll_res = requests.get(f"{backend_url}/status/{job_id}")
                                
                                if poll_res.status_code != 200:
                                    status_box.update(label="Backend lost connection.", state="error")
                                    st.session_state.is_analyzing = False
                                    break
                                    
                                poll_data = poll_res.json()
                                current_status = poll_data.get("status")
        
                                if current_status == "completed":
                                    st.session_state.analysis_results = poll_data.get("result")
                                    st.session_state.analysis_source = "Live Agent Analysis"
                                    # [CHANGE] Update status box to collapse and show green check
                                    status_box.update(label="Analysis Complete!", state="complete", expanded=False)
                                    break 
                                
                                elif current_status == "failed":
                                    status_box.update(label=f"Analysis failed: {poll_data.get('error')}", state="error")
                                    st.session_state.is_analyzing = False
                                    break
                                
                                elif current_status == "not_found":
                                    status_box.update(label="Job lost by server. Restarting...", state="error")
                                    st.session_state.is_analyzing = False
                                    break 
        
                                # [CHANGE] Update the status box text dynamically instead of printing new lines
                                status_box.update(label=f"🕵️ Committee is debating... (Step {attempts+1}/{max_attempts})", state="running")
                                
                                time.sleep(5)
                                attempts += 1
                            
                            if attempts >= max_attempts:
                                status_box.update(label="The agents are taking too long. Please try again.", state="error")
                                st.session_state.is_analyzing = False
                    
                    else:
                        status_box.update(label="Backend Handshake Failed. Check Render URL.", state="error")
                        st.session_state.is_analyzing = False
                except Exception as e:
                    status_box.update(label=f"System Error: {str(e)}", state="error")
                    st.session_state.is_analyzing = False

        # --- DISPLAY RESULTS ---
        # [CHANGE] Pulled data from session state so it doesn't vanish on UI updates
        result = st.session_state.analysis_results
        if result:
            source = st.session_state.analysis_source
            
            if "Intelligence" in source:
                st.info(f"📁 Source: {source} (Price Stable)")
            else:
                st.success(f"🟢 Source: {source}")

            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Technical Signal", result.get('technical_signal', 'N/A'))
            with m2:
                st.metric("Sentiment Score", f"{result.get('sentiment_score', 0)}/10")
            with m3:
                st.metric("Recommendation", result.get('recommendation', 'N/A'))

            col_main, col_side = st.columns([2, 1])
            
            with col_main:
                st.markdown("### 📝 Executive Summary")
                # [CHANGE] Attempt to get 'summary' first, fallback to a truncated 'risk_summary' if missing, to prevent identical text in both columns
                summary_text = result.get('summary')
                if not summary_text:
                     # Fallback: slice the first sentence of the risk summary for the main column
                     raw = result.get('risk_summary', 'No summary available.')
                     summary_text = raw.split('.')[0] + "." if '.' in raw else raw
                st.write(summary_text)
                
            with col_side:
                st.markdown("### 🛡️ Risk Audit")
                # [CHANGE] Ensure the risk bullets skip the first sentence if we used it as the fallback summary
                raw_risks = result.get('risk_summary', '').split('.')
                clean_risks = [r.strip() for r in raw_risks if len(r) > 10]
                
                # If we used the fallback above, skip the first bullet to avoid repetition
                if not result.get('summary') and len(clean_risks) > 1:
                    clean_risks = clean_risks[1:5]
                else:
                    clean_risks = clean_risks[:4]

                for r in clean_risks:
                    st.markdown(f'<div class="risk-bullet">⚠️ {r}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()