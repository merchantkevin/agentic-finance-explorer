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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
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
    try:
        ticker_upper = ticker.upper().strip()
        clean_ticker = ticker_upper

        for suffix in ['.NSE', '.NS', '.BSE', '.BO']:
            if clean_ticker.endswith(suffix):
                clean_ticker = clean_ticker[:-len(suffix)]
                break

        if clean_ticker.isdigit() or ticker_upper.endswith(('.BO', '.BSE')):
            yf_ticker = f"{clean_ticker}.BO"
        else:
            yf_ticker = f"{clean_ticker}.NS"

        stock = yf.Ticker(yf_ticker)
        fast = stock.fast_info

        try:
            mcap = fast.market_cap if hasattr(fast, 'market_cap') else None
            high52 = fast.year_high if hasattr(fast, 'year_high') else None
            low52 = fast.year_low if hasattr(fast, 'year_low') else None
        except Exception:
            mcap, high52, low52 = None, None, None

        try:
            info = stock.info
            pe = info.get('trailingPE')
        except Exception:
            pe = None

        return {
            "mcap": f"₹{mcap/1e7:.2f} Cr" if mcap and mcap > 1e7 else "N/A",
            "pe": f"{pe:.2f}" if pe and isinstance(pe, (int, float)) else "N/A",
            "high52": f"{high52:.2f}" if high52 and isinstance(high52, (int, float)) else "N/A",
            "low52": f"{low52:.2f}" if low52 and isinstance(low52, (int, float)) else "N/A"
        }

    except Exception as e:
        print(f"❌ Fundamentals Error for {ticker}: {e}")
        return {"mcap": "N/A", "pe": "N/A", "high52": "N/A", "low52": "N/A"}

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