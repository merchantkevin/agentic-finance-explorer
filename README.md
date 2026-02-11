# 🏛️ Multi-Agent Financial Intelligence Committee (NSE)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![CrewAI](https://img.shields.io/badge/Framework-CrewAI-ff69b4?style=flat)](https://www.crewai.com/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Cloud-Native](https://img.shields.io/badge/Cloud-Render%20%7C%20Streamlit-663399?style=flat)](https://render.com)

An autonomous investment committee that performs end-to-end technical and fundamental analysis of Indian stocks. By orchestrating a crew of specialized AI agents, the system bridges the gap between raw market data and actionable investment intelligence.

🔗 **[Live Dashboard](https://agentic-finance-explorer-zrkwkgnuyidyfgbqc8jb4a.streamlit.app/)** | 📖 **[API Documentation](https://agentic-finance-explorer.onrender.com/docs)**

---

## 🚀 The Architecture
The system follows a **Decoupled Agentic Pattern**, separating the reasoning engine from the presentation layer.

- **Reasoning Engine (Backend):** A FastAPI server hosting a CrewAI orchestration layer.
- **Frontend (UI):** A Streamlit dashboard optimized for executive decision-making.
- **Data Guardrails:** Pydantic-enforced schemas to ensure deterministic AI outputs.

## 🧠 The "Committee" (Agents)
The system simulates a high-level investment meeting through three distinct agents:

1.  **The Quant Analyst:** Interacts with `yfinance` and `pandas_ta` to extract RSI, MA20, and price action. It operates on **deterministic tools** rather than LLM guesswork.
2.  **The News Correspondent:** Uses the `Serper API` to scrape real-time sentiment from *Moneycontrol*, *The Economic Times*, and *LiveMint*.
3.  **Chief Risk Officer (Adversarial):** Audits the findings of the previous agents to identify "Red Flags" like promoter pledging, regulatory headwinds, or overvaluation.

## 🛠️ Tech Stack
| Layer | Technology |
| :--- | :--- |
| **Agent Framework** | CrewAI |
| **LLM** | GPT-4o-mini (OpenAI) |
| **Backend** | FastAPI (Python) |
| **Frontend** | Streamlit |
| **Data Handling** | Pydantic, Pandas, yfinance |
| **Cloud** | Render (API), Streamlit Cloud (UI) |

## 🌟 Key Engineering Features
- **Defensive Parsing:** Implemented a fallback mechanism to handle stochastic LLM string outputs when schema validation fails.
- **Async Background Tasks:** Uses FastAPI `BackgroundTasks` to manage long-running (45s+) agentic reasoning loops without blocking the user thread.
- **Persistent Caching:** Automated JSON-based caching to reduce API costs and latency for frequent ticker queries.
- **CORS Secure:** Configured Cross-Origin Resource Sharing for secure communication between frontend and backend domains.

---

## ⚙️ Local Setup

1. **Clone & Install** (using `uv` for lightning-fast speeds):
   ```bash
   git clone [https://github.com/merchantkevin/agentic-finance-explorer.git](https://github.com/merchantkevin/agentic-finance-explorer.git)
   cd agentic-finance-explorer
   uv sync