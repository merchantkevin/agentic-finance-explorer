import streamlit as st
import requests
import time

# --- Page Config ---
st.set_page_config(page_title="FinAI | Advisor", page_icon="🏦", layout="wide")

# --- Custom Styling ---
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
    }
    .report-section {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        border-left: 6px solid #1a73e8;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .risk-item {
        color: #d32f2f;
        background-color: #fdecea;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 8px;
        border-left: 4px solid #d32f2f;
    }
    </style>
    """, unsafe_allow_html=True)

# --- App Header ---
st.title("🏛️ Financial Intelligence Committee")
st.caption("AI-Driven Equity Analysis for Indian Markets")
st.divider()

# --- Inputs ---
ticker = st.sidebar.text_input("NSE Ticker", value="RELIANCE").upper()
if not ticker.endswith(".NS"): ticker += ".NS"
analyze_btn = st.sidebar.button("Execute Strategic Analysis", use_container_width=True)

# --- Helper: Bullet Points ---
def format_bullets(text):
    # Splits by common delimiters and returns clean HTML bullets
    items = text.replace('.', '\n').split('\n')
    return "".join([f'<div class="risk-item">⚠️ {i.strip()}</div>' for i in items if len(i) > 5])

# --- Main Logic ---
API_URL = "https://your-app-name.onrender.com"

if analyze_btn:
    with st.spinner(f"Agents are deliberating on {ticker}..."):
        try:
            res = requests.post(f"{API_URL}/analyze", json={"ticker": ticker})
            data = res.json()
            
            # Poll if job started
            if data.get("status") == "started":
                job_id = data.get("job_id")
                while True:
                    status_res = requests.get(f"{API_URL}/status/{job_id}").json()
                    if status_res["status"] == "completed":
                        result = status_res["result"]
                        break
                    time.sleep(5)
            else:
                result = data.get("result")

            # --- THE CLEAN UI ---
            
            # 1. Top Metrics (Ticker Info)
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Market Ticker", ticker)
            with c2: st.metric("Technical Signal", result.get('technical_signal', 'N/A'))
            with c3: st.metric("Sentiment Score", f"{result.get('sentiment_score', 0)}/10")

            st.markdown("### 📊 Analyst Reports")
            col_main, col_side = st.columns([2, 1])

            with col_main:
                # Recommendation Card
                st.markdown(f"""
                <div class="report-section">
                    <h4 style="margin-top:0;">💡 Committee Recommendation</h4>
                    <p style="font-size:1.1rem; line-height:1.6;">{result.get('recommendation', 'Drafting...')}</p>
                </div>
                """, unsafe_allow_html=True)

            with col_side:
                # Risk Audit Card (Bulleted)
                st.markdown("#### 🛡️ Risk Audit")
                risk_html = format_bullets(result.get('risk_summary', 'No immediate threats identified.'))
                st.markdown(risk_html, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Analysis failed: {e}")

else:
    st.info("👈 Enter a ticker and click the button to see the multi-agent analysis.")