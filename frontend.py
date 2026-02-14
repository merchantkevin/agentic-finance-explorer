import streamlit as st
import yfinance as yf
import requests
import time

# --- STYLING & PAGE CONFIG ---
st.set_page_config(page_title="FinAI", layout="wide")

st.markdown("""
    <style>
    .risk-bullet { 
        background-color: #fff5f5; padding: 12px; border-radius: 8px; 
        border-left: 4px solid #9b2c2c; margin-bottom: 10px; 
        font-size: 0.85rem; color: #9b2c2c; line-height: 1.4; 
    }
    </style>
""", unsafe_allow_html=True)

# --- ENGINE ---
def fetch_live_data(ticker):
    try:
        s = yf.Ticker(ticker)
        p = s.fast_info['last_price']
        h = s.history(period="1d")
        d = p - h['Open'].iloc[-1] if not h.empty else 0
        return p, s.fast_info.get('currency', 'USD'), d
    except: return None, None, None

@st.fragment(run_every=5)
def sidebar_ticker(ticker):
    p, c, d = fetch_live_data(ticker)
    if p: 
        st.metric(label=f"Live Price ({ticker})", value=f"{c} {p:.2f}", delta=f"{d:.2f} Today")

# --- STATE MANAGEMENT (Fixes Phase 4) ---
# We store the state so the app doesn't forget what it's doing when the fragment ticks
if "is_analyzing" not in st.session_state:
    st.session_state.is_analyzing = False
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "analysis_source" not in st.session_state:
    st.session_state.analysis_source = None

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    ticker = st.text_input("Ticker", value="RELIANCE.NS").upper()
    
    # When clicked, we update the session state
    if st.button("🔍 Run AI Audit", use_container_width=True):
        st.session_state.is_analyzing = True
        st.session_state.analysis_results = None # Clear old data
    
    st.markdown("---")
    # This now stays permanently at the bottom, unaffected by the main loop
    if ticker:
        sidebar_ticker(ticker)

# --- MAIN LOGIC ---
if st.session_state.is_analyzing:
    
    # Phase 3 Fix: Dynamic Status Box
    with st.status(f"Initializing agents for {ticker}...", expanded=True) as status_box:
        
        # Only run the API call if we haven't already saved the results to session state
        if st.session_state.analysis_results is None:
            try:
                # Replace with your Render URL
                URL = "https://your-backend-url.onrender.com"
                res = requests.post(f"{URL}/analyze", json={"ticker": ticker})
                
                if res.status_code == 200:
                    data = res.json()
                    
                    if data.get("status") == "completed":
                        st.session_state.analysis_results = data["result"]
                        st.session_state.analysis_source = data["source"]
                        status_box.update(label="Analysis Retrieved from Cache!", state="complete", expanded=False)
                    else:
                        job_id = data["job_id"]
                        
                        # Polling Loop
                        for _ in range(30):
                            status_box.update(label=f"🕵️ Committee is debating... (Tick {_+1}/30)", state="running")
                            p_res = requests.get(f"{URL}/status/{job_id}").json()
                            
                            if p_res.get("status") == "completed":
                                st.session_state.analysis_results = p_res["result"]
                                st.session_state.analysis_source = "Live Agent Analysis"
                                status_box.update(label="Analysis Complete!", state="complete", expanded=False)
                                break
                            elif p_res.get("status") == "failed":
                                status_box.update(label="Agents failed to reach consensus.", state="error")
                                st.session_state.is_analyzing = False
                                break
                                
                            time.sleep(5)
                else:
                    status_box.update(label="Backend unreachable.", state="error")
                    st.session_state.is_analyzing = False
            except Exception as e:
                status_box.update(label=f"Error: {e}", state="error")
                st.session_state.is_analyzing = False

    # --- RENDER RESULTS ---
    # We pull from session_state so it survives the 5-second fragment reruns
    res_data = st.session_state.analysis_results
    
    if res_data:
        source = st.session_state.analysis_source
        if "Intelligence" in source:
            st.info(f"📁 Source: {source} (Price Stable)")
        else:
            st.success(f"🟢 Source: {source}")

        # Top Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Technical Signal", res_data.get('technical_signal', 'N/A'))
        m2.metric("Sentiment Score", f"{res_data.get('sentiment_score', 'N/A')}/10")
        m3.metric("Recommendation", res_data.get('recommendation', 'N/A'))

        st.markdown("---")
        
        # Phase 2 Fix: Separate Executive Summary and Risk Audit
        col1, col2 = st.columns([1.5, 1])
        
        with col1:
            st.markdown("### 📝 Executive Summary")
            # Assumes your AI outputs a 'summary' key. If not, fallback to a slice of risk_summary.
            summary_text = res_data.get('summary', res_data.get('risk_summary', 'No summary available.'))
            st.write(summary_text)
            
        with col2:
            st.markdown("### 🛡️ Risk Audit")
            # Extracts risks by splitting sentences, ensuring they look different from the main summary
            raw_risks = res_data.get('risk_summary', '').split('.')
            clean_risks = [r.strip() for r in raw_risks if len(r) > 15][:4] # Take top 4 long points
            
            if clean_risks:
                for r in clean_risks:
                    st.markdown(f'<div class="risk-bullet">⚠️ {r}.</div>', unsafe_allow_html=True)
            else:
                st.info("No significant risks flagged.")