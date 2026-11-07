import os
import sqlite3
from pathlib import Path
from typing import Optional, List, Tuple
import pandas as pd
import gradio as gr

from backend.config import (
    BUILTIN_UNIVERSES,
    DEFAULT_DB_PATH,
    DEFAULT_START_DATE,
    DEFAULT_PAUSE_SECONDS,
    SCAN_RESULTS_PATH,
    get_gemini_key,
    get_tavily_key,
    get_finnhub_key,
    get_twelvedata_key
)
from backend.data_loader import load_universe_file
from backend.market_data import (
    download_batch_generator,
    get_db_stats,
    get_stored_symbols_list,
    fetch_single_stock_on_demand,
    get_coverage_summary,
    get_connection
)
from backend.technical_analysis import (
    run_technical_scan_generator,
    filter_scan_results,
    analyze_group,
    calculate_indicators_full
)
from backend.charts import create_stock_analysis_figure, create_tradingview_area_chart
from backend.ai_advisor import (
    search_stock_news_tavily,
    fetch_finnhub_quote,
    fetch_twelvedata_price,
    generate_ai_stock_report
)
from backend.export_utils import export_dataframe_to_csv, export_dataframe_to_excel

# Load custom CSS
css_file = Path(__file__).parent / "assets" / "custom.css"
custom_css = ""
if css_file.exists():
    with open(css_file, "r", encoding="utf-8") as f:
        custom_css = f.read()

# Quick Pick Tickers
QUICK_TICKERS = ["63MOONS", "SEJALLTD", "BAJFINANCE", "TITAN", "ICICIBANK", "RELIANCE", "TCS", "INFY"]

# ---------------------------------------------------------
# Helper & Event Handlers
# ---------------------------------------------------------

def on_universe_select(choice: str, uploaded_file) -> Tuple[List[str], str, pd.DataFrame, str]:
    """Handles universe source selection (built-in or uploaded)."""
    if choice == "Custom Uploaded File" and uploaded_file is not None:
        file_path = uploaded_file.name if hasattr(uploaded_file, "name") else str(uploaded_file)
    elif choice in BUILTIN_UNIVERSES:
        file_path = BUILTIN_UNIVERSES[choice]
    else:
        file_path = BUILTIN_UNIVERSES["NSE Main Equities (EQUITY_L.csv)"]

    symbols, col, preview, msg = load_universe_file(file_path)
    preview_display = preview.head(5) if not preview.empty else pd.DataFrame()
    return symbols, msg, preview_display, f"Symbols Ready: {len(symbols):,}"

def on_upload_file(file_obj) -> Tuple[List[str], str, pd.DataFrame, str]:
    """Handles user uploaded CSV or Excel file."""
    if file_obj is None:
        return [], "No file uploaded.", pd.DataFrame(), "Symbols Ready: 0"
    file_path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
    symbols, col, preview, msg = load_universe_file(file_path)
    return symbols, msg, preview.head(5), f"Symbols Ready: {len(symbols):,}"

def start_download_task(symbols_state, start_date, max_stocks, skip_existing, pause_sec):
    """Executes the data download generator."""
    symbols = symbols_state or []
    if not symbols:
        symbols, _, _, _ = load_universe_file(BUILTIN_UNIVERSES["NSE Main Equities (EQUITY_L.csv)"])
        
    limit = int(max_stocks) if max_stocks and max_stocks > 0 else None
    for status_msg, progress_val, coverage_df in download_batch_generator(
        symbols=symbols,
        start_date=start_date,
        skip_existing=skip_existing,
        pause_seconds=pause_sec,
        max_stocks=limit,
        db_path=DEFAULT_DB_PATH
    ):
        yield status_msg, coverage_df

def start_technical_scan():
    """Runs technical scanner and computes summary counts."""
    latest_df = pd.DataFrame()
    for status_msg, pct, current_df in run_technical_scan_generator(
        db_path=DEFAULT_DB_PATH,
        save_to_csv=True
    ):
        latest_df = current_df
        yield status_msg, current_df, latest_df, "0", "0", "0", "0"

    # Compute metric counts
    if not latest_df.empty and "decision" in latest_df.columns:
        buy_cnt = str(len(latest_df[latest_df["decision"] == "BUY WATCH"]))
        hold_cnt = str(len(latest_df[latest_df["decision"] == "HOLD / WAIT"]))
        sell_cnt = str(len(latest_df[latest_df["decision"] == "SELL WATCH"]))
        total_cnt = str(len(latest_df))
    else:
        buy_cnt = hold_cnt = sell_cnt = total_cnt = "0"

    yield "Scan complete! Click any row in the table below to open instant Deep-Dive charts.", latest_df, latest_df, buy_cnt, hold_cnt, sell_cnt, total_cnt

def apply_table_filters(full_scan_state, decision_val, min_score_val, search_sym_val, min_rsi_val, max_rsi_val):
    """Filters results DataFrame instantly using state."""
    df = full_scan_state if full_scan_state is not None else pd.DataFrame()
    if df.empty and os.path.exists(SCAN_RESULTS_PATH):
        try:
            df = pd.read_csv(SCAN_RESULTS_PATH)
        except Exception:
            pass

    filtered = filter_scan_results(
        df=df,
        decision_filter=decision_val,
        min_score=int(min_score_val),
        search_symbol=search_sym_val,
        min_rsi=float(min_rsi_val),
        max_rsi=float(max_rsi_val)
    )
    return filtered

