# test_all.py
import yfinance as yf
import json

stock = yf.Ticker("RELIANCE.NS")

print("=== fast_info ===")
fi = stock.fast_info
print({k: getattr(fi, k, 'N/A') for k in [
    'last_price', 'market_cap', 'year_high', 'year_low',
    'shares', 'currency', 'exchange'
]})

print("\n=== income statement (for EPS) ===")
try:
    inc = stock.get_income_stmt(pretty=True)
    print(inc.head(3).to_string())
except Exception as e:
    print("Failed:", e)

print("\n=== balance sheet (for book value, debt) ===")
try:
    bs = stock.balance_sheet
    print(bs.head(10).to_string())
except Exception as e:
    print("Failed:", e)

print("\n=== cashflow ===")
try:
    cf = stock.cashflow
    print(cf.head(5).to_string())
except Exception as e:
    print("Failed:", e)

print("\n=== get_info() — newer method ===")
try:
    info = stock.get_info()
    # Print only the keys that exist
    keys = ['trailingPE','forwardPE','trailingEps','bookValue',
            'dividendYield','returnOnEquity','debtToEquity',
            'marketCap','fiftyTwoWeekHigh','fiftyTwoWeekLow']
    print({k: info.get(k) for k in keys})
except Exception as e:
    print("Failed:", e)