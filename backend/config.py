import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_PATH = str(DATA_DIR / "indian_stock_market.sqlite")
SCAN_RESULTS_PATH = str(DATA_DIR / "indian_stock_scan_results.csv")

# Built-in Universe Files
BUILTIN_UNIVERSES = {
    "NSE Main Equities (EQUITY_L.csv)": str(DATA_DIR / "EQUITY_L.csv"),
    "NSE SME Equities (SME_EQUITY_L.csv)": str(DATA_DIR / "SME_EQUITY_L.csv"),
    "NSE T+0 Eligible (Eligible_T0_Securities.xlsx)": str(DATA_DIR / "Eligible_T0_Securities_20260930121437.xlsx"),
}

# API Keys Configuration
def get_api_key(name: str, fallback_env: str = None) -> str:
    """Retrieve API key from environment variable with optional fallback."""
    val = os.getenv(name, "").strip()
    if not val and fallback_env:
        val = os.getenv(fallback_env, "").strip()
    return val

def get_gemini_key() -> str:
    # Notice: if both are set, prefer GEMINI_API_KEY to avoid OAuth key conflict
    return get_api_key("GEMINI_API_KEY", "GOOGLE_API_KEY")

def get_tavily_key() -> str:
    key = get_api_key("TAVILY_API_KEY")
    # Clean if accidentally duplicated
    if "tvly-dev-" in key and key.count("tvly-dev-") > 1:
        parts = [p for p in key.split("tvly-dev-") if p]
        if parts:
            key = "tvly-dev-" + parts[-1]
    return key

def get_finnhub_key() -> str:
    return get_api_key("FINNHUB_API_KEY")

def get_twelvedata_key() -> str:
    return get_api_key("TWELVEDATA_API_KEY")

# Default Parameters
DEFAULT_START_DATE = os.getenv("DEFAULT_START_DATE", "2015-01-01")
DEFAULT_PAUSE_SECONDS = 0.2
GEMINI_MODELS = ["gemini-3.5-flash-lite", "gemini-3-flash-preview"]

