import os
import pandas as pd
from datetime import datetime

from backend.config import DATA_DIR

def export_dataframe_to_csv(df: pd.DataFrame, prefix: str = "scan_results") -> str:
    """Export a DataFrame to a downloadable timestamped CSV file."""
    if df is None or df.empty:
        return ""
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.csv"
    filepath = str(DATA_DIR / filename)
    df.to_csv(filepath, index=False)
    return filepath

def export_dataframe_to_excel(df: pd.DataFrame, prefix: str = "scan_results") -> str:
    """Export a DataFrame to a downloadable timestamped Excel file."""
    if df is None or df.empty:
        return ""
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.xlsx"
    filepath = str(DATA_DIR / filename)
    df.to_excel(filepath, index=False)
    return filepath