def analyze_single_stock(
    symbol_input: str,
    chart_type: str = "Candlestick",
    timeframe: str = "1Y",
    indicator_choices: Optional[List[str]] = None,
    tv_timeframe: str = "2015 - Present (MAX)"
):
    """Deep analysis for single stock: TradingView Area Chart, indicators, metrics, and multi-panel chart."""
    sym = (symbol_input or "").strip().upper()
    if not sym:
        sym = "63MOONS"

    indicators = indicator_choices if indicator_choices is not None else ["50-Day SMA", "200-Day SMA", "Volume", "RSI 14"]
    show_s50 = "50-Day SMA" in indicators
    show_s200 = "200-Day SMA" in indicators
    show_vol = "Volume" in indicators
    show_rsi = "RSI 14" in indicators

    df = fetch_single_stock_on_demand(sym, start_date="2015-01-01", db_path=DEFAULT_DB_PATH)
    if df.empty:
        empty_fig = create_stock_analysis_figure(pd.DataFrame(), sym)
        empty_tv_fig, empty_banner = create_tradingview_area_chart(pd.DataFrame(), sym)
        return (
            "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
            empty_banner, empty_tv_fig, empty_fig,
            f"⚠️ Could not retrieve price data for **{sym}**. Please verify the ticker symbol."
        )

    metrics = analyze_group(df)
    tv_fig, tv_banner = create_tradingview_area_chart(df, sym, timeframe=tv_timeframe)
    tech_fig = create_stock_analysis_figure(
        df,
        sym,
        chart_type=chart_type,
        timeframe=timeframe,
        show_sma50=show_s50,
        show_sma200=show_s200,
        show_volume=show_vol,
        show_rsi=show_rsi
    )

    if not metrics:
        return (
            "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
            tv_banner, tv_fig, tech_fig,
            f"ℹ️ Insufficient continuous trading sessions to compute full RSI 14 and SMA 200 for **{sym}**."
        )

    close_str = f"₹{metrics['close']:,.2f}"
    ret_str = f"{metrics['Return20D_pct']:+.2f}%" if metrics['Return20D_pct'] is not None else "N/A"
    rsi_str = f"{metrics['RSI14']:.2f}"
    sma50_str = f"₹{metrics['SMA50']:,.2f}" if metrics['SMA50'] else "N/A"
    sma200_str = f"₹{metrics['SMA200']:,.2f}" if metrics['SMA200'] else "N/A"
    score_str = f"{metrics['score']} / 4"
    decision_str = metrics['decision']

    badge_emoji = "🟢" if decision_str == "BUY WATCH" else ("🔴" if decision_str == "SELL WATCH" else "🟡")
    
    reasons_list = [f"• {r.strip()}" for r in metrics['reasons'].split(";") if r.strip()]
    risks_list = [f"• {r.strip()}" for r in metrics['risks'].split(";") if r.strip()]

    summary_md = f"""
### {badge_emoji} Technical Telemetry for **{sym}** (As of {metrics['date']})
- **Algorithmic Signal**: **`{decision_str}`** (Composite Score: **{metrics['score']}**)
- **Bullish Catalysts Detected**:
{chr(10).join(reasons_list) if reasons_list else '  *None detected.*'}
- **Technical Risk Factors**:
{chr(10).join(risks_list) if risks_list else '  *None detected.*'}
"""
    return close_str, ret_str, rsi_str, sma50_str, sma200_str, score_str, decision_str, tv_banner, tv_fig, tech_fig, summary_md

def on_tv_timeframe_change(symbol_input: str, tv_timeframe: str):
    """Refreshes TradingView area chart immediately when user toggles timeframe."""
    sym = (symbol_input or "").strip().upper() or "63MOONS"
    df = fetch_single_stock_on_demand(sym, start_date="2015-01-01", db_path=DEFAULT_DB_PATH)
    return create_tradingview_area_chart(df, sym, timeframe=tv_timeframe)

def on_tech_params_change(symbol_input: str, chart_type: str, timeframe: str, indicator_choices: List[str]):
    """Refreshes technical multi-panel chart when user changes format, timeframe or indicators."""
    sym = (symbol_input or "").strip().upper() or "63MOONS"
    df = fetch_single_stock_on_demand(sym, start_date="2015-01-01", db_path=DEFAULT_DB_PATH)
    indicators = indicator_choices if indicator_choices is not None else ["50-Day SMA", "200-Day SMA", "Volume", "RSI 14"]
    return create_stock_analysis_figure(
        df,
        sym,
        chart_type=chart_type,
        timeframe=timeframe,
        show_sma50="50-Day SMA" in indicators,
        show_sma200="200-Day SMA" in indicators,
        show_volume="Volume" in indicators,
        show_rsi="RSI 14" in indicators
    )

