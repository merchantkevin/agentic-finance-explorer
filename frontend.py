import streamlit as st
import yfinance as yf
import requests
import time
from datetime import datetime
from bs4 import BeautifulSoup
import re

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="FinAI | Research Assistant", 
    page_icon="🔬", 
    layout="wide",
    initial_sidebar_state="auto"
)

# --- 2. CUSTOM STYLING ---
st.markdown("""
    <style>
    /* Metric Value Styling */
    [data-testid="stMetricValue"] > div { 
        font-size: 1.2rem !important; 
        font-weight: 700 !important;
        white-space: normal !important; 
        word-break: break-word !important; 
    }
    
    /* Risk & Catalyst Cards */
    .risk-bullet { 
        background-color: #fff5f5; padding: 12px; border-radius: 8px; 
        border-left: 4px solid #9b2c2c; margin-bottom: 10px; 
        font-size: 0.9rem; color: #9b2c2c; line-height: 1.4; 
    }
    .catalyst-bullet { 
        background-color: #f0fdf4; padding: 12px; border-radius: 8px; 
        border-left: 4px solid #166534; margin-bottom: 10px; 
        font-size: 0.9rem; color: #166534; line-height: 1.4; 
    }
    
    /* Footer Disclaimer Styling */
    .legal-disclaimer {
        margin-top: 50px;
        padding: 15px;
        border-top: 1px solid #e2e8f0;
        font-size: 0.8rem;
        color: #64748b;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. THE PRICE ENGINE (Google Finance - India Focused) ---
def get_current_price(ticker):
    """
    Scrapes live price and currency directly from Google Finance.
    Strictly targets Indian Exchanges (NSE, then BSE/BOM).
    """
    # 1. Clean the ticker (remove Yahoo suffixes if the user typed them)
    clean_ticker = ticker.upper().replace('.NS', '').replace('.BO', '').strip()
    
    # We will try NSE first, then BOM (Bombay Stock Exchange)
    exchanges = ['NSE', 'BOM']
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for exchange in exchanges:
        symbol = f"{clean_ticker}:{exchange}"
        url = f"https://www.google.com/finance/quote/{symbol}"
        
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code != 200:
                continue # If not found on NSE, loop will try BOM next
                
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # The specific HTML class Google uses for the main stock price
            price_div = soup.find('div', class_='YMlKec fxKbKc')
            
            if price_div:
                price_text = price_div.text.strip()
                
                # 2. Separate the currency symbol from the numbers
                match = re.match(r"([^\d\.,]+)?([\d\.,]+)", price_text)
                if match:
                    currency = match.group(1) or "₹"
                    price_str = match.group(2).replace(',', '')
                    price = float(price_str)
                    
                    # 3. Grab the daily change
                    change = 0.0
                    change_div = soup.find('div', class_='JwB6zf')
                    if change_div:
                        change_text = change_div.text.strip().replace(',', '')
                        c_match = re.search(r"([+-])?[^\d\.,]*([\d\.,]+)", change_text)
                        if c_match:
                            sign = -1 if c_match.group(1) == '-' else 1
                            change = sign * float(c_match.group(2))
                            
                    is_weekend = datetime.now().weekday() >= 5
                    return price, currency.strip(), change, is_weekend
                    
        except Exception as e:
            print(f"Scraper error for {symbol}: {e}")

    # Complete Failure (Stock not found on NSE or BSE, or network error)
    return None, None, None, False

# --- 4. THE LIVE HEARTBEAT ---
@st.fragment(run_every=10) 
def live_price_sidebar(ticker_symbol):
    price, currency, change, is_weekend = get_current_price(ticker_symbol)
    if price:
        st.metric(
            label=f"Market Price: {ticker_symbol}", 
            value=f"{currency} {price:.2f}",
            delta=f"{change:.2f} (Prev Close)"
        )
        if is_weekend:
            st.caption("⏸ Market Closed (Weekend)")
        else:
            st.caption("🟢 Market Open (Live)")
    else:
        st.warning("⚠️ Market data unavailable.")

# --- 5. SESSION STATE ---
if "is_analyzing" not in st.session_state: st.session_state.is_analyzing = False
if "analysis_results" not in st.session_state: st.session_state.analysis_results = None
if "analysis_source" not in st.session_state: st.session_state.analysis_source = None
if "current_ticker" not in st.session_state: st.session_state.current_ticker = None

# --- 6. MAIN UI LOGIC ---
def main():
    st.title("🔬 AI Equity Research Assistant")
    st.subheader("Autonomous Information Synthesis & Risk Highlighting")

    with st.sidebar:
        st.header("⚙️ Settings")
        ticker = st.text_input("Stock Ticker", value="RELIANCE.NS").upper()
        
        if st.button("🔍 Synthesize Data", use_container_width=True):
            st.session_state.is_analyzing = True
            st.session_state.analysis_results = None 
            st.session_state.current_ticker = ticker
        
        st.markdown("---")
        if ticker:
            live_price_sidebar(ticker)

    # --- ANALYSIS EXECUTION ---
    if st.session_state.is_analyzing and st.session_state.current_ticker:
        
        if st.session_state.analysis_results is None:
            with st.status(f"Agents synthesizing data for {st.session_state.current_ticker}...", expanded=True) as status_box:
                try:
                    backend_url = "https://agentic-finance-explorer.onrender.com" 
                    response = requests.post(f"{backend_url}/analyze", json={"ticker": st.session_state.current_ticker})
                    
                    if response.status_code == 200:
                        data = response.json()

                        if data.get("status") == "completed":
                            st.session_state.analysis_results = data.get("result")
                            st.session_state.analysis_source = data.get("source")
                            status_box.update(label="Intelligence Retrieved!", state="complete", expanded=False)
                            time.sleep(1)
                            st.rerun() 
                        else:
                            job_id = data.get("job_id")
                            max_attempts = 25
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
                                    st.session_state.analysis_source = "Live Agent Synthesis"
                                    status_box.update(label="Synthesis Complete!", state="complete", expanded=False)
                                    time.sleep(1)
                                    st.rerun() 
                                    break 
                                
                                elif current_status == "failed":
                                    status_box.update(label=f"Analysis failed: {poll_data.get('error')}", state="error")
                                    st.session_state.is_analyzing = False
                                    break
                                
                                status_box.update(label=f"🕵️ Interns are compiling reports... (Step {attempts+1}/{max_attempts})", state="running")
                                time.sleep(5)
                                attempts += 1
                            
                            if attempts >= max_attempts:
                                status_box.update(label="Timeout.", state="error")
                                st.session_state.is_analyzing = False
                    else:
                        status_box.update(label="Backend Handshake Failed.", state="error")
                        st.session_state.is_analyzing = False
                except Exception as e:
                    status_box.update(label=f"System Error: {str(e)}", state="error")
                    st.session_state.is_analyzing = False

        # --- DISPLAY RESULTS ---
        result = st.session_state.analysis_results
        if result:
            source = st.session_state.analysis_source
            
            if "Intelligence" in source:
                st.info(f"📁 Source: {source} (Price Stable Cache)")
            else:
                st.success(f"🟢 Source: {source}")

            # Top Metrics with Tooltips (The 'help' parameter adds the hovering '?')
            m1, m2 = st.columns(2)
            with m1:
                st.metric(
                    label="Technical Signal", 
                    value=result.get('technical_signal', 'N/A'),
                    help="Aggregate signal based on moving averages, RSI, and MACD indicators over recent trading sessions."
                )
            with m2:
                st.metric(
                    label="Market Sentiment Score", 
                    value=f"{result.get('sentiment_score', 0)}/10",
                    help="Scale of 1-10. 1 indicates extreme fear/bearish news coverage, while 10 indicates extreme greed/bullish media sentiment."
                )

            st.markdown("---")
            
            # The New Layout: Catalysts vs Risks
            col_bull, col_bear = st.columns(2)
            
            with col_bull:
                st.markdown("### 📈 Key Catalysts (Bull Case)")
                catalysts = result.get('key_catalysts', [])
                if isinstance(catalysts, list) and catalysts:
                    for c in catalysts:
                        st.markdown(f'<div class="catalyst-bullet">✅ {c}</div>', unsafe_allow_html=True)
                else:
                    st.write("No positive catalysts identified.")
                
            with col_bear:
                st.markdown("### 🛡️ Risk Audit (Bear Case)")
                risks = result.get('risk_summary', [])
                if isinstance(risks, list) and risks:
                    for r in risks:
                        st.markdown(f'<div class="risk-bullet">⚠️ {r}</div>', unsafe_allow_html=True)
                else:
                    st.write("No significant risks identified.")

    # --- MANDATORY LEGAL FOOTER ---
    st.markdown("""
        <div class="legal-disclaimer">
            <strong>Disclaimer:</strong> This application utilizes Large Language Models (LLMs) to synthesize public financial data for informational and educational purposes only. It is not a registered investment advisor. The insights, signals, and scores provided do not constitute financial, legal, or tax advice. Always conduct your own due diligence or consult a certified professional before making investment decisions.
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()