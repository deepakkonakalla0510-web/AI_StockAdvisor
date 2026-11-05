import re
import os
from pathlib import Path
from typing import List, Tuple, Optional
import pandas as pd

def norm(s: str) -> str:
    """Normalize string by removing non-alphanumeric characters and lowercasing."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

def extract_symbols_from_df(raw: pd.DataFrame) -> Tuple[List[str], Optional[str]]:
    """
    Identifies the symbol column and cleans symbols using the exact logic from the notebook.
    """
    cols = {norm(c): c for c in raw.columns}
    symbol_candidates = [
        "symbol", "tradingsymbol", "ticker", "securitysymbol",
        "securitiessymbol", "scripcd", "scripsymbol"
    ]
    symbol_col = next((cols[k] for k in symbol_candidates if k in cols), None)
    
    if symbol_col is None:
        # Fallback: check if any column contains 'symbol' or 'ticker'
        for col in raw.columns:
            if "symbol" in col.lower() or "ticker" in col.lower():
                symbol_col = col
                break

    if symbol_col is None:
        return [], None

    universe = raw[symbol_col].astype(str).str.strip().dropna().drop_duplicates().tolist()
    # Filter valid characters and exclude nan/none
    clean_universe = [
        s for s in universe
        if re.fullmatch(r"[A-Za-z0-9&._-]+", s) and s.lower() not in ["nan", "none", ""]
    ]
    return clean_universe, symbol_col

def load_universe_file(file_path: str) -> Tuple[List[str], Optional[str], pd.DataFrame, str]:
    """
    Load a CSV or Excel file, extract symbols and return preview dataframe with status message.
    """
    if not os.path.exists(file_path):
        return [], None, pd.DataFrame(), f"Error: File not found at {file_path}"
    
    try:
        if file_path.lower().endswith(".xlsx") or file_path.lower().endswith(".xls"):
            raw = pd.read_excel(file_path)
        else:
            raw = pd.read_csv(file_path)
            
        symbols, col_name = extract_symbols_from_df(raw)
        if not symbols:
            return [], None, raw.head(10), f"Warning: No valid symbol column found in {Path(file_path).name}. Available columns: {list(raw.columns)}"
        
        msg = f"Successfully loaded {len(symbols)} symbols from '{Path(file_path).name}' (Symbol column: '{col_name}')"
        return symbols, col_name, raw.head(10), msg
    except Exception as e:
        return [], None, pd.DataFrame(), f"Error reading file {file_path}: {str(e)}"

