import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai_tools import SerperDevTool
from tools import stock_price_analyzer
from pydantic import BaseModel, Field
from typing import List

class FinancialAnalysisOutput(BaseModel):
    ticker: str = Field(description="The stock ticker symbol analyzed")
    technical_signal: str = Field(description="Overall technical trend: 'Bullish', 'Bearish', or 'Neutral'")
    sentiment_score: float = Field(description="Market sentiment score from 1.0 (Extreme Fear/Bearish) to 10.0 (Extreme Greed/Bullish)")
    key_catalysts: List[str] = Field(description="Exactly 3 bullet points highlighting upcoming events, positive news, or fundamental strengths driving the stock.")
    risk_summary: List[str] = Field(description="Exactly 3 bullet points highlighting critical risks, bearish technicals, or fundamental weaknesses.")

load_dotenv()

def run_financial_analysis(ticker: str):
    # 1. Tools & LLM Setup
    search_tool = SerperDevTool()
    my_llm = LLM(model="openai/gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"), temperature=0)

    # 2. Define Agents
    quant_analyst = Agent(
        role='Senior Quant Researcher',
        goal=f'Report technical indicators for {ticker}',
        backstory="You are a precise technical analyst at a Mumbai firm.",
        tools=[stock_price_analyzer],
        llm=my_llm,
        verbose=True,
        allow_delegation=False
    )

    news_analyst = Agent(
        role='Financial News Correspondent',
        goal=f'Identify major news catalysts for {ticker}',
        backstory="""You are an expert financial journalist in India. 
        You scan news from Moneycontrol, Economic Times, and Livemint to find sentiment. 
        You look for earnings, scandals and regulatory news.""",
        tools=[search_tool],
        llm=my_llm,
        verbose=True
    )

    risk_manager = Agent(
        role='Chief Risk Officer (CRO)',
        goal=f'Identify all potential risks and downsides for {ticker}',
        backstory="""You are a cynical, veteran risk manager at a top Indian bank. 
        You believe every investment has a hidden trap. Your job is to find 
        3 specific reasons why the Quant and News agents might be over-optimistic. 
        Look for regulatory risks, promoter issues, or macro-economic threats.""",
        llm=my_llm,
        verbose=True,
        allow_delegation=False
    )

    # 3. Define Tasks
    tech_task = Task(description=f'Fetch Technicals for {ticker}.',
                     expected_output='Price, RSI, and MA20.',
                     agent=quant_analyst
                    )
    
    news_task = Task(description=f'Search news for {ticker} from the last 7 days.',
                     expected_output='3-bullet summary + sentiment score.',
                     agent=news_analyst,
                     context=[tech_task]
                    )
    
    risk_task = Task(
                    description="""Analyze risks for {ticker} based on tech and news. 
                    Provide a sentiment_score, strictly between 0 and 10 (where 0 is extreme panic and 10 is euphoria).
                    Ensure all fields in the JSON are filled accurately.""", 
                    expected_output='A structured JSON object with analysis and risk summary.', 
                    agent=risk_manager, 
                    context=[tech_task, news_task],
                    output_json=FinancialAnalysisOutput
                    )

    # 4. Assemble & Execute
    financial_crew = Crew(
        agents=[quant_analyst, news_analyst, risk_manager],
        tasks=[tech_task, news_task, risk_task],
        verbose=True
    )

    return financial_crew.kickoff(inputs={'ticker': ticker})