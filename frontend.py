import streamlit as st
import requests
import time

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Financial Committee",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS for Visual Flair ---
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .report-card {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 15px;
        border-left: 5px solid #007bff;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .risk-card {
        background-color: #fff5f5;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #feb2b2;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2534/2534351.png", width=80)
st.sidebar.title("Control Panel")
st.sidebar.markdown("---")
ticker_input = st.sidebar.text_input("Enter NSE Ticker", value="RELIANCE", help="e.g. INFY, TCS, HDFCBANK")
analyze_button = st.sidebar.button("🚀 Execute Analysis", use_container_width=True)

# --- Header Section ---
st.title("🏛️ AI Investment Committee")
st.caption("Multi-Agent Intelligence for Indian Equity Markets")
st.divider()

# --- Logic & API Call ---
API_URL = "https://agentic-finance-explorer.onrender.com" # <--- ENSURE THIS IS CORRECT

if analyze_button:
    ticker = ticker_input.strip().upper()
    if not ticker.endswith(".NS"):
        ticker += ".NS"

    with st.spinner("🤖 **Committee is debating...** Fetching data and searching news."):
        try:
            response = requests.post(f"{API_URL}/analyze", json={"ticker": ticker}, timeout=15)
            
            if response.status_code == 200:
                res_json = response.json()
                job_id = res_json.get("job_id")
                
                # Check for completed/cached results
                if res_json.get("status") == "completed":
                    data = res_json.get("result")
                else:
                    # Polling
                    placeholder = st.empty()
                    while True:
                        status_res = requests.get(f"{API_URL}/status/{job_id}").json()
                        if status_res["status"] == "completed":
                            data = status_res["result"]
                            placeholder.empty()  # NEW: Safety check - if data is a string, try to parse it as JSON
                            if isinstance(data, str):
                                try:
                                    data = json.loads(data)
                                except:
                                    # If it's totally unparsable, make it a dummy dict
                                    data = {"recommendation": data, "risk_summary": "Check raw output."}
    
                                # Now .get() will always work!
                                st.subheader(f"Final Report for {ticker}")
                            break
                        elif status_res["status"] == "failed":
                            st.error(f"Analysis Failed: {status_res.get('error')}")
                            st.stop()
                        placeholder.info("🕵️ Agents are investigating technicals and news headlines...")
                        time.sleep(5)

                # --- CREATIVE DATA DISPLAY ---
                
                # 1. Top Metrics Bar
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("Ticker", ticker)
                with m2:
                    sentiment = data.get("sentiment_score", 5)
                    st.metric("Sentiment Score", f"{sentiment}/10", delta=sentiment-5)
                with m3:
                    signal = data.get("technical_signal", "Neutral")
                    st.metric("Signal", signal, delta_color="normal")

                st.markdown("<br>", unsafe_allow_html=True)

                # 2. Main Body Columns
                col_left, col_right = st.columns([2, 1])

                with col_left:
                    st.markdown(f"""
                    <div class="report-card">
                        <h3>📋 Executive Summary</h3>
                        <p style="font-size: 1.1rem; color: #4a5568;">{data.get('recommendation', 'No recommendation available.')}</p>
                    </div>
                    """, unsafe_allow_html=True)

                with col_right:
                    st.markdown(f"""
                    <div class="risk-card">
                        <h4>⚠️ Risk Audit</h4>
                        <p style="font-size: 0.95rem;">{data.get('risk_summary', 'Low risk environment.')}</p>
                    </div>
                    """, unsafe_allow_html=True)

                st.success("✅ Analysis Complete. This report is stored in memory for 24 hours.")

            else:
                st.error(f"API Error: {response.text}")

        except Exception as e:
            st.error(f"Could not connect to the agents: {e}")
else:
    # Default State
    st.info("👈 Enter a ticker in the sidebar and click Execute to start the agentic workflow.")
    
    # Optional: Display some "Latest Trends" or static data here to make it look full
    c1, c2, c3 = st.columns(3)
    c1.image("https://img.icons8.com/clouds/100/000000/chart.png")
    c2.image("https://img.icons8.com/clouds/100/000000/news.png")
    c3.image("https://img.icons8.com/clouds/100/000000/shield.png")