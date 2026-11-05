import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import List, Tuple, Generator, Optional
import numpy as np
import pandas as pd
import yfinance as yf

from backend.config import DEFAULT_DB_PATH, DEFAULT_START_DATE, DEFAULT_PAUSE_SECONDS

def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Connect to SQLite and ensure required tables exist."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS daily_prices (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            adj_close REAL,
            volume REAL,
            PRIMARY KEY(symbol, date)
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS download_log (
            symbol TEXT PRIMARY KEY,
            status TEXT,
            rows_downloaded INTEGER,
            message TEXT,
            updated_at TEXT
        )"""
    )
    conn.commit()
    return conn

def downloaded_ok(conn: sqlite3.Connection, symbol: str) -> bool:
    """Check if symbol was previously downloaded successfully."""
    row = conn.execute("SELECT status FROM download_log WHERE symbol=?", (symbol,)).fetchone()
    return row is not None and row[0] == "success"

def fetch_one(symbol: str, start_date: str, conn: sqlite3.Connection, timeout: int = 25) -> Tuple[bool, int, str]:
    """
    Download historical prices for one symbol from yfinance and store into SQLite.
    Preserves exact logic from notebook cell 11.
    """
    clean_symbol = symbol.strip().upper()
    ticker_str = f"{clean_symbol}.NS" if not clean_symbol.endswith(".NS") and not clean_symbol.endswith(".BO") else clean_symbol
    base_symbol = clean_symbol.replace(".NS", "").replace(".BO", "")

    try:
        hist = yf.download(
            ticker_str,
            start=start_date,
            auto_adjust=False,
            progress=False,
            threads=False,
            timeout=timeout,
        )
        if hist is None or hist.empty:
            raise ValueError(f"No history returned for {ticker_str}; symbol may be unlisted or unsupported.")
            
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)
            
        hist = hist.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
            }
        )
        
        for c in ["open", "high", "low", "close"]:
            if c not in hist.columns:
                raise ValueError("Missing OHLC columns: " + str(list(hist.columns)))
                
        if "adj_close" not in hist.columns:
            hist["adj_close"] = hist["close"]
        if "volume" not in hist.columns:
            hist["volume"] = np.nan
            
        hist = hist.reset_index()
        date_col = "Date" if "Date" in hist.columns else hist.columns[0]
        
        rows = []
        for _, r in hist.iterrows():
            dt = pd.to_datetime(r[date_col]).strftime("%Y-%m-%d")
            
            def val(k):
                v = r.get(k, np.nan)
                return None if pd.isna(v) else float(v)
                
            rows.append((
                base_symbol,
                dt,
                val("open"),
                val("high"),
                val("low"),
                val("close"),
                val("adj_close"),
                val("volume"),
            ))
            
        conn.executemany("INSERT OR REPLACE INTO daily_prices VALUES (?,?,?,?,?,?,?,?)", rows)
        conn.execute(
            "INSERT OR REPLACE INTO download_log VALUES (?,?,?,?,?)",
            (base_symbol, "success", len(rows), "", datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return True, len(rows), ""
        
    except Exception as e:
        conn.execute(
            "INSERT OR REPLACE INTO download_log VALUES (?,?,?,?,?)",
            (base_symbol, "failed", 0, str(e)[:500], datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return False, 0, str(e)

def download_batch_generator(
    symbols: List[str],
    start_date: str = DEFAULT_START_DATE,
    skip_existing: bool = True,
    pause_seconds: float = DEFAULT_PAUSE_SECONDS,
    max_stocks: Optional[int] = None,
    db_path: str = DEFAULT_DB_PATH
) -> Generator[Tuple[str, float, pd.DataFrame], None, None]:
    """
    Generator that processes symbol downloads and yields live status, progress, and coverage preview.
    Used for real-time progress updates in Gradio.
    """
    conn = get_connection(db_path)
    symbols_to_process = symbols if max_stocks is None else symbols[:max_stocks]
    total = len(symbols_to_process)
    
    if total == 0:
        yield "No symbols provided to download.", 0.0, pd.DataFrame()
        conn.close()
        return

    ok_count = 0
    fail_count = 0
    skipped_count = 0
    
    for idx, sym in enumerate(symbols_to_process, 1):
        if skip_existing and downloaded_ok(conn, sym):
            skipped_count += 1
            progress_pct = idx / total
            if idx % 10 == 0 or idx == total:
                yield (
                    f"Processing: {idx}/{total} ({progress_pct:.1%}) | Success: {ok_count} | Skipped: {skipped_count} | Failed: {fail_count} | Current: {sym} (Cached)",
                    progress_pct,
                    get_coverage_summary(conn)
                )
            continue
            
        ok, n_rows, msg = fetch_one(sym, start_date=start_date, conn=conn)
        if ok:
            ok_count += 1
        else:
            fail_count += 1
            
        progress_pct = idx / total
        status_msg = (
            f"Downloading: {idx}/{total} ({progress_pct:.1%}) | "
            f"Success: {ok_count} | Skipped: {skipped_count} | Failed: {fail_count} | "
            f"Last: {sym} ({'OK ' + str(n_rows) + ' rows' if ok else 'Err: ' + msg[:40]})"
        )
        yield status_msg, progress_pct, get_coverage_summary(conn)
        
        if pause_seconds > 0:
            time.sleep(pause_seconds)
            
    final_msg = f"Download complete! Successfully fetched: {ok_count}, Skipped (existing): {skipped_count}, Failed: {fail_count} out of {total} stocks."
    yield final_msg, 1.0, get_coverage_summary(conn)
    conn.close()

def get_coverage_summary(conn: sqlite3.Connection, limit: int = 15) -> pd.DataFrame:
    """Return top stored symbols by latest date and row count."""
    try:
        query = """
            SELECT symbol, COUNT(*) AS daily_rows, MIN(date) AS first_date, MAX(date) AS last_date
            FROM daily_prices
            GROUP BY symbol
            ORDER BY daily_rows DESC
            LIMIT ?
        """
        return pd.read_sql_query(query, conn, params=(limit,))
    except Exception:
        return pd.DataFrame(columns=["symbol", "daily_rows", "first_date", "last_date"])

def get_db_stats(db_path: str = DEFAULT_DB_PATH) -> dict:
    """Return overall statistics of the SQLite database."""
    conn = get_connection(db_path)
    try:
        symbols_count = conn.execute("SELECT COUNT(DISTINCT symbol) FROM daily_prices").fetchone()[0]
        total_rows = conn.execute("SELECT COUNT(*) FROM daily_prices").fetchone()[0]
        dates = conn.execute("SELECT MIN(date), MAX(date) FROM daily_prices").fetchone()
        success_logs = conn.execute("SELECT COUNT(*) FROM download_log WHERE status='success'").fetchone()[0]
        fail_logs = conn.execute("SELECT COUNT(*) FROM download_log WHERE status='failed'").fetchone()[0]
        
        db_size_mb = 0.0
        if os.path.exists(db_path):
            db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
            
        return {
            "symbols_count": symbols_count,
            "total_rows": total_rows,
            "min_date": dates[0] or "N/A",
            "max_date": dates[1] or "N/A",
            "success_count": success_logs,
            "failure_count": fail_logs,
            "db_size_mb": round(db_size_mb, 2),
            "db_path": db_path
        }
    finally:
        conn.close()

def get_stored_symbols_list(db_path: str = DEFAULT_DB_PATH) -> List[str]:
    """Get list of symbols that have price data stored."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT DISTINCT symbol FROM daily_prices ORDER BY symbol").fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()

def fetch_single_stock_on_demand(symbol: str, start_date: str = "2015-01-01", db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Fetch history for a single stock from 2015 till present. Checks DB first; if missing or stale, downloads and caches.
    """
    conn = get_connection(db_path)
    try:
        clean_symbol = symbol.strip().upper().replace(".NS", "").replace(".BO", "")
        # Query existing data
        df = pd.read_sql_query(
            "SELECT * FROM daily_prices WHERE symbol=? ORDER BY date",
            conn,
            params=(clean_symbol,)
        )
        # If empty or fewer than 50 rows, fetch live from 2015-01-01
        if df.empty or len(df) < 50:
            ok, n, msg = fetch_one(clean_symbol, start_date=start_date, conn=conn)
            if ok:
                df = pd.read_sql_query(
                    "SELECT * FROM daily_prices WHERE symbol=? ORDER BY date",
                    conn,
                    params=(clean_symbol,)
                )
        return df
    finally:
        conn.close()

