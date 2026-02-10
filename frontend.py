import streamlit as st
import requests
import time

st.set_page_config(page_title="AI Financial Committee", layout="wide")

st.title("🤖 AI Stock Investment Committee")
st.markdown("Enter an Indian Stock Ticker (e.g., **RELIANCE**, **TCS**, **HDFCBANK**)")

# Sidebar for Input
ticker = st.sidebar.text_input("NSE Ticker", value="RELIANCE")
if not ticker.endswith(".NS"):
    ticker = f"{ticker}.NS"

analyze_button = st.sidebar.button("Run Multi-Agent Analysis")

# Use your Render URL here!
API_URL = "https://agentic-finance-.onrender.com" 

if analyze_button:
    with st.spinner(f"Agents are collaborating on {ticker}... This takes ~60 seconds."):
        # 1. Start Analysis
        try:
            res = requests.post(f"{API_URL}/analyze", json={"ticker": ticker})
            job_id = res.json().get("job_id")
            
            if not job_id and res.json().get("status") == "completed":
                # Handle cached results immediately
                data = res.json().get("result")
            else:
                # 2. Poll for status
                completed = False
                while not completed:
                    status_res = requests.get(f"{API_URL}/status/{job_id}").json()
                    if status_res["status"] == "completed":
                        data = status_res["result"]
                        completed = True
                    elif status_res["status"] == "failed":
                        st.error("Analysis Failed.")
                        break
                    time.sleep(5) # Poll every 5 seconds
            
            # 3. Display Results in Beautiful Cards
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Technical Signal")
                st.info(data.get("technical_signal", "N/A"))
                
                st.subheader("📰 Sentiment Score")
                st.metric(label="Market Sentiment", value=f"{data.get('sentiment_score', 0)}/10")

            with col2:
                st.subheader("⚠️ Risk Audit")
                st.warning(data.get("risk_summary", "No risks identified."))
            
            st.divider()
            st.subheader("💡 Final Recommendation")
            st.success(data.get("recommendation", "Neutral"))
            
        except Exception as e:
            st.error(f"Could not connect to API: {e}")

st.sidebar.markdown("---")
st.sidebar.caption("Built with CrewAI, FastAPI, and GPT-4o-mini")