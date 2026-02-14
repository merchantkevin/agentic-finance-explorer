import streamlit as st
import yfinance as yf
import requests
import time
from datetime import datetime
from bs4 import BeautifulSoup

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

# --- 3. IRONCLAD PRICE ENGINE (API + Scraping Fallback + Currency Routing) ---
def get_current_price(ticker):
    # Helper to clean up currency display
    def format_currency(curr):
        if curr == "INR": return "₹"
        if curr == "USD": return "$"
        if curr == "EUR": return "€"
        if curr == "GBP": return "£"
        return curr + " "

    # Helper to guess currency based on ticker suffix if API fails
    def guess_currency(t):
        if t.endswith('.NS') or t.endswith('.BO'): return "₹"
        if t.endswith('.L'): return "£"
        if t.endswith('.DE') or t.endswith('.PA'): return "€"
        if t.endswith('.TO'): return "CAD $"
        return "$" # Default to USD for standard US tickers (AAPL, TSLA)

    # ATTEMPT 1: The standard yfinance API
    try:
        stock = yf.Ticker(ticker)
        
        if hasattr(stock.fast_info, 'last_price'):
            price = stock.fast_info.last_price
            currency = format_currency(stock.fast_info.currency)
        else:
            price = stock.info.get('currentPrice', stock.info.get('previousClose'))
            currency = format_currency(stock.info.get('currency', 'USD'))
            
        if price:
            hist = stock.history(period="5d")
            change = price - hist['Close'].iloc[-2] if len(hist) >= 2 else 0.0
            is_weekend = datetime.now().weekday() >= 5
            return price, currency, change, is_weekend
    except Exception:
        pass # If yfinance fails, silently move to the fallback

    # ATTEMPT 2: Web Scraping Fallback
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Search the HTML for the specific live price tag
        price_tag = soup.find('fin-streamer', {'data-symbol': ticker.upper(), 'data-field': 'regularMarketPrice'})
        
        if price_tag and price_tag.text:
            price = float(price_tag.text.replace(',', ''))
            is_weekend = datetime.now().weekday() >= 5
            
            # Use our router to guess the currency instead of hardcoding "USD"
            guessed_currency = guess_currency(ticker.upper())
            
            return price, guessed_currency, 0.0, is_weekend
            
    except Exception as e:
        print(f"Fallback Scraper Error: {e}")

    # ATTEMPT 3: Complete Failure
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