import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_tavily():
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("Tavily: No key found")
        return False
    try:
        url = "https://api.tavily.com/search"
        payload = {"api_key": api_key, "query": "Reliance Industries NSE latest stock news", "max_results": 2}
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Tavily API: SUCCESS (found {len(data.get('results', []))} results)")
            return True
        else:
            print(f"Tavily API: Failed with status {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"Tavily API Error: {e}")
        return False

def test_finnhub():
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        print("Finnhub: No key found")
        return False
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={api_key}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Finnhub API: SUCCESS (current price: {data.get('c')})")
            return True
        else:
            print(f"Finnhub API: Failed with status {resp.status_code}")
            return False
    except Exception as e:
        print(f"Finnhub API Error: {e}")
        return False

def test_twelvedata():
    api_key = os.getenv("TWELVEDATA_API_KEY")
    if not api_key:
        print("TwelveData: No key found")
        return False
    try:
        url = f"https://api.twelvedata.com/price?symbol=AAPL&apikey={api_key}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"TwelveData API: SUCCESS (price: {data.get('price')})")
            return True
        else:
            print(f"TwelveData API: Failed with status {resp.status_code}")
            return False
    except Exception as e:
        print(f"TwelveData API Error: {e}")
        return False

def test_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Gemini: No key found")
        return False
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": "Say 'Stock Advisor AI is active' in 5 words or less."}]}]}
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            print(f"Gemini API: SUCCESS -> {text}")
            return True
        else:
            print(f"Gemini API Failed: {resp.status_code} {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return False

if __name__ == "__main__":
    print("Testing external API keys...")
    test_tavily()
    test_finnhub()
    test_twelvedata()
    test_gemini()
