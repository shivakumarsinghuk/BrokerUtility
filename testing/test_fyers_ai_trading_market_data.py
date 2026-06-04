import unittest

from broker_platform.fyers.ai_trading_market_data import FyersMarketDataAdapter


class FakeRow(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class FakeFrame:
    empty = False

    def __init__(self, rows):
        self.rows = rows

    def iterrows(self):
        for index, row in enumerate(self.rows):
            yield index, FakeRow(row)


class FakeQuote:
    ltp = 104.0
    high = 106.0
    low = 99.0
    volume = 12000
    prev_close = 98.5
    open = 100.0
    bid = 103.95
    ask = 104.05
    change = 5.5
    change_percent = 5.58
    spread = 0.10
    avg_trade_price = 102.5
    last_trade_time = 1780557300


class FakeUtility:
    def fetchOHLC(self, **kwargs):
        return FakeFrame(
            [
                {"date": "2026-06-04 09:15:00", "open": "100", "high": "102", "low": "99", "close": "101", "volume": "1000"},
                {"date": "2026-06-04 09:16:00", "open": "101", "high": "103", "low": "100", "close": "102", "volume": "1100"},
            ]
        )

    def get_quotes(self, requests):
        return {requests[0].symbol: FakeQuote()}


class FyersMarketDataAdapterTest(unittest.TestCase):
    def test_fetch_market_data_converts_history_and_quote_snapshot(self):
        adapter = FyersMarketDataAdapter(utility=FakeUtility())

        candles, meta = adapter.fetch_market_data("RPOWER", "2026-06-04 09:15:00", "2026-06-04 09:30:00")

        self.assertEqual(len(candles), 3)
        self.assertEqual(candles[0]["price"], 101.0)
        self.assertIsNotNone(candles[0]["vwap"])
        self.assertEqual(candles[-1]["price"], 104.0)
        self.assertEqual(meta["regularMarketPrice"], 104.0)
        self.assertEqual(meta["previousClose"], 98.5)
        self.assertEqual(meta["bid"], 103.95)
        self.assertEqual(meta["changePercent"], 5.58)


if __name__ == "__main__":
    unittest.main()
