import os
import uuid
import json
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from main import run_financial_analysis
import sqlite3
import yfinance as yf
from datetime import datetime, timedelta

# Create the cabinet if it doesn't exist
def init_db():
    conn = sqlite3.connect('market_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reports 
                 (ticker TEXT PRIMARY KEY, price REAL, timestamp TEXT, data TEXT)''')
    conn.commit()
    conn.close()

init_db() # Run this once when the app starts

app = FastAPI(title="AI Financial Analyst API")

# --- THE SECURITY KEY (CORS) ---
# This tells Render: "It's okay to let my Streamlit site talk to me."
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

results_db = {}

class AnalysisRequest(BaseModel):
    ticker: str

def get_cache_filename(ticker: str):
    return f"cache_{ticker.replace('.', '_')}.json"

@app.get("/")
def home():
    return {"status": "AI Agents Online", "version": "2.0"}

@app.post("/analyze")
async def start_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    ticker = request.ticker.upper()
    
    # 1. Get Live Price
    stock = yf.Ticker(ticker)
    current_price = stock.fast_info['last_price']
    
    # 2. Check the Filing Cabinet
    conn = sqlite3.connect('market_data.db')
    c = conn.cursor()
    c.execute("SELECT price, timestamp, data FROM reports WHERE ticker=?", (ticker,))
    row = c.fetchone()
    conn.close()

    if row:
        old_price, old_time, saved_data = row
        price_change = abs(current_price - old_price) / old_price
        last_run = datetime.fromisoformat(old_time)
        
        # If price moved < 1% AND it was less than 2 hours ago:
        if price_change < 0.01 and (datetime.now() - last_run) < timedelta(hours=2):
            return {"status": "completed", "result": json.loads(saved_data), "source": "cache"}

    # 3. If price moved too much or cabinet is empty, run Agents...
    cache_file = get_cache_filename(ticker)

    # 1. Check Cache
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cached_data = json.load(f)
            return {"status": "completed", "result": cached_data["result"], "source": "cache"}

    # 2. Start Job
    job_id = str(uuid.uuid4())
    results_db[job_id] = {"status": "pending", "result": None}
    background_tasks.add_task(execute_analysis, job_id, ticker)
    
    return {"job_id": job_id, "status": "started"}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    # Ensure we return the dictionary properly
    job_data = results_db.get(job_id)
    if not job_data:
        return {"status": "not_found"}
    return job_data

def execute_analysis(job_id: str, ticker: str):
    try:
        output = run_financial_analysis(ticker)
        
        # CrewAI returns a CrewOutput. We need the JSON dict.
        if hasattr(output, 'json_dict') and output.json_dict:
            analysis_data = output.json_dict
        else:
            # Fallback if AI fails to format JSON correctly
            analysis_data = {
                "ticker": ticker,
                "technical_signal": "Analysis Incomplete",
                "sentiment_score": 5.0,
                "risk_summary": str(output),
                "recommendation": "Agent returned unstructured text. Review manually."
            }

        cache_data = {"timestamp": datetime.now().isoformat(), "result": analysis_data}
        with open(get_cache_filename(ticker), "w") as f:
            json.dump(cache_data, f)
            
        results_db[job_id] = {"status": "completed", "result": analysis_data}
    except Exception as e:
        results_db[job_id] = {"status": "failed", "error": str(e)}