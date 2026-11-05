# 📈 AI Stock Advisor & Quantitative Screener

A comprehensive, production-grade interactive web application for Indian Equity Market analysis (NSE), built with **Gradio**, **yfinance**, **Plotly**, and **Google Gemini AI**.

Transformed and upgraded from the original Google Colab notebook (`Copy_of_Stock_Advisor.ipynb`) into a maintainable, professional, and deployable financial intelligence platform.

---

## 🌟 Key Features

1. **Market Screener & Quantitative Technical Scanner**:
   - Analyzes large equity universes (NSE Main Equities `EQUITY_L.csv`, SME Equities `SME_EQUITY_L.csv`, T+0 Eligible `Eligible_T0_Securities.xlsx`, or custom uploaded CSV/Excel files).
   - Fully preserves the original quantitative scoring model:
     - **SMA50 & SMA200** Trend Alignment
     - **Wilder's RSI 14** Momentum Oscillator (with 40–65 sweet-spot detection)
     - **20-Session Return Velocity**
     - Exact scoring rules (+2, -2, +1, -1) and signals (**BUY WATCH**, **HOLD / WAIT**, **SELL WATCH**).
   - Interactive, real-time filtering by Signal, Minimum Score, Symbol search, and RSI range.
   - 1-click export of scan results to timestamped **CSV** and **Excel** files.

2. **Single Stock Deep-Dive & Interactive 3-Panel Charts**:
   - Real-time/on-demand data lookup for any NSE ticker (e.g. `RELIANCE`, `TCS`, `INFY`, `63MOONS`, `SEJALLTD`).
   - Dynamic KPI ribbon showing Price, 20D Return %, RSI 14, SMA50, SMA200, Score, and Signal.
   - Interactive Plotly chart with 3 synchronized panels:
     - **Panel 1**: Price (Candlestick or Line) with 50-day and 200-day Simple Moving Averages.
     - **Panel 2**: Color-coded Trading Volume bars.
     - **Panel 3**: RSI 14 with Overbought (70), Oversold (30), and Moderate Range (40–65) reference lines.

3. **AI Stock Advisor & Research Reports**:
   - Integrated with **Google Gemini AI** (`gemini-3.5-flash-lite` / `gemini-3-flash-preview`).
   - Live web search and financial news sentiment via **Tavily Search API**.
   - Global quotes and profile lookups via **Finnhub** and **TwelveData**.
   - Generates structured research reports covering Executive Verdict, Technical Posture, News Catalysts, Tactical Entry/Target/Stop-Loss levels, and Risk Warnings.
   - Automatic deterministic fallback report if external AI endpoints are unreachable.

4. **SQLite Local Storage & Cache Explorer**:
   - Persistent SQLite database caching daily price records and download logs.
   - Allows incremental and resumable downloads without refetching existing symbols.
   - Live database statistics: row counts, date spans, success/failure logs, and file size on disk.

5. **Settings & Dynamic API Diagnostics**:
   - Real-time configuration of API credentials (`GEMINI_API_KEY`, `TAVILY_API_KEY`, `FINNHUB_API_KEY`, `TWELVEDATA_API_KEY`).
   - 1-click live API connectivity tester verifying all 4 external services.

---

## 🏗️ Project Architecture

```
AI_StockAdvisor/
├── app.py                      # Main Gradio application entry point
├── backend/
│   ├── __init__.py
│   ├── config.py               # Paths, environment configuration, API keys
│   ├── data_loader.py          # Stock universe parsing (CSV & Excel) and symbol cleansing
│   ├── market_data.py          # yfinance data fetcher & SQLite caching engine
│   ├── technical_analysis.py   # Exact mathematical indicators, scoring & filtering
│   ├── charts.py               # Interactive Plotly multi-panel financial charts
│   ├── ai_advisor.py           # Gemini, Tavily, Finnhub, and TwelveData integration
│   └── export_utils.py         # CSV & Excel timestamped export utilities
├── data/
│   ├── EQUITY_L.csv            # NSE Main Board equity securities list
│   ├── SME_EQUITY_L.csv        # NSE SME securities list
│   ├── Eligible_T0_Securities_20260930121437.xlsx  # T+0 Eligible securities list
│   └── indian_stock_market.sqlite                 # Cached price data and logs
├── assets/
│   └── custom.css              # Financial terminal UI styling and dark theme
├── tests/
│   ├── test_backend.py         # Automated unit test suite
│   └── test_api_keys.py        # Live endpoint validation script
├── .env                        # Local API credentials (git-ignored)
├── .env.example                # Template for environment variables
├── requirements.txt            # Production dependencies
└── README.md                   # Project documentation & deployment guide
```

---

## 📐 Mathematical Model & Scoring Strategy

The quantitative engine strictly preserves the algorithm from the original Colab notebook:

### 1. Indicators
- **Base Price ($P_t$)**: Adjusted Close (if available) else Close.
- **$\text{SMA}_{50}$**: 50-session rolling arithmetic mean:
  $$\text{SMA}_{50} = \frac{1}{50} \sum_{i=0}^{49} P_{t-i}$$
