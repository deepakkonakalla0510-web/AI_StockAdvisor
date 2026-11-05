import os
from typing import Dict, Any, List, Optional
import requests

from backend.config import (
    get_gemini_key,
    get_tavily_key,
    get_finnhub_key,
    get_twelvedata_key,
    GEMINI_MODELS
)

def search_stock_news_tavily(symbol: str, company_name: str = "", api_key: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Search for latest news and sentiment for a stock using Tavily Search API.
    """
    key = api_key or get_tavily_key()
    if not key:
        return []
        
    query_target = company_name if company_name else symbol
    query = f"{query_target} NSE India stock news earnings financial performance"
    
    try:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": key,
            "query": query,
            "search_depth": "basic",
            "max_results": 4,
            "include_domains": ["moneycontrol.com", "economictimes.indiatimes.com", "livemint.com", "reuters.com", "business-standard.com", "cnbctv18.com"]
        }
        resp = requests.post(url, json=payload, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            return [
                {
                    "title": item.get("title", ""),
                    "content": item.get("content", ""),
                    "url": item.get("url", "")
                }
                for item in data.get("results", [])
            ]
        # If domain-restricted search yielded 0 results, retry general search
        payload.pop("include_domains", None)
        resp2 = requests.post(url, json=payload, timeout=8)
        if resp2.status_code == 200:
            data2 = resp2.json()
            return [
                {
                    "title": item.get("title", ""),
                    "content": item.get("content", ""),
                    "url": item.get("url", "")
                }
                for item in data2.get("results", [])
            ]
    except Exception as e:
        print(f"Tavily search notice for {symbol}: {e}")
        
    return []

def fetch_finnhub_quote(symbol: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Fetch quote or market data from Finnhub."""
    key = api_key or get_finnhub_key()
    if not key:
        return {}
        
    try:
        # Check standard symbol
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={key}"
        resp = requests.get(url, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("c", 0) > 0:
                return data
    except Exception as e:
        print(f"Finnhub quote notice: {e}")
        
    return {}

def fetch_twelvedata_price(symbol: str, api_key: Optional[str] = None) -> Optional[float]:
    """Fetch real-time price from TwelveData API."""
    key = api_key or get_twelvedata_key()
    if not key:
        return None
        
    try:
        # Try Indian NSE ticker format
        url = f"https://api.twelvedata.com/price?symbol={symbol}&exchange=NSE&apikey={key}"
        resp = requests.get(url, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            if "price" in data:
                return float(data["price"])
    except Exception as e:
        print(f"TwelveData notice: {e}")
        
    return None

def generate_ai_stock_report(
    symbol: str,
    technical_data: Dict[str, Any],
    news_items: Optional[List[Dict[str, str]]] = None,
    gemini_key: Optional[str] = None,
    preferred_model: str = "gemini-3.5-flash-lite",
    focus_mode: str = "Full Strategic Investment Report"
) -> str:
    """
    Generate an AI research report combining technical setup,
    market news sentiment, and algorithmic decision using Google Gemini.
    """
    key = gemini_key or get_gemini_key()
    
    # Extract technical indicators
    close = technical_data.get("close", "N/A")
    rsi = technical_data.get("RSI14", "N/A")
    sma50 = technical_data.get("SMA50", "N/A")
    sma200 = technical_data.get("SMA200", "N/A")
    ret20 = technical_data.get("Return20D_pct", "N/A")
    score = technical_data.get("score", 0)
    decision = technical_data.get("decision", "HOLD / WAIT")
    reasons = technical_data.get("reasons", "None")
    risks = technical_data.get("risks", "None")
    
    # Format news items
    news_context = ""
    if news_items and len(news_items) > 0:
        news_context = "### Recent Real-Time News & Market Headlines:\n"
        for i, item in enumerate(news_items, 1):
            news_context += f"{i}. **{item.get('title')}**\n   _{item.get('content')}_\n\n"
    else:
        news_context = "No recent company-specific news headlines retrieved. Analysis based primarily on price action and technical momentum.\n"

    # Build prompt with focus
    prompt = f"""
You are an expert Chief Quantitative Analyst and SEBI-registered Investment Strategist.
Perform an in-depth stock analysis and tactical advisory for the Indian stock: **{symbol}** (National Stock Exchange).
Special Focus: **{focus_mode}**

Here are the verified quantitative metrics and algorithmic findings from our automated scanner:
- **Symbol**: {symbol}
- **Current Close Price**: INR {close}
- **50-Day Moving Average (SMA50)**: INR {sma50}
- **200-Day Moving Average (SMA200)**: INR {sma200}
- **Relative Strength Index (RSI 14, Wilder's Formula)**: {rsi}
- **20-Trading-Session Percentage Return**: {ret20}%
- **Quantitative Model Score**: {score} (Range: -5 to +5)
- **Model Decision**: {decision}
- **Identified Bullish Drivers (Reasons)**: {reasons}
- **Identified Risk Factors**: {risks}

{news_context}

Provide a well-structured, professional investment brief in clear Markdown with the following sections, tailored specifically for **{focus_mode}**:
1. **Executive Verdict & Summary**: Direct assessment of the stock and whether the {decision} is warranted.
2. **Technical Architecture Analysis**:
   - Trend health: Price vs SMA50 vs SMA200 (Golden Cross / Death Cross / Alignment)
   - Momentum posture: RSI 14 condition (Overbought >70, Oversold <30, or Healthy Expansion 40-65)
   - 20-Day Velocity: Interpretation of {ret20}% recent gain/loss
3. **News & Market Sentiment**: Synthesis of the latest events and their prospective catalyst impact.
4. **Actionable Trade Setup**:
   - Suggested Entry Zone
   - Immediate Resistance & Upside Targets (INR)
   - Key Support Level & Strict Invalidation / Stop-Loss Level (INR)
   - Risk-to-Reward Ratio Assessment
5. **Key Caveats & Risk Warning**: Specific warnings for retail traders.
6. **Statutory Disclaimer**: Standard market risk reminder.

Be concise, analytical, objective, and realistic. Avoid generic disclaimers in the main body.
"""

    if not key:
        return generate_algorithmic_fallback_report(symbol, technical_data, news_items, "No Gemini API Key provided. Set GEMINI_API_KEY in the Settings tab to enable full AI generative analysis.")

    # Call Gemini REST endpoint
    models_to_try = [preferred_model] + [m for m in GEMINI_MODELS if m != preferred_model]
    
    for model_name in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 2048
                }
            }
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                result_json = resp.json()
                candidates = result_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
            else:
                print(f"Gemini model {model_name} returned HTTP {resp.status_code}: {resp.text[:150]}")
        except Exception as e:
            print(f"Gemini call error with {model_name}: {e}")

    # If all remote AI calls fail, provide algorithmic fallback report
    return generate_algorithmic_fallback_report(
        symbol, technical_data, news_items,
        "Gemini API request encountered a network or quota limitation. Displaying quantitative algorithmic analysis."
    )

def generate_algorithmic_fallback_report(
    symbol: str,
    tech: Dict[str, Any],
    news_items: Optional[List[Dict[str, str]]],
    notice: str = ""
) -> str:
    """
    Fallback deterministic report when LLM API is unavailable.
    Ensures the user ALWAYS gets a complete, actionable technical analysis.
    """
    close = tech.get("close", "N/A")
    sma50 = tech.get("SMA50", "N/A")
    sma200 = tech.get("SMA200", "N/A")
    rsi = tech.get("RSI14", "N/A")
    ret20 = tech.get("Return20D_pct", "N/A")
    score = tech.get("score", 0)
    decision = tech.get("decision", "HOLD / WAIT")
    reasons = tech.get("reasons", "None")
    risks = tech.get("risks", "None")

    badge = "🟢" if decision == "BUY WATCH" else ("🔴" if decision == "SELL WATCH" else "🟡")

    report = f"""
# {badge} Tactical Stock Advisory: {symbol}

> [!NOTE]
> {notice}

---

### 1. Executive Verdict
- **Model Recommendation**: **{decision}**
- **Composite Score**: **{score} / 4**
- **Current Market Price**: **₹{close}**

### 2. Quantitative Technical Breakdown
- **Trend Alignment**:
  - **50-Day Simple Moving Average (SMA50)**: ₹{sma50}
  - **200-Day Simple Moving Average (SMA200)**: ₹{sma200}
  - *Evaluation*: {"Bullish golden alignment (Price > SMA50 > SMA200)" if "price > SMA50 > SMA200" in reasons else "Bearish alignment or neutral consolidation."}
- **Momentum Oscillator (RSI 14)**: **{rsi}**
  - *Interpretation*: {"Healthy momentum within sweet spot zone (40 - 65)" if (isinstance(rsi, (int, float)) and 40 <= rsi <= 65) else ("Overbought warning (>70)" if (isinstance(rsi, (int, float)) and rsi > 70) else "Oversold condition (<30)")}
- **20-Day Velocity**: **{ret20}%** return over the past 20 trading sessions.

### 3. Bullish Drivers & Risk Factors
- **Identified Bullish Drivers**: `{reasons if reasons else 'No primary bullish catalysts detected.'}`
- **Identified Risk Factors**: `{risks if risks else 'No immediate technical warning flags.'}`

### 4. Tactical Support & Resistance Levels
- **Immediate Support**: ₹{round(float(sma50) * 0.97, 2) if isinstance(sma50, (int, float)) else 'N/A'} (approx. -3% from SMA50)
- **Stop-Loss / Invalidation**: ₹{round(float(sma200) * 0.98, 2) if isinstance(sma200, (int, float)) else 'N/A'} (below SMA200)
- **Target Zone**: ₹{round(float(close) * 1.08, 2) if isinstance(close, (int, float)) else 'N/A'} (+8% initial resistance)
"""

    if news_items:
        report += "\n### 5. Recent News Headlines\n"
        for item in news_items[:3]:
            report += f"- [{item.get('title')}]({item.get('url', '#')}): {item.get('content', '')[:120]}...\n"

    report += """
---
*Disclaimer: This analysis is algorithmically generated for educational and informational purposes only. It does not constitute investment advice.*
"""
    return report

