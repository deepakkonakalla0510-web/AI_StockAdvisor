import os
import sys
import unittest
import pandas as pd
import numpy as np

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import BUILTIN_UNIVERSES, DEFAULT_DB_PATH
from backend.data_loader import load_universe_file
from backend.technical_analysis import analyze_group, calculate_indicators_full, filter_scan_results
from backend.charts import create_stock_analysis_figure, create_tradingview_area_chart

class TestStockAdvisorBackend(unittest.TestCase):

    def test_universe_loading(self):
        csv_path = BUILTIN_UNIVERSES["NSE Main Equities (EQUITY_L.csv)"]
        symbols, col, preview, msg = load_universe_file(csv_path)
        self.assertGreater(len(symbols), 2000, "EQUITY_L.csv should contain > 2000 symbols")
        self.assertIsNotNone(col, "Symbol column should be detected")
        self.assertIn("20MICRONS", symbols)

    def test_technical_analysis_algorithm(self):
        # Create synthetic time series with known behavior (250 sessions)
        dates = pd.date_range("2024-01-01", periods=250, freq="B").strftime("%Y-%m-%d").tolist()
        # Uptrending price: 100 to 200
        prices = np.linspace(100, 200, 250)
        df = pd.DataFrame({
            "symbol": ["TEST"] * 250,
            "date": dates,
            "open": prices - 1,
            "high": prices + 2,
            "low": prices - 2,
            "close": prices,
            "adj_close": prices,
            "volume": [100000] * 250
        })

        res = analyze_group(df)
        self.assertIsNotNone(res)
        self.assertEqual(res["symbol"], "TEST")
        self.assertGreater(res["score"], 0, "Uptrend should have positive score")
        self.assertIn("price > SMA50 > SMA200", res["reasons"])
        self.assertIn("positive 20-session return", res["reasons"])
        # RSI 100 triggers overbought deduction (-1), score is 2 -> HOLD / WAIT
        self.assertEqual(res["score"], 2)
        self.assertEqual(res["decision"], "HOLD / WAIT")
        self.assertIn("RSI above 70", res["risks"])

    def test_filtering(self):
        sample_df = pd.DataFrame([
            {"symbol": "STOCKA", "score": 4, "decision": "BUY WATCH", "RSI14": 55.0},
            {"symbol": "STOCKB", "score": 0, "decision": "HOLD / WAIT", "RSI14": 45.0},
            {"symbol": "STOCKC", "score": -3, "decision": "SELL WATCH", "RSI14": 25.0},
        ])
        filtered = filter_scan_results(sample_df, decision_filter="BUY WATCH", min_score=3)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]["symbol"], "STOCKA")

    def test_chart_creation(self):
        dates = pd.date_range("2024-01-01", periods=250, freq="B").strftime("%Y-%m-%d").tolist()
        prices = np.linspace(100, 150, 250)
        df = pd.DataFrame({
            "symbol": ["TEST"] * 250,
            "date": dates,
            "open": prices,
            "high": prices + 1,
            "low": prices - 1,
            "close": prices,
            "adj_close": prices,
            "volume": [50000] * 250
        })
        fig = create_stock_analysis_figure(df, "TEST", chart_type="Candlestick")
        self.assertIsNotNone(fig)
        self.assertEqual(len(fig.data), 5) # Candlestick, SMA50, SMA200, Volume, RSI14

    def test_tradingview_area_chart(self):
        dates = pd.date_range("2015-01-01", periods=1000, freq="B").strftime("%Y-%m-%d").tolist()
        prices = np.linspace(100, 500, 1000)
        df = pd.DataFrame({
            "symbol": ["RELIANCE"] * 1000,
            "date": dates,
            "open": prices,
            "high": prices + 2,
            "low": prices - 2,
            "close": prices,
            "adj_close": prices,
            "volume": [100000] * 1000
        })
        fig, banner = create_tradingview_area_chart(df, "RELIANCE", timeframe="2015 - Present (MAX)")
        self.assertIsNotNone(fig)
        self.assertIn("RELIANCE", banner)
        self.assertIn("tv-header-card", banner)
        self.assertIn("pill-positive", banner) # 100 -> 500 is positive
        self.assertEqual(fig.layout.yaxis.side, "right")

if __name__ == "__main__":
    unittest.main()