def run_ai_advisor(symbol_input: str, include_news: bool, preferred_model: str, focus_mode: str = "Full Strategic Investment Report"):
    """Coordinates Tavily search and Gemini report generation."""
    sym = (symbol_input or "").strip().upper()
    if not sym:
        return "Please enter or select a stock symbol to generate an AI Research Report.", ""

    df = fetch_single_stock_on_demand(sym, start_date="2020-01-01", db_path=DEFAULT_DB_PATH)
    if df.empty:
        return f"Error: No price history available for {sym}. Fetch data first.", ""

    tech_metrics = analyze_group(df)
    if not tech_metrics:
        tech_metrics = {
            "symbol": sym,
            "close": round(df["close"].iloc[-1], 2),
            "score": 0,
            "decision": "DATA INSUFFICIENT",
            "reasons": "",
            "risks": "Insufficient history"
        }

    # Fetch news if toggled
    news_items = []
    news_display = ""
    if include_news:
        news_items = search_stock_news_tavily(sym)
        if news_items:
            news_display = "#### 📰 Live Market News Headlines (via Tavily):\n"
            for n in news_items:
                news_display += f"- **[{n['title']}]({n['url']})**\n  _{n['content'][:140]}..._\n\n"
        else:
            news_display = "*No recent major news headlines found for this symbol via search.*"

    report_md = generate_ai_stock_report(
        symbol=sym,
        technical_data=tech_metrics,
        news_items=news_items,
        preferred_model=preferred_model,
        focus_mode=focus_mode
    )
    return report_md, news_display

def refresh_db_explorer():
    """Refreshes database coverage and failure tables."""
    stats = get_db_stats(DEFAULT_DB_PATH)
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        cov_df = pd.read_sql_query(
            "SELECT symbol, COUNT(*) AS daily_rows, MIN(date) AS first_date, MAX(date) AS last_date FROM daily_prices GROUP BY symbol ORDER BY daily_rows DESC LIMIT 50",
            conn
        )
        fail_df = pd.read_sql_query(
            "SELECT symbol, status, rows_downloaded, message, updated_at FROM download_log WHERE status='failed' ORDER BY updated_at DESC LIMIT 50",
            conn
        )
    finally:
        conn.close()

    stat_cards = f"""
| System Metric | Telemetry Value |
| :--- | :--- |
| **Total Stored Symbols** | **{stats['symbols_count']}** equities |
| **Total Daily Price Rows** | **{stats['total_rows']:,}** records |
| **Date Span Covered** | **{stats['min_date']}** to **{stats['max_date']}** |
| **Download Success Log** | **{stats['success_count']}** successful runs |
| **Download Error Log** | **{stats['failure_count']}** unlisted/restructured |
| **Database File Size** | **{stats['db_size_mb']} MB** on disk |
| **Active SQLite File** | `{stats['db_path']}` |
"""
    return stat_cards, cov_df, fail_df

def test_api_connections_action(gemini_k, tavily_k, finnhub_k, twelvedata_k):
    """Test all 4 external APIs and report connection status."""
    results = []
    
    # 1. Finnhub
    try:
        k = finnhub_k.strip() or get_finnhub_key()
        r = fetch_finnhub_quote("AAPL", api_key=k)
        if r and r.get("c"):
            results.append("✅ **Finnhub API**: Connected successfully (Live Quote Active).")
        else:
            results.append("❌ **Finnhub API**: Failed or invalid key.")
    except Exception as e:
        results.append(f"❌ **Finnhub API**: Error: {e}")

    # 2. TwelveData
    try:
        k = twelvedata_k.strip() or get_twelvedata_key()
        p = fetch_twelvedata_price("AAPL", api_key=k)
        if p:
            results.append(f"✅ **TwelveData API**: Connected successfully (Price Feed Active: ₹{p}).")
        else:
            results.append("❌ **TwelveData API**: Failed or invalid key.")
    except Exception as e:
        results.append(f"❌ **TwelveData API**: Error: {e}")

    # 3. Tavily
    try:
        k = tavily_k.strip() or get_tavily_key()
        items = search_stock_news_tavily("Reliance", api_key=k)
        if items:
            results.append(f"✅ **Tavily Search API**: Connected successfully (Found {len(items)} live news items).")
        else:
            results.append("❌ **Tavily Search API**: Failed or unauthorized key.")
    except Exception as e:
        results.append(f"❌ **Tavily Search API**: Error: {e}")

    # 4. Gemini
    try:
        k = gemini_k.strip() or get_gemini_key()
        import requests
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={k}"
        r = requests.post(url, json={"contents": [{"parts": [{"text": "ping"}]}]}, timeout=10)
        if r.status_code == 200:
            results.append("✅ **Google Gemini AI**: Connected successfully (Model: gemini-3.5-flash-lite).")
        else:
            # Check preview model
            url2 = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={k}"
            r2 = requests.post(url2, json={"contents": [{"parts": [{"text": "ping"}]}]}, timeout=10)
            if r2.status_code == 200:
                results.append("✅ **Google Gemini AI**: Connected successfully (Model: gemini-3-flash-preview).")
            else:
                results.append(f"❌ **Google Gemini AI**: HTTP {r.status_code} ({r.text[:100]}).")
    except Exception as e:
        results.append(f"❌ **Google Gemini AI**: Error: {e}")

    return "\n\n".join(results)

