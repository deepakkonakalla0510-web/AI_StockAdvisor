from typing import Optional, List
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from backend.technical_analysis import calculate_indicators_full

def create_stock_analysis_figure(
    df: pd.DataFrame,
    symbol: str,
    chart_type: str = "Candlestick",
    timeframe: str = "1Y",
    show_sma50: bool = True,
    show_sma200: bool = True,
    show_volume: bool = True,
    show_rsi: bool = True
) -> go.Figure:
    """
    Creates an interactive, customizable multi-panel financial chart:
    - Main Panel: Price (Candlestick / Line) with SMA50 and SMA200 overlays
    - Optional Subplot 1: Trading Volume
    - Optional Subplot 2: Wilder's RSI (14) with key momentum thresholds
    """
    if df is None or df.empty or len(df) < 5:
        fig = go.Figure()
        fig.add_annotation(
            text=f"No price history available to chart for {symbol}.",
            showarrow=False,
            font=dict(size=16, color="#94a3b8"),
            xref="paper", yref="paper", x=0.5, y=0.5
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0b0f19",
            plot_bgcolor="#111827",
            height=600
        )
        return fig

    # Ensure technical indicators are calculated
    if "SMA50" not in df.columns or "RSI14" not in df.columns:
        df = calculate_indicators_full(df)

    # Filter based on selected timeframe
    plot_df = df.sort_values("date").copy()
    if timeframe == "1M":
        plot_df = plot_df.tail(22)
    elif timeframe == "3M":
        plot_df = plot_df.tail(66)
    elif timeframe == "6M":
        plot_df = plot_df.tail(130)
    elif timeframe == "1Y":
        plot_df = plot_df.tail(252)
    elif timeframe == "2Y":
        plot_df = plot_df.tail(504)
    # "ALL" uses all available records

    # Determine dynamic subplot structure
    rows = 1
    row_heights = [1.0]
    specs = [[{"secondary_y": False}]]
    subplot_titles = [f"{symbol} • Price (INR)"]

    has_volume = show_volume and "volume" in plot_df.columns and plot_df["volume"].notna().any()
    has_rsi = show_rsi and "RSI14" in plot_df.columns

    if has_volume and has_rsi:
        rows = 3
        row_heights = [0.60, 0.20, 0.20]
        specs = [[{}], [{}], [{}]]
        subplot_titles = [f"{symbol} • Price (INR)", "Volume", "RSI 14 Momentum"]
        vol_row = 2
        rsi_row = 3
    elif has_volume and not has_rsi:
        rows = 2
        row_heights = [0.75, 0.25]
        specs = [[{}], [{}]]
        subplot_titles = [f"{symbol} • Price (INR)", "Volume"]
        vol_row = 2
        rsi_row = None
    elif not has_volume and has_rsi:
        rows = 2
        row_heights = [0.75, 0.25]
        specs = [[{}], [{}]]
        subplot_titles = [f"{symbol} • Price (INR)", "RSI 14 Momentum"]
        vol_row = None
        rsi_row = 2
    else:
        vol_row = None
        rsi_row = None

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=row_heights,
        subplot_titles=subplot_titles
    )

    # Main Price Trace
    if chart_type == "Candlestick" and all(c in plot_df.columns for c in ["open", "high", "low", "close"]):
        fig.add_trace(
            go.Candlestick(
                x=plot_df["date"],
                open=plot_df["open"],
                high=plot_df["high"],
                low=plot_df["low"],
                close=plot_df["close"],
                name="Price (OHLC)",
                increasing_line_color="#10b981",  # Vibrant emerald
                increasing_fillcolor="#10b981",
                decreasing_line_color="#f43f5e",  # Vibrant rose/crimson
                decreasing_fillcolor="#f43f5e",
            ),
            row=1, col=1
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=plot_df["date"],
                y=plot_df["close"],
                name="Close Price",
                line=dict(color="#38bdf8", width=2.2),  # Electric sky blue
                mode="lines"
            ),
            row=1, col=1
        )

    # SMA 50 Overlay
    if show_sma50 and "SMA50" in plot_df.columns and plot_df["SMA50"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=plot_df["date"],
                y=plot_df["SMA50"],
                name="SMA 50 (Short Trend)",
                line=dict(color="#f59e0b", width=1.8),  # Amber
                mode="lines"
            ),
            row=1, col=1
        )

    # SMA 200 Overlay
    if show_sma200 and "SMA200" in plot_df.columns and plot_df["SMA200"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=plot_df["date"],
                y=plot_df["SMA200"],
                name="SMA 200 (Long Trend)",
                line=dict(color="#ec4899", width=2.0),  # Pink/Rose
                mode="lines"
            ),
            row=1, col=1
        )

    # Volume Subplot
    if vol_row is not None:
        if "open" in plot_df.columns:
            bar_colors = ["#10b981" if c >= o else "#f43f5e" for c, o in zip(plot_df["close"], plot_df["open"])]
        else:
            bar_colors = ["#60a5fa"] * len(plot_df)

        fig.add_trace(
            go.Bar(
                x=plot_df["date"],
                y=plot_df["volume"],
                name="Volume",
                marker_color=bar_colors,
                opacity=0.75
            ),
            row=vol_row, col=1
        )

    # RSI Subplot
    if rsi_row is not None:
        fig.add_trace(
            go.Scatter(
                x=plot_df["date"],
                y=plot_df["RSI14"],
                name="RSI (14)",
                line=dict(color="#a855f7", width=2.0),  # Purple
                mode="lines"
            ),
            row=rsi_row, col=1
        )

        # Overbought reference line (70)
        fig.add_hline(
            y=70, line_dash="dash", line_color="#f43f5e", line_width=1.2,
            row=rsi_row, col=1, annotation_text="Overbought 70", annotation_position="top right",
            annotation_font=dict(size=9, color="#f43f5e")
        )
        # Moderate Sweet Spot Upper Band (65)
        fig.add_hline(
            y=65, line_dash="dot", line_color="#f59e0b", line_width=0.8,
            row=rsi_row, col=1
        )
        # Moderate Sweet Spot Lower Band (40)
        fig.add_hline(
            y=40, line_dash="dot", line_color="#f59e0b", line_width=0.8,
            row=rsi_row, col=1
        )
        # Oversold reference line (30)
        fig.add_hline(
            y=30, line_dash="dash", line_color="#10b981", line_width=1.2,
            row=rsi_row, col=1, annotation_text="Oversold 30", annotation_position="bottom right",
            annotation_font=dict(size=9, color="#10b981")
        )

    # Global Aesthetic Styling
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#06070a",   # Render obsidian deep dark
        plot_bgcolor="#0b0d15",    # Subtle elevated dark surface
        margin=dict(l=55, r=40, t=55, b=40),
        height=720,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color="#cbd5e1")
        ),
        xaxis=dict(gridcolor="#161925", rangeslider=dict(visible=False)),
        xaxis2=dict(gridcolor="#161925") if rows >= 2 else dict(),
        xaxis3=dict(gridcolor="#161925") if rows >= 3 else dict(),
    )

    fig.update_yaxes(title_text="Price (₹)", row=1, col=1, gridcolor="#161925", title_font=dict(size=12, color="#94a3b8"))
    if vol_row is not None:
        fig.update_yaxes(title_text="Vol", row=vol_row, col=1, gridcolor="#161925", title_font=dict(size=11, color="#94a3b8"))
    if rsi_row is not None:
        fig.update_yaxes(title_text="RSI", row=rsi_row, col=1, range=[0, 100], gridcolor="#161925", title_font=dict(size=11, color="#94a3b8"))

    return fig

