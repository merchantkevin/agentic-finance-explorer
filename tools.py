import pandas as pd
import yfinance as yf
import pandas_ta as ta
from crewai.tools import tool

@tool("stock_price_analyzer")
def stock_price_analyzer(ticker: str):
    """
    Pulls historical data for an Indian stock (NSE) and calculates 
    RSI and 20-day Moving Average.
    """
    if not ticker.endswith(".NS"):
        ticker = f"{ticker}.NS"
        
    # auto_adjust=True ensures we get a consistent 'Close' column
    data = yf.download(ticker, period="1mo", interval="1d", auto_adjust=True)
    
    if data.empty:
        return f"Error: No data found for {ticker}."

    # FIX: Flatten MultiIndex columns if they exist
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    # Calculate indicators
    data['RSI'] = ta.rsi(data['Close'], length=14)
    data['MA20'] = ta.sma(data['Close'], length=20)
    
    # Get the last row values as scalar floats
    # .item() or float() on a single-element selection is the safest way
    last_row = data.iloc[-1]
    
    current_price = float(last_row['Close'])
    
    # Handle NaN values for RSI/MA
    rsi_val = last_row['RSI']
    ma_val = last_row['MA20']
    
    # Convert to strings for the agent
    rsi_str = f"{float(rsi_val):.2f}" if pd.notnull(rsi_val) else "Calculating..."
    ma_str = f"{float(ma_val):.2f}" if pd.notnull(ma_val) else "Calculating..."

    return (f"--- Data for {ticker} ---\n"
            f"Price: ₹{current_price:.2f}\n"
            f"RSI: {rsi_str}\n"
            f"MA20: ₹{ma_str}\n")