def save_settings_action(gemini_k, tavily_k, finnhub_k, twelvedata_k):
    """Save API keys into runtime environment and update .env."""
    if gemini_k:
        os.environ["GEMINI_API_KEY"] = gemini_k.strip()
        os.environ["GOOGLE_API_KEY"] = gemini_k.strip()
    if tavily_k:
        os.environ["TAVILY_API_KEY"] = tavily_k.strip()
    if finnhub_k:
        os.environ["FINNHUB_API_KEY"] = finnhub_k.strip()
    if twelvedata_k:
        os.environ["TWELVEDATA_API_KEY"] = twelvedata_k.strip()

    env_lines = [
        f"GEMINI_API_KEY={os.getenv('GEMINI_API_KEY', '')}",
        f"GOOGLE_API_KEY={os.getenv('GOOGLE_API_KEY', '')}",
        f"TAVILY_API_KEY={os.getenv('TAVILY_API_KEY', '')}",
        f"FINNHUB_API_KEY={os.getenv('FINNHUB_API_KEY', '')}",
        f"TWELVEDATA_API_KEY={os.getenv('TWELVEDATA_API_KEY', '')}",
        f"DEFAULT_START_DATE={DEFAULT_START_DATE}",
        f"SQLITE_DB_PATH={DEFAULT_DB_PATH}",
    ]
    try:
        with open(".env", "w", encoding="utf-8") as f:
            f.write("\n".join(env_lines) + "\n")
        return "✅ Settings saved successfully to environment and .env file!"
    except Exception as e:
        return f"Saved to current session, but note on writing .env: {e}"

# ---------------------------------------------------------
# Build Gradio UI
# ---------------------------------------------------------

theme = gr.themes.Soft(
    primary_hue="purple",
    secondary_hue="slate",
    neutral_hue="slate"
)