def create_tradingview_area_chart(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str = "2015 - Present (MAX)"
) -> tuple[go.Figure, str]:
    """
    Creates a TradingView-style Area Chart with price change from 2015 till present:
    - High-impact header: Symbol, Current Price, Net Absolute Change, and % Return
    - Clean emerald / rose gradient area line
    - Right-side Y-axis, interactive crosshairs, and date-range zoom
    """
    if df is None or df.empty or len(df) < 2:
        fig = go.Figure()
        fig.add_annotation(
            text=f"No price history available from 2015 to present for {symbol}.",
            showarrow=False,
            font=dict(size=16, color="#94a3b8"),
            xref="paper", yref="paper", x=0.5, y=0.5
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#080c14",
            plot_bgcolor="#080c14",
            height=480
        )
        empty_banner = f"""
        <div class="tv-header-card">
            <span class="tv-symbol-pill">{symbol}</span>
            <span class="tv-current-price">₹0.00</span>
            <span class="tv-change-pill">No Data</span>
        </div>
        """
        return fig, empty_banner

    full_df = df.sort_values("date").copy()
    
    # Slice according to selected timeframe
    if timeframe == "1M":
        plot_df = full_df.tail(22).copy()
    elif timeframe == "6M":
        plot_df = full_df.tail(126).copy()
    elif timeframe == "1Y":
        plot_df = full_df.tail(252).copy()
    elif timeframe == "3Y":
        plot_df = full_df.tail(756).copy()
    elif timeframe == "5Y":
        plot_df = full_df.tail(1260).copy()
    elif timeframe == "YTD":
        curr_year = pd.to_datetime(full_df["date"].iloc[-1]).year
        ytd_df = full_df[pd.to_datetime(full_df["date"]).dt.year == curr_year]
        plot_df = ytd_df.copy() if not ytd_df.empty else full_df.tail(252).copy()
    else:  # "2015 - Present (MAX)"
        # Default: all data from 2015 onwards
        df_2015 = full_df[full_df["date"] >= "2015-01-01"]
        plot_df = df_2015.copy() if not df_2015.empty else full_df.copy()

    start_price = float(plot_df["close"].iloc[0])
    current_price = float(plot_df["close"].iloc[-1])
    delta_p = current_price - start_price
    pct_change = (delta_p / start_price) * 100 if start_price > 0 else 0.0

    is_positive = delta_p >= 0
    main_color = "#00c076" if is_positive else "#f43f5e"
    fill_color = "rgba(0, 192, 118, 0.12)" if is_positive else "rgba(244, 63, 94, 0.12)"
    sign_str = "+" if is_positive else ""
    pill_class = "pill-positive" if is_positive else "pill-negative"

    # Historical stats
    high_period = plot_df["close"].max()
    low_period = plot_df["close"].min()
    w52_slice = full_df.tail(252)
    w52_high = w52_slice["close"].max() if not w52_slice.empty else high_period
    w52_low = w52_slice["close"].min() if not w52_slice.empty else low_period
    first_record_date = str(plot_df["date"].iloc[0])
    latest_record_date = str(plot_df["date"].iloc[-1])

    # Plotly Figure
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=plot_df["date"],
            y=plot_df["close"],
            name=symbol,
            mode="lines",
            line=dict(color=main_color, width=2.2, shape="spline", smoothing=0.3),
            fill="tozeroy",
            fillcolor=fill_color,
            hovertemplate="<b>₹%{y:,.2f}</b><br><span style='font-size:11px;color:#94a3b8'>%{x|%d %b %Y}</span><extra></extra>"
        )
    )

    # Style exactly like Render / TradingView aesthetic
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#08090f",   # Render obsidian canvas
        plot_bgcolor="#08090f",
        margin=dict(l=20, r=65, t=15, b=30),
        height=480,
        hovermode="x unified",
        showlegend=False
    )

    # X-Axis with clean subtle grid & purple crosshair spike
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#161925",
        gridwidth=1,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="#a855f7",
        spikethickness=1,
        spikedash="dot",
        tickfont=dict(size=11, color="#64748b")
    )

    # Y-Axis on RIGHT side with currency format and purple crosshair
    fig.update_yaxes(
        side="right",
        showgrid=True,
        gridcolor="#161925",
        gridwidth=1,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="#a855f7",
        spikethickness=1,
        spikedash="dot",
        tickprefix="₹",
        tickformat=",.1f",
        tickfont=dict(size=11, color="#94a3b8")
    )

    # TradingView-style Header Card Banner
    header_html = f"""
    <div class="tv-header-card">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 8px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div class="tv-logo-circle">{symbol[:2]}</div>
                <div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 18px; font-weight: 700; color: #f8fafc;">{symbol}</span>
                        <span style="font-size: 11px; background: #1e293b; color: #94a3b8; padding: 2px 6px; border-radius: 4px; font-weight: 600;">NSE</span>
                    </div>
                    <div style="font-size: 12px; color: #64748b;">National Stock Exchange of India • Daily History</div>
                </div>
            </div>
            <div style="display: flex; align-items: baseline; gap: 10px;">
                <span class="tv-price-large">₹{current_price:,.2f}</span>
                <span class="tv-change-badge {pill_class}">
                    {sign_str}₹{abs(delta_p):,.2f} ({sign_str}{pct_change:+.2f}%)
                </span>
            </div>
        </div>
        <div class="tv-stats-ribbon">
            <div class="tv-stat-item">
                <span class="tv-stat-lbl">Timeframe:</span>
                <span class="tv-stat-val">{first_record_date} → {latest_record_date}</span>
            </div>
            <div class="tv-stat-item">
                <span class="tv-stat-lbl">Starting Price (2015):</span>
                <span class="tv-stat-val">₹{start_price:,.2f}</span>
            </div>
            <div class="tv-stat-item">
                <span class="tv-stat-lbl">Period Range:</span>
                <span class="tv-stat-val">₹{low_period:,.2f} – ₹{high_period:,.2f}</span>
            </div>
            <div class="tv-stat-item">
                <span class="tv-stat-lbl">52-Week Range:</span>
                <span class="tv-stat-val">₹{w52_low:,.2f} – ₹{w52_high:,.2f}</span>
            </div>
        </div>
    </div>
    """

    return fig, header_html
