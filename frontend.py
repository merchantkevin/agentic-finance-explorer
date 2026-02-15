import streamlit as st
import requests
import time
from datetime import datetime
from bs4 import BeautifulSoup
import yfinance as yf
import plotly.graph_objects as go

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
    [data-testid="InputInstructions"] { display: none !important; }
    /* Fixes the wrapping issue - forces numbers to stay on one line */
    [data-testid="stMetricValue"] > div { 
        font-size: 1.3rem !important; 
        font-weight: 700 !important;
        white-space: nowrap !important; 
    }
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
    .legal-disclaimer {
        margin-top: 50px; padding: 15px; border-top: 1px solid #e2e8f0;
        font-size: 0.8rem; color: #64748b; text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import yfinance as yf

# --- 3. THE SMART PRICE ENGINE (Groww + Google + Auto-Router) ---
def get_current_price(ticker):
    ticker_upper = ticker.upper().strip()
    
    # 1. Clean the ticker (remove all suffixes)
    clean_ticker = ticker_upper.replace('.NSE', '').replace('.NS', '').replace('.BO', '').replace('.BSE', '').strip()
    
    # 2. The Smart Router: BSE strictly requires 6-digit Scrip Codes (e.g. 500325)
    # If the ticker contains letters (e.g. RELIANCE), we MUST route to NSE. 
    if clean_ticker.isdigit():
        groww_exchange = "BSE"
        google_exchange = "BOM"
    else:
        groww_exchange = "NSE"
        google_exchange = "NSE"
        
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}

    # ---------------------------------------------------------
    # ATTEMPT 1: Groww JSON API (Fastest)
    # ---------------------------------------------------------
    try:
        url = f"https://groww.in/v1/api/stocks_data/v1/tr_live_prices/exchange/{groww_exchange}/segment/CASH/{clean_ticker}/latest"
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            price = float(data.get('ltp', 0.0))
            prev_close = float(data.get('close', 0.0))
            if price > 0:
                return price, "₹", (price - prev_close), datetime.now().weekday() >= 5
    except Exception:
        pass

    # ---------------------------------------------------------
    # ATTEMPT 2: Google Finance Fallback
    # ---------------------------------------------------------
    try:
        url = f"https://www.google.com/finance/quote/{clean_ticker}:{google_exchange}"
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        price_div = soup.find('div', {'data-last-price': True})
        if price_div:
            price = float(price_div['data-last-price'])
            prev_close_div = soup.find('div', {'data-previous-close': True})
            change = price - float(prev_close_div['data-previous-close']) if prev_close_div else 0.0
            return price, "₹", change, datetime.now().weekday() >= 5
    except Exception:
        pass
        
    # ---------------------------------------------------------
    # ATTEMPT 3: The Yahoo Finance Safety Net (For BSE-exclusive microcaps)
    # ---------------------------------------------------------
    try:
        # If the user typed an alphabetic BSE ticker (like a BSE-only penny stock),
        # yfinance is the only library that can successfully map the '.BO' letters.
        stock = yf.Ticker(ticker_upper)
        hist = stock.history(period="5d")
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else price
            return price, "₹", (price - prev_close), datetime.now().weekday() >= 5
    except Exception:
        pass

    # Complete Failure
    return None, None, None, False

@st.cache_data(ttl=1800) # Cache for 1 hour so it's instantly fast
def get_fundamentals(ticker):
    try:
        # We use yfinance here because historical data is stable, unlike live prices
        yf_ticker = ticker if (ticker.endswith('.NS') or ticker.endswith('.BO')) else ticker + '.NS'
        info = yf.Ticker(yf_ticker).info
        mcap = info.get('marketCap', 0)
        mcap_str = f"₹{mcap/1e7:.2f} Cr" if mcap > 1e7 else "N/A"
        pe = info.get('trailingPE', 'N/A')
        return {
            "mcap": mcap_str,
            "pe": f"{pe:.2f}" if isinstance(pe, (int, float)) else "N/A",
            "high52": info.get('fiftyTwoWeekHigh', 'N/A'),
            "low52": info.get('fiftyTwoWeekLow', 'N/A')
        }
    except:
        return {"mcap": "N/A", "pe": "N/A", "high52": "N/A", "low52": "N/A"}