- **$\text{SMA}_{200}$**: 200-session rolling arithmetic mean:
  $$\text{SMA}_{200} = \frac{1}{200} \sum_{i=0}^{199} P_{t-i}$$
- **Wilder's Relative Strength Index ($\text{RSI}_{14}$)**:
  Exponential moving average with smoothing factor $\alpha = \frac{1}{14}$ on positive price deltas ($\text{AG}$) and negative price deltas ($\text{AL}$):
  $$\text{RS} = \frac{\text{AG}}{\text{AL}}, \quad \text{RSI}_{14} = 100 - \frac{100}{1 + \text{RS}}$$
- **20-Day Velocity**:
  $$\text{Return20D\_pct} = \left(\frac{P_t - P_{t-20}}{P_{t-20}}\right) \times 100$$

### 2. Scoring System
| Condition | Score Impact | Tag Added |
| :--- | :---: | :--- |
| $P_t > \text{SMA}_{50} > \text{SMA}_{200}$ | **+2** | `price > SMA50 > SMA200` (Reason) |
| $P_t < \text{SMA}_{50} < \text{SMA}_{200}$ | **-2** | `price < SMA50 < SMA200` (Risk) |
| $\text{SMA}_{50} > \text{SMA}_{200}$ (Partial) | **+1** | `SMA50 > SMA200` (Reason) |
| $\text{SMA}_{50} < \text{SMA}_{200}$ (Partial) | **-1** | `SMA50 < SMA200` (Risk) |
| Insufficient 200-Day History | **0** | `insufficient 200-day history` (Risk) |
| $40 \le \text{RSI}_{14} \le 65$ (Sweet Spot) | **+1** | `moderate RSI` (Reason) |
| $\text{RSI}_{14} > 70$ (Overbought) | **-1** | `RSI above 70` (Risk) |
| $\text{RSI}_{14} < 30$ (Oversold) | **0** | `RSI below 30` (Risk) |
| $\text{Return20D\_pct} > 0$ | **+1** | `positive 20-session return` (Reason) |
| $\text{Return20D\_pct} \le 0$ | **-1** | `negative 20-session return` (Risk) |

### 3. Final Decision
- **Score $\ge 3$** $\rightarrow$ **BUY WATCH** 🟢
- **Score $\le -2$** $\rightarrow$ **SELL WATCH** 🔴
- **$-1 \le \text{Score} \le 2$** $\rightarrow$ **HOLD / WAIT** 🟡

---

## 🚀 Quickstart & Local Setup

### Prerequisites
- Python 3.10+ (tested and verified on Python 3.11)
- Git

### 1. Clone & Navigate
```bash
git clone <repository_url>
cd AI_StockAdvisor
```

### 2. Create Virtual Environment
```bash
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and enter your keys:
```bash
cp .env.example .env
```
Edit `.env`:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
FINNHUB_API_KEY=your_finnhub_api_key_here
TWELVEDATA_API_KEY=your_twelvedata_api_key_here
DEFAULT_START_DATE=2015-01-01
SQLITE_DB_PATH=data/indian_stock_market.sqlite
```

### 5. Run the Application
```bash
python app.py
```
Open your browser at `http://127.0.0.1:7860`.

---

## 🚀 Render Deployment Guide

