import unittest

from broker_platform.fyers.fyers_utility import fyers_utitlity
from datatypes.trade_data import get_quote_request_data


class FakeFyersClient:
    def quotes(self, data):
        return {
            "s": "ok",
            "code": 200,
            "message": "",
            "d": [
                {
                    "n": "NSE:RPOWER-EQ",
                    "v": {
                        "ask": 0,
                        "bid": 28.59,
                        "chp": 4.38,
                        "ch": 1.2,
                        "high_price": 28.94,
                        "low_price": 27.38,
                        "lp": 28.59,
                        "open_price": 27.44,
                        "prev_close_price": 27.39,
                        "spread": 0,
                        "symbol": "NSE:RPOWER-EQ",
                        "tt": "1780704000",
                        "volume": 66252903,
                        "atp": 28.13,
                    },
                }
            ],
        }


class FyersUtilityQuotesTest(unittest.TestCase):
    def test_get_quotes_maps_fyers_v3_quote_payload(self):
        utility = object.__new__(fyers_utitlity)
        utility.fyers = FakeFyersClient()

        quotes = utility.get_quotes([get_quote_request_data("RPOWER", "EQ")])
        quote = quotes["RPOWER"]

        self.assertEqual(quote.ltp, 28.59)
        self.assertEqual(quote.bid, 28.59)
        self.assertEqual(quote.prev_close, 27.39)
        self.assertEqual(quote.change_percent, 4.38)
        self.assertEqual(quote.avg_trade_price, 28.13)
        self.assertEqual(quote.raw["symbol"], "NSE:RPOWER-EQ")


if __name__ == "__main__":
    unittest.main()
