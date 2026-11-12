import unittest
from unittest.mock import Mock, patch

from BrokerUtility.broker_platform.kite.kite_utility import kite_utitlity


class KiteOrderSymbolNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.broker = kite_utitlity.__new__(kite_utitlity)
        self.broker.kite = Mock()
        self.broker.kite.place_order.return_value = "order-123"

    @patch("BrokerUtility.broker_platform.kite.kite_utility.KITE_API_RETRY_COUNT", 1)
    def test_prefixed_option_symbol_uses_bare_symbol_and_nfo_exchange(self):
        order_id = self.broker.place_order(
            tradingsymbol="NFO:NIFTY26N1725050PE",
            transaction_type="BUY",
            quantity=65,
            order_type="MARKET",
            market_type="OPT",
        )

        self.assertEqual(order_id, "order-123")
        kwargs = self.broker.kite.place_order.call_args.kwargs
        self.assertEqual(kwargs["tradingsymbol"], "NIFTY26N1725050PE")
        self.assertEqual(kwargs["exchange"], "NFO")

    @patch("BrokerUtility.broker_platform.kite.kite_utility.KITE_API_RETRY_COUNT", 1)
    def test_bare_future_symbol_uses_nfo_exchange(self):
        self.broker.place_order(
            tradingsymbol="NIFTY26NOVFUT",
            transaction_type="BUY",
            quantity=1,
            order_type="MARKET",
            market_type="FUT",
        )

        kwargs = self.broker.kite.place_order.call_args.kwargs
        self.assertEqual(kwargs["tradingsymbol"], "NIFTY26NOVFUT")
        self.assertEqual(kwargs["exchange"], "NFO")

    @patch("BrokerUtility.broker_platform.kite.kite_utility.KITE_API_RETRY_COUNT", 1)
    def test_rejects_non_nfo_qualified_derivative_symbol(self):
        with self.assertRaisesRegex(ValueError, "Expected an NFO trading symbol"):
            self.broker.place_order(
                tradingsymbol="NSE:NIFTY26N1725050PE",
                transaction_type="BUY",
                quantity=65,
                order_type="MARKET",
                market_type="OPT",
            )

        self.broker.kite.place_order.assert_not_called()


if __name__ == "__main__":
    unittest.main()
