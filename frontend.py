import streamlit as st
import requests
import time

st.set_page_config(page_title="FinAI | Intelligence", page_icon="🏦", layout="wide")

# Custom UI Styling
st.markdown("""
    <style>
    .report-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border-left: 6px solid #1a73e8; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); color: #1f2937; }
    .risk-box { background-color: #fff5f5; padding: 15px; border-radius: 10px; border: 1px solid #feb2b2; color: #9b2c2c; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏛️ Financial Intelligence Committee")
st.sidebar.header("Agent Controls")

# --- USER INPUT ---
ticker = st.sidebar.text_input("NSE Ticker", value="RELIANCE").upper()
if not ticker.endswith(".NS"): ticker += ".NS"
analyze_btn = st.sidebar.button("Execute Strategic Analysis", use_container_width=True)

# --- CHANGE THIS TO YOUR ACTUAL RENDER URL ---
API_URL = "https://agentic-finance-explorer.onrender.com" 

if analyze_btn:
    with st.spinner(f"Agents are deliberating on {ticker}..."):
        try:
            # Step 1: Request Analysis
            res = requests.post(f"{API_URL}/analyze", json={"ticker": ticker}, timeout=15)
            
            if res.status_code == 200:
                data = res.json()
                
                if data.get("status") == "completed":
                    result = data.get("result")
                else:
                    job_id = data.get("job_id")
                    # Step 2: Polling
                    with st.status("🔍 Agents investigating technicals and news...") as status:
                        while True:
                            status_res = requests.get(f"{API_URL}/status/{job_id}").json()
                            if status_res.get("status") == "completed":
                                result = status_res.get("result")
                                status.update(label="Analysis Complete!", state="complete")
                                break
                            elif status_res.get("status") == "failed":
                                st.error("Agents failed to reach a consensus.")
                                st.stop()
                            time.sleep(5)

                # --- DISPLAY ---
                col1, col2, col3 = st.columns(3)
                col1.metric("Ticker", ticker)
                col2.metric("Signal", result.get('technical_signal', 'N/A'))
                col3.metric("Sentiment", f"{result.get('sentiment_score', 0)}/10")

                st.markdown("---")
                c_main, c_side = st.columns([2, 1])

                with c_main:
                    st.markdown(f"""<div class='report-card'><h4>💡 Recommendation</h4><p>{result.get('recommendation', 'No data available.')}</p></div>""", unsafe_allow_html=True)

                with c_side:
                    st.markdown("#### 🛡️ Risk Audit")
                    st.markdown(f"""<div class='risk-box'>{result.get('risk_summary', 'No immediate threats.')}</div>""", unsafe_allow_html=True)
            else:
                st.error(f"Server Error: {res.status_code}. Check Render logs.")

        except Exception as e:
            st.error(f"Handshake Failed: {e}. Check if Render URL is correct.")

else:
    st.info("Enter a ticker in the sidebar to begin.")