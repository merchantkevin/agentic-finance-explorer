import os
import json
from openai import OpenAI

# We reuse the same OpenAI client that CrewAI uses
# No new API keys needed
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ─────────────────────────────────────────────
# EVALUATOR 1: Rule-Based Consistency Check
# ─────────────────────────────────────────────
def eval_signal_consistency(analysis_data: dict) -> dict:
    """
    Checks if technical_signal and sentiment_score agree with each other.
    This is pure logic — no LLM, no API call, no cost, instant.

    Returns a dict with:
    - score: 1.0 (consistent) or 0.0 (contradictory)
    - reason: human-readable explanation
    """
    signal = str(analysis_data.get("technical_signal", "")).strip().title()
    try:
        score = float(analysis_data.get("sentiment_score", 5.0))
    except (ValueError, TypeError):
        score = 5.0

    # Define expected score ranges for each signal
    rules = {
        "Bullish":  score > 5.5,
        "Bearish":  score < 4.5,
        "Neutral":  3.5 <= score <= 6.5,
    }

    is_consistent = rules.get(signal, True)  # unknown signal = no penalty

    if is_consistent:
        reason = f"{signal} signal with score {score} — consistent."
    else:
        reason = (
            f"CONTRADICTION: {signal} signal but sentiment_score is {score}. "
            f"A {signal} call should have a "
            f"{'score > 5.5' if signal == 'Bullish' else 'score < 4.5' if signal == 'Bearish' else 'score between 3.5 and 6.5'}."
        )

    return {
        "score": 1.0 if is_consistent else 0.0,
        "reason": reason
    }


# ─────────────────────────────────────────────
# EVALUATOR 2: LLM-as-Judge Quality Scores
# ─────────────────────────────────────────────
def eval_with_llm_judge(analysis_data: dict, ticker: str) -> dict:
    """
    Sends the analysis output to GPT-4o-mini with a rubric.
    Asks it to score 3 dimensions and return JSON.

    Returns a dict with scores for:
    - risk_specificity (1–5)
    - catalyst_specificity (1–5)
    - overall_quality (1–10)
    - reasoning: one sentence explaining the scores
    """

    # Format the analysis cleanly for the judge
    risk_bullets   = "\n".join(f"  - {r}" for r in analysis_data.get("risk_summary", []))
    catalyst_bullets = "\n".join(f"  - {c}" for c in analysis_data.get("key_catalysts", []))

    prompt = f"""You are a strict financial analysis quality reviewer.

You are evaluating an AI-generated stock analysis report for {ticker}.

Here is the report output:

TECHNICAL SIGNAL: {analysis_data.get("technical_signal")}
SENTIMENT SCORE: {analysis_data.get("sentiment_score")} / 10

KEY CATALYSTS (should be specific to {ticker}):
{catalyst_bullets}

RISK SUMMARY (should be specific to {ticker}):
{risk_bullets}

---
Score this report on the following 3 dimensions.
Be strict. Generic statements that could apply to ANY stock should score 1–2.

DIMENSION 1 — risk_specificity (integer 1–5):
  5 = All 3 risks are specific to {ticker} (e.g. mentions actual company events, promoter issues, sector-specific threats)
  3 = Mix of specific and generic risks
  1 = All 3 risks are generic boilerplate (e.g. "market volatility", "macroeconomic uncertainty")

DIMENSION 2 — catalyst_specificity (integer 1–5):
  5 = All 3 catalysts are specific and concrete (e.g. mentions actual upcoming events, earnings, product launches)
  3 = Mix of specific and vague catalysts
  1 = All 3 catalysts are vague or generic

DIMENSION 3 — overall_quality (integer 1–10):
  10 = Excellent, actionable, specific report
  5  = Average, some useful content
  1  = Useless, entirely generic

Return ONLY a valid JSON object. No explanation outside the JSON. No markdown.
Example format:
{{"risk_specificity": 4, "catalyst_specificity": 3, "overall_quality": 7, "reasoning": "One sentence here."}}
"""

    try:
        print(f"🤖 Sending to LLM judge for {ticker}...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,       # deterministic scoring
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if the model adds them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        scores = json.loads(raw)

        return {
            "risk_specificity":    float(scores.get("risk_specificity", 3)),
            "catalyst_specificity": float(scores.get("catalyst_specificity", 3)),
            "overall_quality":     float(scores.get("overall_quality", 5)),
            "reasoning":           str(scores.get("reasoning", ""))
        }

    except Exception as e:
        print(f"⚠️ LLM judge failed for {ticker}: {e}")
        print(f"⚠️ Full error: {type(e).__name__}: {e}")
        # Return neutral scores on failure — don't crash the analysis
        return {
            "risk_specificity":    3.0,
            "catalyst_specificity": 3.0,
            "overall_quality":     5.0,
            "reasoning":           f"Eval failed: {str(e)}"
        }


# ─────────────────────────────────────────────
# MAIN ENTRY POINT — called from app.py
# ─────────────────────────────────────────────
def run_eval(analysis_data: dict, ticker: str) -> dict:
    """
    Runs all evaluators and returns a single combined scores dict.
    This is the only function app.py needs to call.
    """
    print(f"🔍 Running eval for {ticker}...")

    consistency   = eval_signal_consistency(analysis_data)
    llm_scores    = eval_with_llm_judge(analysis_data, ticker)

    results = {
        "signal_consistency":    consistency["score"],
        "consistency_reason":    consistency["reason"],
        "risk_specificity":      llm_scores["risk_specificity"],
        "catalyst_specificity":  llm_scores["catalyst_specificity"],
        "overall_quality":       llm_scores["overall_quality"],
        "reasoning":             llm_scores["reasoning"],
    }

    print(f"✅ Eval complete for {ticker}: overall_quality={results['overall_quality']}/10")
    return results