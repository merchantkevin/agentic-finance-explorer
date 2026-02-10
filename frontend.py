import streamlit as st
import requests
import time

st.set_page_config(page_title="AI Financial Committee", layout="wide")

st.title("🤖 AI Stock Investment Committee")

# 1. FIX YOUR URL HERE
# Make sure there is NO trailing slash at the end
API_URL = "https://agentic-finance-explorer.onrender.com" 

ticker = st.sidebar.text_input("NSE Ticker (e.g. RELIANCE)", value="RELIANCE")
analyze_button = st.sidebar.button("Run Analysis")

if analyze_button:
    formatted_ticker = ticker.strip().upper()
    if not formatted_ticker.endswith(".NS"):
        formatted_ticker += ".NS"

    with st.spinner(f"Agents are analyzing {formatted_ticker}..."):
        try:
            # Send the request
            response = requests.post(
                f"{API_URL}/analyze", 
                json={"ticker": formatted_ticker},
                timeout=10
            )
            
            # DEBUG: If it's not a success code, show the raw text
            if response.status_code != 200:
                st.error(f"Server Error ({response.status_code}): {response.text}")
            else:
                res_json = response.json()
                job_id = res_json.get("job_id")
                
                # If it was a cached result
                if res_json.get("status") == "completed":
                    st.success("Analysis found in cache!")
                    st.json(res_json.get("result"))
                else:
                    # Polling for background job
                    status_area = st.empty()
                    completed = False
                    while not completed:
                        status_area.write("⏱️ Agents are still working...")
                        status_res = requests.get(f"{API_URL}/status/{job_id}").json()
                        
                        if status_res["status"] == "completed":
                            status_area.empty()
                            st.subheader(f"Final Report for {formatted_ticker}")
                            st.write(status_res["result"])
                            completed = True
                        elif status_res["status"] == "failed":
                            st.error(f"Agent Error: {status_res.get('error')}")
                            break
                        time.sleep(5)

        except Exception as e:
            st.error(f"Connection Failed: {e}")