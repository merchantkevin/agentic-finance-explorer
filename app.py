import os
import uuid
import json
import sqlite3
import yfinance as yf
from datetime import datetime, timedelta
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from main import run_financial_analysis

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
# This is the "Shield" that prevents the currentTradingPeriod error
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
        # If price moved < 1% AND it was less than 2 hours ago, return saved data instantly
        if price_change < 0.01 and (datetime.now() - last_run) < timedelta(hours=2):
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
    try:
        # Run CrewAI Agents
        output = run_financial_analysis(ticker)
        
        # Safely extract data
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

        # Get price for the DB record
        final_price = get_safe_price(ticker)
        
        # Save to SQL
        save_to_db(ticker, final_price, analysis_data)
        
        # Update results memory
        results_db[job_id] = {
            "status": "completed", 
            "result": analysis_data,
            "source": "Live Agent Analysis"
        }
        
    except Exception as e:
        print(f"❌ Background Task Failed: {e}")
        results_db[job_id] = {"status": "failed", "error": str(e)}