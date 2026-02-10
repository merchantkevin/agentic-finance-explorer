import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai_tools import SerperDevTool
from tools import stock_price_analyzer

load_dotenv()

def run_financial_analysis(ticker: str):
    # 1. Tools & LLM Setup
    search_tool = SerperDevTool()
    my_llm = LLM(model="openai/gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))

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
        You scan news from Moneycontrol, ET, and Mint to find sentiment. 
        You look for earnings, scandals, or regulatory news.""",
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
        allow delegation=False
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
    
    risk_task = Task(description=f'Critique reports for {ticker}. Find 3 threats.',
                     expected_output='Risk Disclosure + Confidence Score.',
                     agent=risk_manager,
                     context=[tech_task, news_task]
                    )

    # 4. Assemble & Execute
    financial_crew = Crew(
        agents=[quant_analyst, news_analyst, risk_manager],
        tasks=[tech_task, news_task, risk_task],
        verbose=True
    )

    return financial_crew.kickoff(inputs={'ticker': ticker})