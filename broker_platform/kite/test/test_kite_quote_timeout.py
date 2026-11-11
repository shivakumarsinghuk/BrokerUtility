import unittest
from unittest.mock import patch

from requests.exceptions import ReadTimeout

from BrokerUtility.broker_platform.kite.kite_utility import (
    KITE_API_RETRY_COUNT,
    kite_utitlity,
)
from DataTypes.trade_data import get_quote_request_data


class FakeKite:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def quote(self, symbol):
        self.calls.append(symbol)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class KiteQuoteTimeoutTests(unittest.TestCase):
    def make_broker(self, responses):
        broker = kite_utitlity.__new__(kite_utitlity)
        broker.kite = FakeKite(responses)
        return broker

    def test_quote_retries_after_read_timeout(self):
        expected = {"NFO:NIFTY26NOVFUT": {"last_price": 100.0}}
        broker = self.make_broker([ReadTimeout("timed out"), expected])

        with patch("BrokerUtility.broker_platform.kite.kite_utility.time.sleep"):
            result = broker.get_quote(
                get_quote_request_data("NIFTY26NOVFUT", "FUT"))

        self.assertEqual(result, expected["NFO:NIFTY26NOVFUT"])
        self.assertEqual(len(broker.kite.calls), 2)

    def test_quote_returns_none_after_all_read_timeouts(self):
        broker = self.make_broker(
            [ReadTimeout("timed out") for _ in range(KITE_API_RETRY_COUNT)])

        with patch("BrokerUtility.broker_platform.kite.kite_utility.time.sleep") as sleep:
            result = broker.get_quote(
                get_quote_request_data("NIFTY26NOVFUT", "FUT"))

        self.assertIsNone(result)
        self.assertEqual(len(broker.kite.calls), KITE_API_RETRY_COUNT)
        self.assertEqual(sleep.call_count, KITE_API_RETRY_COUNT - 1)

    def test_unrelated_kite_errors_are_not_suppressed(self):
        broker = self.make_broker([ValueError("unexpected response")])

        with self.assertRaisesRegex(ValueError, "unexpected response"):
            broker.get_quote(get_quote_request_data("NIFTY26NOVFUT", "FUT"))


if __name__ == "__main__":
    unittest.main()
