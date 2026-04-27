import os
import uuid
import json
import sqlite3
import time
import yfinance as yf
from datetime import datetime, timedelta
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from main import run_financial_analysis
from langfuse import Langfuse
from bs4 import BeautifulSoup

# --- 1. DATABASE CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "market_data.db")

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS reports 
                     (ticker TEXT PRIMARY KEY, price REAL, timestamp TEXT, data TEXT)''')
        conn.commit()
        conn.close()
        print("✅ DB initialized successfully")
    except Exception as e:
        print(f"❌ DB Initialization Error: {e}")

def save_to_db(ticker, price, data_dict):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""REPLACE INTO reports (ticker, price, timestamp, data) 
                     VALUES (?, ?, ?, ?)""", 
                  (ticker, price, datetime.now().isoformat(), json.dumps(data_dict)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Error saving to DB: {e}")

# Initialize DB on startup
init_db()

# --- LANGFUSE OBSERVABILITY CLIENT ---
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)

# --- 2. API SETUP ---
app = FastAPI(title="AI Financial Analyst API")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://agentic-finance-explorer-zrkwkgnuyidyfgbqc8jb4a.streamlit.app"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

results_db = {}

class AnalysisRequest(BaseModel):
    ticker: str

# --- 3. HELPER: SAFE PRICE FETCH ---
def get_safe_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        # We use .fast_info specifically because it avoids the buggy .info block
        price = stock.fast_info.get('last_price')
        if price is None:
            # Fallback if fast_info fails
            price = 0.0
        return price
    except Exception as e:
        print(f"⚠️ YFinance Warning for {ticker}: {e}")
        return 0.0

# --- 4. ROUTES ---
@app.get("/")
def home():
    return {"status": "AI Agents Online", "version": "2.0"}
    
@app.get("/fundamentals/{ticker}")
def get_fundamentals(ticker: str):
    clean = ticker.upper().strip()
    for suffix in ['.NSE', '.NS', '.BSE', '.BO']:
        if clean.endswith(suffix):
            clean = clean[:-len(suffix)]
            break

    result = {
        "mcap": "N/A", "pe": "N/A", "high52": "N/A", "low52": "N/A",
        "book_value": "N/A", "div_yield": "N/A", "roce": "N/A",
        "roe": "N/A", "eps": "N/A", "debt_eq": "N/A"
    }

    def sf(val):
        try:
            return float(str(val).replace(',', '').strip())
        except:
            return None

    def fmt(val, prefix='', suffix='', decimals=2):
        f = sf(val)
        return f"{prefix}{f:.{decimals}f}{suffix}" if f is not None else "N/A"

    def get_row(df, *keys):
        for k in keys:
            if k in df.index:
                val = sf(df.loc[k].iloc[0])
                if val is not None:
                    return val
        return None

    try:
        # Try NSE first, fall back to BSE
        stock = yf.Ticker(f"{clean}.NS")
        fast = stock.fast_info

        # Test if this ticker is valid — fast_info.last_price is None for invalid tickers
        if not getattr(fast, 'last_price', None):
            stock = yf.Ticker(f"{clean}.BO")
            fast = stock.fast_info

        # --- LAYER 1: fast_info — always reliable ---
        shares  = sf(getattr(fast, 'shares', None))
        price   = sf(getattr(fast, 'last_price', None))
        mcap    = sf(getattr(fast, 'market_cap', None))
        yr_high = sf(getattr(fast, 'year_high', None))
        yr_low  = sf(getattr(fast, 'year_low', None))

        if mcap:    result['mcap']   = f"₹{mcap/1e7:,.0f} Cr"
        if yr_high: result['high52'] = f"₹{yr_high:.2f}"
        if yr_low:  result['low52']  = f"₹{yr_low:.2f}"

        # --- LAYER 2: get_info() — try first for derived metrics ---
        info = {}
        try:
            info = stock.get_info() or {}
        except Exception as e:
            print(f"get_info() failed for {clean}: {e}")
       
        if info.get('trailingEps'):   result['eps']        = fmt(info['trailingEps'], prefix='₹')
        if info.get('bookValue'):     result['book_value'] = fmt(info['bookValue'], prefix='₹')
        if info.get('returnOnEquity'):result['roe']        = fmt(info['returnOnEquity'] * 100, suffix='%')
        if info.get('debtToEquity'):  result['debt_eq']    = fmt(info['debtToEquity'])

        # --- LAYER 3: Financial statements — fallback + ROCE ---
        try:
            income_stmt   = stock.get_income_stmt()
            balance_sheet = stock.balance_sheet

            net_income     = get_row(income_stmt,   'Net Income', 'NetIncome')
            ebitda         = get_row(income_stmt,   'Normalized EBITDA', 'EBITDA')
            common_equity  = get_row(balance_sheet, 'Common Stock Equity', 'StockholdersEquity')
            total_debt     = get_row(balance_sheet, 'Total Debt', 'LongTermDebt')   
            invested_cap   = get_row(balance_sheet, 'Invested Capital')
            total_assets   = get_row(balance_sheet, 'Total Assets')
            current_liab   = get_row(balance_sheet, 'Current Liabilities')
            
            # P/E: Price / EPS — calculate directly, don't rely on result['eps'] string
            if result['pe'] == 'N/A' and price and net_income and shares and shares > 0:
                eps_val = net_income / shares
                if eps_val > 0:
                    result['pe'] = f"{price / eps_val:.2f}"

            # Dividend Yield: Annual Dividends Paid / Market Cap * 100
            try:
                cashflow = stock.cashflow
                dividends_paid = get_row(cashflow, 'Cash Dividends Paid', 'Common Stock Dividend Paid')
                if dividends_paid and mcap and mcap > 0:
                    # dividends_paid is negative in cashflow statement, so abs()
                    result['div_yield'] = f"{(abs(dividends_paid) / mcap) * 100:.2f}%"
            except Exception as e:
                print(f"Dividend yield calc error: {e}")
            # Fallback EPS: Net Income / shares
            if result['eps'] == 'N/A' and net_income and shares and shares > 0:
                result['eps'] = f"₹{net_income / shares:.2f}"

            # Fallback Book Value: Common Equity / shares
            if result['book_value'] == 'N/A' and common_equity and shares and shares > 0:
                result['book_value'] = f"₹{common_equity / shares:.2f}"

            # Fallback ROE: Net Income / Common Equity
            if result['roe'] == 'N/A' and net_income and common_equity and common_equity > 0:
                result['roe'] = f"{(net_income / common_equity) * 100:.2f}%"

            # Fallback D/E: Total Debt / Common Equity (as percentage, matching yfinance format)
            if result['debt_eq'] == 'N/A' and total_debt and common_equity and common_equity > 0:
                result['debt_eq'] = fmt((total_debt / common_equity) * 100)

            # ROCE: Net Income / Invested Capital (best approximation from available data)
            # Fall back to Total Assets - Current Liabilities if Invested Capital missing
            capital_employed = invested_cap or (
                (total_assets - current_liab) if total_assets and current_liab else None
            )
            if net_income and capital_employed and capital_employed > 0:
                result['roce'] = f"{(net_income / capital_employed) * 100:.2f}%"

        except Exception as e:
            print(f"Statements fallback error for {clean}: {e}")

    except Exception as e:
        print(f"❌ Fundamentals Error for {ticker}: {e}")

    return result

@app.post("/analyze")
async def start_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    ticker = request.ticker.upper()
    job_id = str(uuid.uuid4())
    
    # 1. Get Live Price safely
    current_price = get_safe_price(ticker)
    
    # 2. Check the SQL Filing Cabinet
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT price, timestamp, data FROM reports WHERE ticker=?", (ticker,))
        row = c.fetchone()
        conn.close()
    except:
        row = None

    if row:
        old_price, old_time, saved_data = row
        last_run = datetime.fromisoformat(old_time)
        
        # Calculate price change if we have a valid current price
        price_change = 0
        if old_price > 0 and current_price > 0:
            price_change = abs(current_price - old_price) / old_price
        
        # SMART CACHE LOGIC: 
        # If price moved < 0.5% AND it was less than 1 hour ago, return saved data instantly
        if price_change < 0.005 and (datetime.now() - last_run) < timedelta(hours=1):
            return {
                "status": "completed", 
                "result": json.loads(saved_data), 
                "source": "Verified Intelligence"
            }

    # 3. If no cache or price moved too much, start the Agents
    results_db[job_id] = {"status": "pending", "result": None}
    background_tasks.add_task(execute_analysis, job_id, ticker)
    
    return {"job_id": job_id, "status": "started"}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job_data = results_db.get(job_id)
    if not job_data:
        return {"status": "not_found"}
    return job_data

# --- 5. BACKGROUND ENGINE ---
def execute_analysis(job_id: str, ticker: str):
    # --- START LANGFUSE TRACE ---
    # A "trace" is one complete run of the analysis for a ticker.
    # Think of it like opening a logbook entry for this job.
    start_time = time.time()

    trace = langfuse.trace(
        name="stock-analysis",
        metadata={
            "ticker": ticker,
            "job_id": job_id
        },
        tags=[ticker]
    )

    try:
        # --- START A SPAN FOR THE CREWAI RUN ---
        # A "span" is a timed section inside the trace.
        # This one measures exactly how long the CrewAI agents take.
        crew_span = trace.span(
            name="crewai-kickoff",
            input={"ticker": ticker}
        )

        # Run CrewAI Agents (nothing changed here)
        output = run_financial_analysis(ticker)

        # Calculate how long the agents took
        latency = round(time.time() - start_time, 2)

        # --- END THE CREWAI SPAN ---
        crew_span.end(
            output={"status": "success"},
            metadata={"latency_seconds": latency}
        )

        # Safely extract data (nothing changed here)
        if hasattr(output, 'json_dict') and output.json_dict:
            analysis_data = output.json_dict
        else:
            analysis_data = {
                "ticker": ticker,
                "technical_signal": "Analysis Incomplete",
                "sentiment_score": 5.0,
                "risk_summary": str(output),
                "recommendation": "Manual Review Required"
            }

        # Get price for the DB record (nothing changed here)
        final_price = get_safe_price(ticker)

        # Save to SQL (nothing changed here)
        save_to_db(ticker, final_price, analysis_data)

        # Update results memory (nothing changed here)
        results_db[job_id] = {
            "status": "completed",
            "result": analysis_data,
            "source": "Live Agent Analysis"
        }

        # --- UPDATE TRACE WITH FINAL RESULT ---
        # Now that we have the result, attach it to the trace.
        # This is what you'll see in the Langfuse dashboard.
        trace.update(
            output={
                "technical_signal": analysis_data.get("technical_signal"),
                "sentiment_score": analysis_data.get("sentiment_score"),
                "status": "completed"
            },
            metadata={
                "ticker": ticker,
                "latency_seconds": latency,
                "job_id": job_id,
                "fallback_used": not (hasattr(output, 'json_dict') and output.json_dict)
            }
        )

    except Exception as e:
        # --- LOG THE FAILURE TO LANGFUSE ---
        latency = round(time.time() - start_time, 2)
        print(f"❌ Background Task Failed: {e}")
        results_db[job_id] = {"status": "failed", "error": str(e)}

        trace.update(
            metadata={
                "ticker": ticker,
                "job_id": job_id,
                "status": "failed",
                "error": str(e),
                "latency_seconds": latency
            }
        )

    finally:
        # --- FLUSH ENSURES DATA IS SENT ---
        # Langfuse batches data before sending. flush() forces it to send now.
        # This is important in background tasks where the process might end
        # before the batch is sent automatically.
        langfuse.flush()