Deploy this application directly on [Render](https://render.com) using the included `render.yaml` Blueprint or via the web dashboard.

### Option A: Blueprint Deployment (Recommended)
1. Push your code to your GitHub account: `https://github.com/deepakkonakalla0510-web/AI_StockAdvisor`.
2. Log in to [Render](https://dashboard.render.com).
3. Click **New +** $\rightarrow$ **Blueprint**.
4. Connect your GitHub repository `deepakkonakalla0510-web/AI_StockAdvisor`.
5. Render detects `render.yaml` automatically.
6. Under **Environment Variables**, fill in your secret keys:
   - `GEMINI_API_KEY`
   - `TAVILY_API_KEY`
   - `FINNHUB_API_KEY`
   - `TWELVEDATA_API_KEY`
7. Click **Apply**. Render will automatically build and deploy your app.

### Option B: Manual Web Service Deployment
1. In Render Dashboard, click **New +** $\rightarrow$ **Web Service**.
2. Select your repository `deepakkonakalla0510-web/AI_StockAdvisor`.
3. Configure the service:
   - **Name**: `ai-stock-advisor`
   - **Language**: `Python 3`
   - **Region**: Any (e.g. `Oregon (US West)` or `Singapore`)
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
   - **Plan**: `Free`
4. Expand **Advanced** $\rightarrow$ **Add Environment Variable**:
   - `PYTHON_VERSION`: `3.11.8`
   - `GRADIO_SERVER_NAME`: `0.0.0.0`
   - `GEMINI_API_KEY`: *(Your Gemini API Key)*
   - `TAVILY_API_KEY`: *(Your Tavily API Key)*
   - `FINNHUB_API_KEY`: *(Your Finnhub API Key)*
   - `TWELVEDATA_API_KEY`: *(Your TwelveData API Key)*
5. Click **Create Web Service**. Render binds to the dynamic `$PORT` automatically and provides a live HTTPS URL (e.g. `https://ai-stock-advisor.onrender.com`).

---

## 🐙 GitHub Push Instructions

To push this project to your GitHub account (`deepakkonakalla0510-web`):

1. **Create a new GitHub Repository**:
   - Go to [github.com/new](https://github.com/new).
   - Repository Name: `AI_StockAdvisor`
   - Visibility: **Public** or **Private**
   - Leave "Add a README file", ".gitignore template", and "license" unchecked.

2. **Initialize Git and Push**:
   ```bash
   git init
   git add .
   git commit -m "feat: complete AI Stock Advisor web application with TradingView charts & Render configuration"
   git branch -M main
   git remote add origin https://github.com/deepakkonakalla0510-web/AI_StockAdvisor.git
   git push -u origin main
   ```

---

## 🌐 Hugging Face Spaces Deployment Guide

Deploying this app to **Hugging Face Spaces** takes less than 2 minutes:

1. **Create Space**:
   - Visit [Hugging Face Spaces](https://huggingface.co/new-space).
   - Enter a name (e.g. `ai-stock-advisor`).
   - Select **Gradio** as the Space SDK.
   - Choose **Public** or **Private** visibility.

2. **Upload / Push Project Files**:
   - Push repository files (`app.py`, `backend/`, `data/`, `assets/`, `requirements.txt`, `README.md`).
   - *Do not push `.env` or `.venv`.*

3. **Configure Space Secrets**:
   In your Space: go to **Settings** $\rightarrow$ **Variables and secrets** $\rightarrow$ **New secret**:
   - `GEMINI_API_KEY`: Your Google Gemini API Key
   - `TAVILY_API_KEY`: Your Tavily Search Key
   - `FINNHUB_API_KEY`: Your Finnhub API Key
   - `TWELVEDATA_API_KEY`: Your TwelveData API Key

4. **Automatic Build & Launch**:
   - Hugging Face automatically installs `requirements.txt` and executes `python app.py`.
   - Your web app is live with a permanent public URL!

---

## 📋 Modifications from the Original Colab Notebook

| # | Colab Notebook Component | Web Application Implementation | Reason for Modification |
| :---: | :--- | :--- | :--- |
| **1** | `%pip -q install ...` in notebook cell | `requirements.txt` & isolated virtual environment | Standard Python deployment requirement outside notebook environment. |
| **2** | `google.colab.files.upload()` | `gr.File()` component & automatic detection of built-in CSV/Excel files | Colab's file upload API only works inside Google Colab browser sessions. |
| **3** | `google.colab.drive.mount('/content/drive')` | Persistent local SQLite database (`data/indian_stock_market.sqlite`) | Eliminates dependency on Google Drive authorization; works universally. |
| **4** | Hardcoded path `/content/` | Relative configurable paths (`data/`, `backend/config.py`) | Ensures cross-platform compatibility (Windows, Linux, macOS, cloud containers). |
| **5** | `google.colab.sheets.InteractiveSheet()` | Interactive sortable Gradio DataFrame + CSV/Excel download buttons | `google.colab.sheets` is a proprietary Colab widget unavailable elsewhere. |
| **6** | Static table displays (`display(df.head())`) | Interactive Gradio UI with real-time filters (RSI, Score, Decision, Symbol search) | Enables responsive user interaction without re-executing code cells. |
| **7** | Terminal loop printouts | Generator-based live progress bars and status message streaming | Provides clean visual UX without cluttering logs. |
| **8** | Single notebook script | Clean modular architecture (`backend/` package, `app.py`, `tests/`) | Enhances maintainability, testability, and separation of concerns. |
| **9** | Pure technical calculation | Integrated AI Research Report (Gemini + Tavily + Finnhub + TwelveData) | Elevates raw numeric indicator output into actionable, professional investment intelligence. |

---

## 🧪 Testing and Verification Results

The project includes an automated test suite (`tests/test_backend.py`) verifying:
- ✅ **Universe Loading**: Successfully parses and validates 2,605 symbols from `EQUITY_L.csv`.
- ✅ **Indicator Accuracy**: Confirmed mathematical calculation of Wilder's RSI 14, 50-day SMA, 200-day SMA, and 20-day return.
- ✅ **Scoring Model**: Validated exact score assignments (+2, -2, +1, -1) and decision categorization.
- ✅ **Interactive Charts**: Verified 3-panel Plotly layout (Candlestick, Volume, RSI with threshold bands).
- ✅ **API Connectivity**: Validated live responses for Gemini (`gemini-3.5-flash-lite`), Tavily, Finnhub, and TwelveData.
- ✅ **Server Health**: Verified Gradio HTTP server endpoint launches and returns HTTP 200.

---

## ⚠️ Notes & Disclaimer

- **Market Data**: Stock prices are retrieved via `yfinance` for National Stock Exchange of India (NSE). Intraday quotes may be delayed per exchange terms.
- **Financial Disclaimer**: This application is built for research, educational, and quantitative exploration purposes only. It is **not** financial advice or SEBI-registered advisory. Always conduct independent due diligence before making investment decisions.