# --- 4. UI FRAGMENTS ---
@st.fragment(run_every=10) 
def live_price_sidebar(ticker_symbol):
    price, currency, change, is_weekend = get_current_price(ticker_symbol)
    if price:
        st.metric(label=f"Live Price: {ticker_symbol}", value=f"{currency} {price:.2f}", delta=f"{change:.2f} Today")
        st.caption("⏸ Market Closed" if is_weekend else "🟢 Market Open")

        # FEATURE 3: Minimalist Fundamentals inside a collapsible expander
        with st.expander("📊 Fundamental Snapshot", expanded=False):
            funds = get_fundamentals(ticker_symbol)
            
            st.metric(
                label="Market Cap", 
                value=funds['mcap'], 
                help="The total price tag of the entire company. If you wanted to buy every single share of this business today, this is how much it would cost."
            )
            st.metric(
                label="P/E Ratio", 
                value=funds['pe'], 
                help="How expensive the stock is compared to the actual profit the company makes. A lower number usually means you are getting a better deal."
            )
            st.metric(
                label="52-Week Range", 
                value=f"₹{funds['low52']} - ₹{funds['high52']}", 
                help="The absolute highest and lowest price this stock has sold for over the last year."
            )
    else:
        st.warning("⚠️ Market data unavailable.")

@st.fragment
def render_interactive_chart(ticker):
    st.markdown("### 📈 Price Action")
    
    # Chart Controls
    col1, col2 = st.columns([1, 1])
    with col1:
        chart_type = st.radio("Type", ["Line", "Candlestick"], horizontal=True, label_visibility="collapsed")
    with col2:
        timeframe = st.radio("Time", ["1D", "1M", "3M", "6M"], horizontal=True, label_visibility="collapsed", index=3)
        
    # Map selection to yfinance parameters
    tf_map = {"1D": ("1d", "5m"), "1M": ("1mo", "1d"), "3M": ("3mo", "1d"), "6M": ("6mo", "1d")}
    period, interval = tf_map[timeframe]
    
    try:
        # THE FIX 1: Smart Router for the Chart (handles BSE numerical tickers correctly)
        ticker_upper = ticker.upper().strip()
        clean_ticker = ticker_upper.replace('.NS', '').replace('.BO', '').replace('.BSE', '').strip()
        
        yf_ticker = ticker_upper
        if not clean_ticker.isdigit() and not yf_ticker.endswith('.NS'):
            yf_ticker = f"{clean_ticker}.NS"
        elif clean_ticker.isdigit() and not yf_ticker.endswith('.BO'):
            yf_ticker = f"{clean_ticker}.BO"
            
        hist = yf.Ticker(yf_ticker).history(period=period, interval=interval)
        
        # THE FIX 2: The Weekend 1D Intraday Bug 
        # yfinance often returns empty data on weekends for 1d. We fetch 5d and slice the last day.
        if hist.empty and period == "1d":
            hist = yf.Ticker(yf_ticker).history(period="5d", interval=interval)
            if not hist.empty:
                last_day = hist.index[-1].date()
                hist = hist[hist.index.date == last_day]
        
        if not hist.empty:
            fig = go.Figure()
            if chart_type == "Candlestick":
                fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close']))
            else:
                fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], mode='lines', line=dict(color='#2563eb', width=2)))
                
            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                height=350,
                xaxis_rangeslider_visible=False,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            plotly_config = {
                'displaylogo': False,
                'modeBarButtonsToRemove': [
                    'zoom2d', 'pan2d', 'select2d', 'lasso2d', 
                    'zoomIn2d', 'zoomOut2d', 'resetScale2d'
                ]
            }
            
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
        else:
            st.warning("⚠️ Chart data currently unavailable for this ticker.")
    except Exception as e:
        st.error(f"Could not load chart: {e}")

# --- 5. SESSION STATE & TRIGGERS ---
if "is_analyzing" not in st.session_state: st.session_state.is_analyzing = False
if "analysis_results" not in st.session_state: st.session_state.analysis_results = None
if "analysis_source" not in st.session_state: st.session_state.analysis_source = None
if "current_ticker" not in st.session_state: st.session_state.current_ticker = None
if "ticker_input" not in st.session_state: st.session_state.ticker_input = ""

def trigger_analysis():
    # THE FIX: Only trigger the AI if the user actually typed something
    if st.session_state.ticker_input.strip():
        st.session_state.is_analyzing = True
        st.session_state.analysis_results = None
        st.session_state.current_ticker = st.session_state.ticker_input.upper().strip()
    else:
        st.session_state.is_analyzing = False

