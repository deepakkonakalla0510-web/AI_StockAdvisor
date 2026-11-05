import os
import sqlite3
from typing import Dict, Any, Optional, List, Generator, Tuple
import numpy as np
import pandas as pd

from backend.config import DEFAULT_DB_PATH, SCAN_RESULTS_PATH
from backend.market_data import get_connection

def calculate_indicators_full(g: pd.DataFrame) -> pd.DataFrame:
    """
    Computes SMA50, SMA200, RSI14, and 20D percentage return for an entire price series.
    Preserves exact formulas from the notebook.
    """
    df = g.sort_values("date").copy()
    base = df["adj_close"].where(df["adj_close"].notna(), df["close"]).astype(float)
    df["base_price"] = base
    df["SMA50"] = base.rolling(50, min_periods=50).mean()
    df["SMA200"] = base.rolling(200, min_periods=200).mean()
    
    # Wilder's RSI calculation (alpha = 1/14, adjust=False)
    d = base.diff()
    ag = d.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    al = (-d.clip(upper=0)).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = ag / al.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    # Handle pure zero downward movements (RSI = 100) or zero movements (RSI = 50)
    rsi = rsi.where(~((al == 0) & (ag > 0)), 100.0)
    rsi = rsi.where(~((al == 0) & (ag == 0)), 50.0)
    df["RSI14"] = rsi
    
    # 20-session percentage return
    df["Return20D_pct"] = base.pct_change(20) * 100
    return df

def analyze_group(g: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Analyzes a group of daily prices for a single stock and returns the scoring,
    decision, reasons, and risks.
    Exact implementation of cell 13 from the original notebook.
    """
    df = calculate_indicators_full(g)
    valid = df.dropna(subset=["RSI14"])
    if valid.empty:
        return None
        
    r = valid.iloc[-1]
    base = df["base_price"]
    score, reasons, risks = 0, [], []
    
    # Moving Average Conditions
    if pd.notna(r["SMA200"]):
        if base.loc[r.name] > r["SMA50"] > r["SMA200"]:
            score += 2
            reasons.append("price > SMA50 > SMA200")
        elif base.loc[r.name] < r["SMA50"] < r["SMA200"]:
            score -= 2
            risks.append("price < SMA50 < SMA200")
        elif r["SMA50"] > r["SMA200"]:
            score += 1
            reasons.append("SMA50 > SMA200")
        else:
            score -= 1
            risks.append("SMA50 < SMA200")
    else:
        risks.append("insufficient 200-day history")
        
    # RSI Conditions
    if 40 <= r["RSI14"] <= 65:
        score += 1
        reasons.append("moderate RSI")
    elif r["RSI14"] > 70:
        score -= 1
        risks.append("RSI above 70")
    elif r["RSI14"] < 30:
        risks.append("RSI below 30")
        
    # 20-Day Return Conditions
    if pd.notna(r["Return20D_pct"]):
        if r["Return20D_pct"] > 0:
            score += 1
            reasons.append("positive 20-session return")
        else:
            score -= 1
            risks.append("negative 20-session return")
            
    # Final Decision
    decision = "BUY WATCH" if score >= 3 else ("SELL WATCH" if score <= -2 else "HOLD / WAIT")
    
    return {
        "symbol": str(g["symbol"].iloc[-1]),
        "date": str(r["date"]),
        "close": round(float(r["close"]), 2),
        "RSI14": round(float(r["RSI14"]), 2),
        "SMA50": round(float(r["SMA50"]), 2) if pd.notna(r["SMA50"]) else None,
        "SMA200": round(float(r["SMA200"]), 2) if pd.notna(r["SMA200"]) else None,
        "Return20D_pct": round(float(r["Return20D_pct"]), 2) if pd.notna(r["Return20D_pct"]) else None,
        "score": int(score),
        "decision": decision,
        "reasons": "; ".join(reasons),
        "risks": "; ".join(risks),
    }

def run_technical_scan_generator(
    db_path: str = DEFAULT_DB_PATH,
    symbols_subset: Optional[List[str]] = None,
    save_to_csv: bool = True
) -> Generator[Tuple[str, float, pd.DataFrame], None, None]:
    """
    Runs the technical analysis scanner across stored database prices.
    Yields live progress updates and returns the sorted scan results DataFrame.
    """
    conn = get_connection(db_path)
    try:
        if symbols_subset and len(symbols_subset) > 0:
            placeholders = ",".join("?" for _ in symbols_subset)
            query = f"SELECT * FROM daily_prices WHERE symbol IN ({placeholders}) ORDER BY symbol, date"
            all_data = pd.read_sql_query(query, conn, params=symbols_subset)
        else:
            all_data = pd.read_sql_query("SELECT * FROM daily_prices ORDER BY symbol, date", conn)
            
        if all_data.empty:
            yield "No price data found in database. Please download data first.", 0.0, pd.DataFrame()
            return
            
        grouped = list(all_data.groupby("symbol"))
        total = len(grouped)
        results = []
        
        yield f"Starting technical scan on {total} symbols...", 0.0, pd.DataFrame()
        
        for idx, (sym, group) in enumerate(grouped, 1):
            res = analyze_group(group)
            if res:
                results.append(res)
                
            if idx % 50 == 0 or idx == total:
                pct = idx / total
                yield f"Scanning indicators: {idx}/{total} ({pct:.1%}) - Found {len(results)} analyzed stocks", pct, pd.DataFrame(results).tail(10) if results else pd.DataFrame()
                
        scan_df = pd.DataFrame(results)
        if not scan_df.empty:
            scan_df = scan_df.sort_values(["score", "Return20D_pct"], ascending=False).reset_index(drop=True)
            if save_to_csv:
                os.makedirs(os.path.dirname(os.path.abspath(SCAN_RESULTS_PATH)), exist_ok=True)
                scan_df.to_csv(SCAN_RESULTS_PATH, index=False)
                
            summary_msg = (
                f"Scan Complete! Successfully analyzed {len(scan_df)} stocks. "
                f"BUY WATCH: {len(scan_df[scan_df['decision'] == 'BUY WATCH'])}, "
                f"HOLD/WAIT: {len(scan_df[scan_df['decision'] == 'HOLD / WAIT'])}, "
                f"SELL WATCH: {len(scan_df[scan_df['decision'] == 'SELL WATCH'])}"
            )
            yield summary_msg, 1.0, scan_df
        else:
            yield "Scan completed but no symbols had sufficient price/RSI history.", 1.0, pd.DataFrame()
    finally:
        conn.close()

def filter_scan_results(
    df: pd.DataFrame,
    decision_filter: str = "ALL",
    min_score: int = -5,
    search_symbol: str = "",
    min_rsi: float = 0.0,
    max_rsi: float = 100.0
) -> pd.DataFrame:
    """
    Filter scan results by decision, minimum score, symbol search, and RSI range.
    """
    if df is None or df.empty:
        return pd.DataFrame()
        
    filtered = df.copy()
    
    if decision_filter and decision_filter != "ALL":
        filtered = filtered[filtered["decision"] == decision_filter]
        
    if "score" in filtered.columns:
        filtered = filtered[filtered["score"] >= min_score]
        
    if search_symbol and search_symbol.strip():
        term = search_symbol.strip().upper()
        filtered = filtered[filtered["symbol"].str.contains(term, case=False, na=False)]
        
    if "RSI14" in filtered.columns:
        filtered = filtered[(filtered["RSI14"] >= min_rsi) & (filtered["RSI14"] <= max_rsi)]
        
    return filtered