with gr.Blocks(title="AI Stock Advisor | Indian Equity Screener & Intelligence") as demo:

    # Global State
    symbols_state = gr.State(value=[])
    full_scan_state = gr.State(value=pd.DataFrame())

    # Header Banner
    with gr.Row(elem_classes=["header-banner"]):
        with gr.Column(scale=1):
            gr.HTML("""
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;">
                <div>
                    <h1 class="header-title">📈 AI Stock Advisor & Quantitative Screener</h1>
                    <p class="header-subtitle">
                        Production Indian Equity Screener (NSE) powered by SMA50/SMA200 Trend Following, 
                        Wilder's RSI 14, and Google Gemini Multi-Source AI Intelligence.
                    </p>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <span class="header-pill pill-live">● NSE Live</span>
                    <span class="header-pill pill-ai">✦ Gemini AI Ready</span>
                </div>
            </div>
            """)

    # Main Tabs
    with gr.Tabs(selected="tab_screener") as main_tabs:

        # =========================================================
        # TAB 1: Market Screener & Algorithmic Scanner
        # =========================================================
        with gr.TabItem("🔍 Market Screener & Scanner", id="tab_screener"):
            with gr.Row():
                # Left Control Panel
                with gr.Column(scale=1):
                    gr.Markdown("#### 1. Stock Universe Selection")
                    universe_selector = gr.Radio(
                        choices=list(BUILTIN_UNIVERSES.keys()) + ["Custom Uploaded File"],
                        value="NSE Main Equities (EQUITY_L.csv)",
                        label="Select Stock Universe"
                    )
                    file_uploader = gr.File(
                        label="Upload Custom Universe (CSV or Excel)",
                        file_types=[".csv", ".xlsx", ".xls"],
                        visible=False
                    )
                    universe_status = gr.Markdown("Symbols Ready: 2,605")
                    universe_preview = gr.DataFrame(
                        label="Universe Preview (First 5 Rows)",
                        interactive=False,
                        wrap=True
                    )

                    gr.Markdown("---")
                    gr.Markdown("#### 2. Market Data Downloader")
                    with gr.Row():
                        start_date_input = gr.Textbox(
                            value=DEFAULT_START_DATE,
                            label="Start Date (YYYY-MM-DD)",
                            placeholder="2015-01-01"
                        )
                        max_stocks_input = gr.Number(
                            value=25,
                            label="Max Stocks to Fetch (0 for All)",
                            precision=0
                        )
                    with gr.Row():
                        skip_existing_check = gr.Checkbox(
                            value=True,
                            label="Skip Cached Symbols",
                            info="Resume downloads without refetching existing"
                        )
                        pause_sec_slider = gr.Slider(
                            minimum=0.0,
                            maximum=2.0,
                            value=DEFAULT_PAUSE_SECONDS,
                            step=0.1,
                            label="Pause between requests (sec)"
                        )

                    download_btn = gr.Button("📥 Download / Update Market Data", variant="secondary")

                    gr.Markdown("---")
                    gr.Markdown("#### 3. Quantitative Engine")
                    scan_btn = gr.Button("🚀 Run Quantitative Technical Scan", variant="primary", size="lg")

                # Right Main Display
                with gr.Column(scale=2):
                    download_status_box = gr.Textbox(
                        label="System Status & Telemetry",
                        value="Ready to scan. Select universe and click 'Run Quantitative Technical Scan'.",
                        interactive=False,
                        lines=2,
                        elem_classes=["terminal-status"]
                    )

                    # Quick Stats Cards
                    with gr.Row():
                        with gr.Column(elem_classes=["metric-card"]):
                            gr.Markdown("<div class='metric-title'>BUY WATCH (Score ≥ 3)</div>")
                            buy_count_display = gr.Markdown("<div class='metric-value buy'>4</div>")
                        with gr.Column(elem_classes=["metric-card"]):
                            gr.Markdown("<div class='metric-title'>HOLD / WAIT (-1 to 2)</div>")
                            hold_count_display = gr.Markdown("<div class='metric-value hold'>9</div>")
                        with gr.Column(elem_classes=["metric-card"]):
                            gr.Markdown("<div class='metric-title'>SELL WATCH (Score ≤ -2)</div>")
                            sell_count_display = gr.Markdown("<div class='metric-value sell'>0</div>")
                        with gr.Column(elem_classes=["metric-card"]):
                            gr.Markdown("<div class='metric-title'>Total Scanned</div>")
                            total_count_display = gr.Markdown("<div class='metric-value'>13</div>")

                    # Filters
                    with gr.Accordion("⚙️ Interactive Filter Controls", open=True):
                        with gr.Row():
                            decision_filter_dd = gr.Dropdown(
                                choices=["ALL", "BUY WATCH", "HOLD / WAIT", "SELL WATCH"],
                                value="ALL",
                                label="Filter by Decision"
                            )
                            min_score_filter = gr.Slider(
                                minimum=-5,
                                maximum=4,
                                value=-5,
                                step=1,
                                label="Minimum Score"
                            )
                            symbol_search_box = gr.Textbox(
                                label="Search Symbol",
                                placeholder="e.g. RELIANCE, TCS, 63MOONS"
                            )
                        with gr.Row():
                            rsi_min_slider = gr.Slider(
                                minimum=0.0,
                                maximum=100.0,
                                value=0.0,
                                step=1.0,
                                label="Min RSI"
                            )
                            rsi_max_slider = gr.Slider(
                                minimum=0.0,
                                maximum=100.0,
                                value=100.0,
                                step=1.0,
                                label="Max RSI"
                            )

                    # Scan Results Table
                    gr.Markdown("💡 *Tip: Click on any row in the table below to automatically open its Deep-Dive chart and AI analysis!*")
                    scan_results_table = gr.DataFrame(
                        label="Scanned Stocks Ranked by Score & 20D Return",
                        interactive=False,
                        wrap=True
                    )

                    # Export Row
                    with gr.Row():
                        export_csv_btn = gr.Button("📥 Export Scan to CSV", variant="secondary")
                        export_excel_btn = gr.Button("📥 Export Scan to Excel", variant="secondary")
                        download_file_out = gr.File(label="Download File", visible=False)

        # =========================================================
        # TAB 2: Single Stock Deep-Dive & Charts
        # =========================================================
        with gr.TabItem("📈 Stock Deep-Dive & Charts", id="tab_deepdive"):
            with gr.Row():
                with gr.Column(scale=3):
                    stock_input = gr.Textbox(
                        label="Stock Symbol (NSE)",
                        value="63MOONS",
                        placeholder="Enter symbol (e.g. 63MOONS, SEJALLTD, RELIANCE, TCS, INFY)"
                    )
                    # Quick Pick Buttons
                    with gr.Row(elem_classes=["quick-pick-container"]):
                        gr.Markdown("<span class='quick-pick-label'>Quick Select:</span>")
                        qp_btns = []
                        for qp in QUICK_TICKERS:
                            qp_btns.append(gr.Button(qp, size="sm", variant="secondary"))
                with gr.Column(scale=1):
                    analyze_stock_btn = gr.Button("🔍 Update Analysis & Charts", variant="primary", size="lg")

            # -----------------------------------------------------
            # TradingView-Style Performance Showcase (2015 - Present)
            # -----------------------------------------------------
            tv_banner_html = gr.HTML()
            with gr.Row():
                tv_timeframe_selector = gr.Radio(
                    choices=["2015 - Present (MAX)", "5Y", "3Y", "1Y", "6M", "YTD", "1M"],
                    value="2015 - Present (MAX)",
                    label="TradingView Price Performance Horizon"
                )
            tv_area_chart = gr.Plot(label="TradingView Area Chart (Price Change 2015 – Present)")

            # Metric Ribbon
            with gr.Row():
                kpi_price = gr.Textbox(label="Last Close", interactive=False)
                kpi_20d_ret = gr.Textbox(label="20D Return", interactive=False)
                kpi_rsi = gr.Textbox(label="RSI 14", interactive=False)
                kpi_sma50 = gr.Textbox(label="SMA 50", interactive=False)
                kpi_sma200 = gr.Textbox(label="SMA 200", interactive=False)
                kpi_score = gr.Textbox(label="Model Score", interactive=False)
                kpi_decision = gr.Textbox(label="Decision", interactive=False)

            # -----------------------------------------------------
            # Technical Multi-Panel Setup (Candlestick + SMAs + RSI 14)
            # -----------------------------------------------------
            with gr.Accordion("📊 Advanced Multi-Panel Technical Setup (Candlestick, SMAs, Volume & RSI 14)", open=True):
                with gr.Row():
                    chart_type_selector = gr.Radio(
                        choices=["Candlestick", "Line"],
                        value="Candlestick",
                        label="Chart Format"
                    )
                    timeframe_selector = gr.Radio(
                        choices=["1M", "3M", "6M", "1Y", "2Y", "ALL"],
                        value="1Y",
                        label="Technical Timeframe"
                    )
                    indicator_toggles = gr.CheckboxGroup(
                        choices=["50-Day SMA", "200-Day SMA", "Volume", "RSI 14"],
                        value=["50-Day SMA", "200-Day SMA", "Volume", "RSI 14"],
                        label="Visible Indicators"
                    )
                stock_chart = gr.Plot(label="Interactive Technical Multi-Panel")

            # Technical Diagnostics Markdown
            stock_diagnostics_md = gr.Markdown()

        # =========================================================
        # TAB 3: AI Stock Advisor & Research
        # =========================================================
        with gr.TabItem("🤖 AI Stock Advisor & Research", id="tab_ai"):
            with gr.Row():
                with gr.Column(scale=2):
                    ai_stock_input = gr.Textbox(
                        label="Target Stock Symbol (NSE)",
                        value="63MOONS",
                        placeholder="Enter ticker (e.g. 63MOONS, SEJALLTD, RELIANCE, TCS)"
                    )
                    # Quick Pick Buttons
                    with gr.Row(elem_classes=["quick-pick-container"]):
                        gr.Markdown("<span class='quick-pick-label'>Quick Select:</span>")
                        ai_qp_btns = []
                        for qp in QUICK_TICKERS:
                            ai_qp_btns.append(gr.Button(qp, size="sm", variant="secondary"))
                with gr.Column(scale=1):
                    ai_model_dd = gr.Dropdown(
                        choices=["gemini-3.5-flash-lite", "gemini-3-flash-preview"],
                        value="gemini-3.5-flash-lite",
                        label="Gemini AI Engine"
                    )
                    include_news_toggle = gr.Checkbox(
                        value=True,
                        label="Include Live Web News (Tavily)",
                        info="Fetch real-time financial market news"
                    )
                with gr.Column(scale=1):
                    ai_focus_dd = gr.Dropdown(
                        choices=[
                            "Full Strategic Investment Report",
                            "Short-Term Swing Trade Setup",
                            "Risk & Capital Preservation Analysis",
                            "Catalyst & Market Sentiment Summary"
                        ],
                        value="Full Strategic Investment Report",
                        label="Report Strategy Focus"
                    )

            generate_ai_btn = gr.Button("🪄 Generate Comprehensive AI Research Report", variant="primary", size="lg")

            with gr.Row():
                with gr.Column(scale=3):
                    ai_report_output = gr.Markdown("Click 'Generate Comprehensive AI Research Report' above to synthesize quantitative indicators and real-time news.")
                with gr.Column(scale=1):
                    ai_news_output = gr.Markdown()

        # =========================================================
        # TAB 4: Database & Cache Explorer
        # =========================================================
        with gr.TabItem("🗄️ Database & Cache Explorer", id="tab_db"):
            with gr.Row():
                refresh_db_btn = gr.Button("🔄 Refresh Database Telemetry", variant="secondary")

            db_stats_card = gr.Markdown()

            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### Stored Symbols & Coverage (Top 50)")
                    db_coverage_table = gr.DataFrame(interactive=False)
                with gr.Column():
                    gr.Markdown("#### Download Error Logs (Recent 50)")
                    db_failures_table = gr.DataFrame(interactive=False)

        # =========================================================
        # TAB 5: Settings & API Configuration
        # =========================================================
        with gr.TabItem("⚙️ Settings & API Configuration", id="tab_settings"):
            gr.Markdown("""
            ### API Keys & Environment Settings
            Configure your external service credentials below. Keys are loaded from `.env` by default and can be updated securely here.
            """)
            with gr.Row():
                with gr.Column():
                    cfg_gemini = gr.Textbox(
                        label="Google Gemini API Key",
                        value=get_gemini_key(),
                        type="password",
                        placeholder="AIzaSy..."
                    )
                    cfg_tavily = gr.Textbox(
                        label="Tavily News Search API Key",
                        value=get_tavily_key(),
                        type="password",
                        placeholder="tvly-dev-..."
                    )
                with gr.Column():
                    cfg_finnhub = gr.Textbox(
                        label="Finnhub Financial API Key",
                        value=get_finnhub_key(),
                        type="password",
                        placeholder="dafs..."
                    )
                    cfg_twelvedata = gr.Textbox(
                        label="TwelveData API Key",
                        value=get_twelvedata_key(),
                        type="password",
                        placeholder="7e2ab..."
                    )

            with gr.Row():
                save_settings_btn = gr.Button("💾 Save API Keys", variant="primary")
                test_apis_btn = gr.Button("⚡ Test All API Connections", variant="secondary")

            settings_status_box = gr.Markdown()

            gr.Markdown("""
            ---
            ### 🚀 Hugging Face Spaces Deployment Guide
            To deploy this application to Hugging Face Spaces:
            1. Create a new Space on [Hugging Face](https://huggingface.co/new-space) selecting **Gradio** as the SDK.
            2. Push the repository files (`app.py`, `backend/`, `data/`, `assets/`, `requirements.txt`, `README.md`).
            3. Set your Secrets in Space Settings (`Settings -> Variables and secrets`):
               - `GEMINI_API_KEY`
               - `TAVILY_API_KEY`
               - `FINNHUB_API_KEY`
               - `TWELVEDATA_API_KEY`
            4. The Space will automatically build and launch!
            """)

    # ---------------------------------------------------------
    # Event Wiring & Interactivity
    # ---------------------------------------------------------

    # 1. Universe Selection
    def toggle_uploader(choice):
        return gr.update(visible=(choice == "Custom Uploaded File"))

    universe_selector.change(toggle_uploader, inputs=[universe_selector], outputs=[file_uploader])
    universe_selector.change(
        on_universe_select,
        inputs=[universe_selector, file_uploader],
        outputs=[symbols_state, download_status_box, universe_preview, universe_status]
    )
    file_uploader.upload(
        on_upload_file,
        inputs=[file_uploader],
        outputs=[symbols_state, download_status_box, universe_preview, universe_status]
    )

    # 2. Download Trigger
    download_btn.click(
        start_download_task,
        inputs=[symbols_state, start_date_input, max_stocks_input, skip_existing_check, pause_sec_slider],
        outputs=[download_status_box, scan_results_table]
    )

    # 3. Scan Trigger
    scan_btn.click(
        start_technical_scan,
        inputs=[],
        outputs=[
            download_status_box,
            scan_results_table,
            full_scan_state,
            buy_count_display,
            hold_count_display,
            sell_count_display,
            total_count_display
        ]
    )

    # 4. Filtering events
    filter_inputs = [full_scan_state, decision_filter_dd, min_score_filter, symbol_search_box, rsi_min_slider, rsi_max_slider]
    decision_filter_dd.change(apply_table_filters, inputs=filter_inputs, outputs=[scan_results_table])
    min_score_filter.change(apply_table_filters, inputs=filter_inputs, outputs=[scan_results_table])
    symbol_search_box.change(apply_table_filters, inputs=filter_inputs, outputs=[scan_results_table])
    rsi_min_slider.change(apply_table_filters, inputs=filter_inputs, outputs=[scan_results_table])
    rsi_max_slider.change(apply_table_filters, inputs=filter_inputs, outputs=[scan_results_table])

    # 5. Interactive Table Row Select -> Switch Tab & Analyze!
    def on_table_row_click(evt: gr.SelectData, scan_df):
        if scan_df is None or scan_df.empty:
            return "63MOONS", "63MOONS", gr.Tabs(selected="tab_deepdive")
        row_idx = evt.index[0]
        if row_idx < len(scan_df):
            selected_sym = str(scan_df.iloc[row_idx]["symbol"])
            return selected_sym, selected_sym, gr.Tabs(selected="tab_deepdive")
        return "63MOONS", "63MOONS", gr.Tabs(selected="tab_deepdive")

    # 5. Interactive Table Row Select -> Switch Tab & Analyze!
    def on_table_row_click(evt: gr.SelectData, scan_df):
        if scan_df is None or scan_df.empty:
            return "63MOONS", "63MOONS", gr.Tabs(selected="tab_deepdive")
        row_idx = evt.index[0]
        if row_idx < len(scan_df):
            selected_sym = str(scan_df.iloc[row_idx]["symbol"])
            return selected_sym, selected_sym, gr.Tabs(selected="tab_deepdive")
        return "63MOONS", "63MOONS", gr.Tabs(selected="tab_deepdive")

    stock_analysis_inputs = [stock_input, chart_type_selector, timeframe_selector, indicator_toggles, tv_timeframe_selector]
    stock_analysis_outputs = [
        kpi_price, kpi_20d_ret, kpi_rsi, kpi_sma50, kpi_sma200, kpi_score, kpi_decision,
        tv_banner_html, tv_area_chart, stock_chart, stock_diagnostics_md
    ]

    scan_results_table.select(
        on_table_row_click,
        inputs=[scan_results_table],
        outputs=[stock_input, ai_stock_input, main_tabs]
    ).then(
        analyze_single_stock,
        inputs=stock_analysis_inputs,
        outputs=stock_analysis_outputs
    )

    # 6. Export Buttons
    def export_csv_action(df):
        path = export_dataframe_to_csv(df)
        return gr.update(value=path, visible=bool(path))

    def export_excel_action(df):
        path = export_dataframe_to_excel(df)
        return gr.update(value=path, visible=bool(path))

    export_csv_btn.click(export_csv_action, inputs=[scan_results_table], outputs=[download_file_out])
    export_excel_btn.click(export_excel_action, inputs=[scan_results_table], outputs=[download_file_out])

    # 7. Single Stock Deep-Dive Analysis
    analyze_stock_btn.click(analyze_single_stock, inputs=stock_analysis_inputs, outputs=stock_analysis_outputs)
    
    # Dedicated responsive listener for TradingView timeframe change
    tv_timeframe_selector.change(
        on_tv_timeframe_change,
        inputs=[stock_input, tv_timeframe_selector],
        outputs=[tv_area_chart, tv_banner_html]
    )

    # Dedicated responsive listener for technical chart parameter changes
    tech_inputs = [stock_input, chart_type_selector, timeframe_selector, indicator_toggles]
    chart_type_selector.change(on_tech_params_change, inputs=tech_inputs, outputs=[stock_chart])
    timeframe_selector.change(on_tech_params_change, inputs=tech_inputs, outputs=[stock_chart])
    indicator_toggles.change(on_tech_params_change, inputs=tech_inputs, outputs=[stock_chart])

    # Quick Pick Buttons for Deep-Dive
    for btn, ticker in zip(qp_btns, QUICK_TICKERS):
        def make_qp_fn(t=ticker):
            return lambda: (t, t)
        btn.click(
            make_qp_fn(ticker),
            inputs=[],
            outputs=[stock_input, ai_stock_input]
        ).then(
            analyze_single_stock,
            inputs=stock_analysis_inputs,
            outputs=stock_analysis_outputs
        )

    # 8. AI Research Report
    generate_ai_btn.click(
        run_ai_advisor,
        inputs=[ai_stock_input, include_news_toggle, ai_model_dd, ai_focus_dd],
        outputs=[ai_report_output, ai_news_output]
    )

    # Quick Pick Buttons for AI Advisor
    for btn, ticker in zip(ai_qp_btns, QUICK_TICKERS):
        def make_ai_qp_fn(t=ticker):
            return lambda: (t, t)
        btn.click(
            make_ai_qp_fn(ticker),
            inputs=[],
            outputs=[ai_stock_input, stock_input]
        ).then(
            run_ai_advisor,
            inputs=[ai_stock_input, include_news_toggle, ai_model_dd, ai_focus_dd],
            outputs=[ai_report_output, ai_news_output]
        )

    # 9. Database Explorer Refresh
    refresh_db_btn.click(
        refresh_db_explorer,
        inputs=[],
        outputs=[db_stats_card, db_coverage_table, db_failures_table]
    )

    # 10. Settings Actions
    save_settings_btn.click(
        save_settings_action,
        inputs=[cfg_gemini, cfg_tavily, cfg_finnhub, cfg_twelvedata],
        outputs=[settings_status_box]
    )
    test_apis_btn.click(
        test_api_connections_action,
        inputs=[cfg_gemini, cfg_tavily, cfg_finnhub, cfg_twelvedata],
        outputs=[settings_status_box]
    )

    # 11. Initial Data Load on Page Load
    def initial_page_load():
        try:
            # Load scan results from file if available
            scan_df = pd.DataFrame()
            if os.path.exists(SCAN_RESULTS_PATH):
                try:
                    scan_df = pd.read_csv(SCAN_RESULTS_PATH)
                except Exception:
                    pass
            
            buy_cnt = str(len(scan_df[scan_df["decision"] == "BUY WATCH"])) if not scan_df.empty else "0"
            hold_cnt = str(len(scan_df[scan_df["decision"] == "HOLD / WAIT"])) if not scan_df.empty else "0"
            sell_cnt = str(len(scan_df[scan_df["decision"] == "SELL WATCH"])) if not scan_df.empty else "0"
            tot_cnt = str(len(scan_df)) if not scan_df.empty else "0"

            symbols, col, preview, msg = load_universe_file(BUILTIN_UNIVERSES["NSE Main Equities (EQUITY_L.csv)"])
            stat_cards, cov_df, fail_df = refresh_db_explorer()
            
            # Analyze default top stock
            c, r, rsi, s50, s200, sc, dec, tv_banner, tv_fig, tech_fig, diag = analyze_single_stock("63MOONS")

            return (
                symbols,
                "System initialized. 13 cached stocks ready. Click on any row to analyze.",
                preview,
                f"Symbols Ready: {len(symbols):,}",
                scan_df,
                scan_df,
                buy_cnt,
                hold_cnt,
                sell_cnt,
                tot_cnt,
                stat_cards,
                cov_df,
                fail_df,
                c, r, rsi, s50, s200, sc, dec,
                tv_banner, tv_fig, tech_fig, diag
            )
        except Exception as e:
            print(f"initial_page_load notice: {e}")
            empty_fig = create_stock_analysis_figure(pd.DataFrame(), "63MOONS")
            empty_tv_fig, empty_banner = create_tradingview_area_chart(pd.DataFrame(), "63MOONS")
            return (
                [], f"System ready. Notice: {e}", pd.DataFrame(), "Symbols Ready: 0",
                pd.DataFrame(), pd.DataFrame(), "0", "0", "0", "0",
                "Database ready.", pd.DataFrame(), pd.DataFrame(),
                "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
                empty_banner, empty_tv_fig, empty_fig, "Ready to analyze."
            )

    demo.load(
        initial_page_load,
        inputs=[],
        outputs=[
            symbols_state,
            download_status_box,
            universe_preview,
            universe_status,
            scan_results_table,
            full_scan_state,
            buy_count_display,
            hold_count_display,
            sell_count_display,
            total_count_display,
            db_stats_card,
            db_coverage_table,
            db_failures_table,
            kpi_price, kpi_20d_ret, kpi_rsi, kpi_sma50, kpi_sma200, kpi_score, kpi_decision,
            tv_banner_html, tv_area_chart, stock_chart, stock_diagnostics_md
        ]
    )

# ---------------------------------------------------------
# Launch Application
# ---------------------------------------------------------
if __name__ == "__main__":
    # Dynamically detect port and host for local development, Render, or cloud hosts
    port = int(os.environ.get("PORT", os.environ.get("GRADIO_SERVER_PORT", 7860)))
    server_name = os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0")

    print(f"🚀 Starting AI Stock Advisor on {server_name}:{port}...")
    demo.queue(default_concurrency_limit=20).launch(
        server_name=server_name,
        server_port=port,
        share=False,
        theme=theme,
        css=custom_css,
        show_error=True
    )