# --- 6. MAIN UI LOGIC ---
def main():
    st.title("🔬 AI Investment Research Assistant")
    st.subheader("Autonomous Information Synthesis & Risk Highlighting")

    with st.sidebar:
        #st.header("⚙️ Settings")
        # THE FIX: Added the placeholder parameter
        st.text_input(
            "Stock Ticker", 
            key="ticker_input", 
            placeholder="e.g. RELIANCE.NS", 
            on_change=trigger_analysis
        )
        
        st.button("🔍 Analyze Data", use_container_width=True, on_click=trigger_analysis)
        st.markdown("---")
        
        # This automatically hides the live price/fundamentals if the input is empty!
        if st.session_state.ticker_input.strip():
            live_price_sidebar(st.session_state.ticker_input.upper().strip())

    if st.session_state.is_analyzing and st.session_state.current_ticker:
        if st.session_state.analysis_results is None:
            with st.status(f"Agents synthesizing data for {st.session_state.current_ticker}...", expanded=True) as status_box:
                try:                    
                    backend_url = "https://agentic-finance-explorer.onrender.com" 
                    response = requests.post(f"{backend_url}/analyze", json={"ticker": st.session_state.current_ticker})
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "completed":
                            st.session_state.analysis_results, st.session_state.analysis_source = data.get("result"), data.get("source")
                            status_box.update(label="Intelligence Retrieved!", state="complete", expanded=False)
                            time.sleep(1)
                            st.rerun() 
                        else:
                            job_id = data.get("job_id")
                            max_attempts, attempts = 25, 0
                            while attempts < max_attempts:
                                poll_res = requests.get(f"{backend_url}/status/{job_id}")
                                if poll_res.status_code != 200: break
                                poll_data = poll_res.json()
                                current_status = poll_data.get("status")
        
                                if current_status == "completed":
                                    st.session_state.analysis_results, st.session_state.analysis_source = poll_data.get("result"), "Live Agent Analysis"
                                    status_box.update(label="Analysis Complete!", state="complete", expanded=False)
                                    #time.sleep(1)
                                    st.rerun() 
                                    break 
                                elif current_status == "failed":
                                    status_box.update(label=f"Analysis failed.", state="error")
                                    break
                                
                                status_box.update(label=f"🕵️ Agents are compiling reports...", state="running")
                                time.sleep(5)
                                attempts += 1
                except Exception as e:
                    status_box.update(label=f"System Error: {str(e)}", state="error")
                    st.session_state.is_analyzing = False

        result = st.session_state.analysis_results
        if result:
            source = st.session_state.analysis_source
            if "Intelligence" in source: st.info(f"📁 Source: {source} (Price Stable Cache)")
            else: st.success(f"🟢 Source: {source}")

            # Top Metrics
            m1, m2 = st.columns(2)
            with m1:
                st.metric(
                    label="Technical Signal", 
                    value=result.get('technical_signal', 'N/A'), 
                    help="The AI's guess on where the price is heading based on recent chart patterns. 'Bullish' means it looks like it will go up, 'Bearish' means it looks like it will go down."
                )
            with m2:
                st.metric(
                    label="Market Sentiment Score", 
                    value=f"{result.get('sentiment_score', 0)}/10", 
                    help="How people feel about the stock right now. 1 means people are panicking and selling. 10 means people are excited and buying."
                )
                        
            # AI Analysis Columns
            col_bull, col_bear = st.columns(2)
            with col_bull:
                st.markdown("### 📈 Key Catalysts")
                catalysts = result.get('key_catalysts', [])
                if isinstance(catalysts, list) and catalysts:
                    for c in catalysts: st.markdown(f'<div class="catalyst-bullet">✅ {c}</div>', unsafe_allow_html=True)
                else: st.write("No positive catalysts identified.")
                
            with col_bear:
                st.markdown("### 🛡️ Risk Audit")
                risks = result.get('risk_summary', [])
                if isinstance(risks, list) and risks:
                    for r in risks: st.markdown(f'<div class="risk-bullet">⚠️ {r}</div>', unsafe_allow_html=True)
                else: st.write("No significant risks identified.")

            # FEATURE 1: Interactive Chart
            render_interactive_chart(st.session_state.current_ticker)
            st.markdown("---")
    
    st.markdown("""
        <div class="legal-disclaimer">
            <strong>Disclaimer:</strong> This application utilizes Large Language Models (LLMs) to synthesize public financial data for informational purposes only. It is not financial advice.
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()