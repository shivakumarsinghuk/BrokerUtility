import unittest

from broker_platform.zebu.ai_trading_market_data import ZebuMarketDataAdapter


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


class FakeUtility:
    def fetchOHLC(self, **kwargs):
        return FakeFrame(
            [
                {"date": "2026-05-30 09:15:00", "open": "100", "high": "102", "low": "99", "close": "101", "volume": "1000", "vwap": "100.5"},
                {"date": "2026-05-30 09:16:00", "open": "101", "high": "103", "low": "100", "close": "102", "volume": "1100", "vwap": "101.2"},
            ]
        )

    def get_quotes(self, requests, p_exchange="NSE"):
        return {requests[0].symbol: FakeQuote()}


class ZebuMarketDataAdapterTest(unittest.TestCase):
    def test_fetch_market_data_converts_candles_and_quote_meta(self):
        adapter = ZebuMarketDataAdapter(utility=FakeUtility())

        candles, meta = adapter.fetch_market_data("RPOWER", "1", "2")

        self.assertEqual(len(candles), 3)
        self.assertEqual(candles[0]["price"], 101.0)
        self.assertEqual(candles[-1]["price"], 104.0)
        self.assertEqual(meta["regularMarketPrice"], 104.0)
        self.assertEqual(meta["previousClose"], 98.5)


if __name__ == "__main__":
    unittest.main()
