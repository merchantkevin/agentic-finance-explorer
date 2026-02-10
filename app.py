from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import uuid
from main import run_financial_analysis

app = FastAPI(title="AI Financial Analyst API")

# Temporary in-memory database
results_db = {}

class AnalysisRequest(BaseModel):
    ticker: str

@app.get("/")
def read_root():
    return {"message": "Welcome to the AI Financial Analyst API. Use /docs to see the UI."}

@app.post("/analyze")
async def start_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    results_db[job_id] = {"status": "pending", "result": None}
    
    # Add to background because LLMs are slow (30-60 seconds)
    background_tasks.add_task(execute_analysis, job_id, request.ticker)
    
    return {"job_id": job_id, "status": "started"}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    data = results_db.get(job_id)
    if not data:
        return {"error": "Job ID not found"}
    return data

def execute_analysis(job_id: str, ticker: str):
    try:
        # This calls the function in main.py
        output = run_financial_analysis(ticker)
        results_db[job_id] = {"status": "completed", "result": str(output)}
    except Exception as e:
        results_db[job_id] = {"status": "failed", "error": str(e)}