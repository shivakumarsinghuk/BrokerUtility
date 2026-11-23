from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import Mock, patch

from BrokerUtility.broker_platform.kite.kite_utility import kite_utitlity
from DataTypes.trade_data import DEFINE_TRADE_OPEN


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
        self.assertEqual(kwargs["market_protection"], -1)

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
        self.assertEqual(kwargs["market_protection"], -1)

    @patch("BrokerUtility.broker_platform.kite.kite_utility.KITE_API_RETRY_COUNT", 1)
    def test_limit_order_does_not_set_market_protection(self):
        self.broker.place_order(
            tradingsymbol="NFO:NIFTY26N1725050PE",
            transaction_type="BUY",
            quantity=65,
            order_type="LIMIT",
            price=100.0,
            market_type="OPT",
        )

        kwargs = self.broker.kite.place_order.call_args.kwargs
        self.assertIsNone(kwargs["market_protection"])

    @patch("BrokerUtility.broker_platform.kite.kite_utility.KITE_API_RETRY_COUNT", 1)
    def test_market_order_modification_uses_automatic_market_protection(self):
        self.broker.getOrderInfoByOrderId = Mock(return_value=Mock(variety="regular"))
        self.broker.kite.modify_order.return_value = "order-123"

        modified_id = self.broker.modify_order("order-123", order_type="MARKET")

        self.assertEqual(modified_id, "order-123")
        self.assertEqual(
            self.broker.kite.modify_order.call_args.kwargs["market_protection"], -1)

    @patch("BrokerUtility.broker_platform.kite.kite_utility.KITE_API_RETRY_COUNT", 1)
    def test_market_order_modification_preserves_explicit_market_protection(self):
        self.broker.getOrderInfoByOrderId = Mock(return_value=Mock(variety="regular"))
        self.broker.kite.modify_order.return_value = "order-123"

        self.broker.modify_order(
            "order-123", order_type="MARKET", market_protection=2.5)

        self.assertEqual(
            self.broker.kite.modify_order.call_args.kwargs["market_protection"], 2.5)

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

    def test_order_status_poll_does_not_print_the_full_history_response(self):
        self.broker.kite.order_history.return_value = [
            {
                "tradingsymbol": "NIFTY26N1725300PE",
                "transaction_type": "BUY",
                "price": 112.65,
                "status": "OPEN PENDING",
                "variety": "regular",
                "filled_quantity": 0,
                "average_price": 0,
            },
            {
                "tradingsymbol": "NIFTY26N1725300PE",
                "transaction_type": "BUY",
                "price": 112.65,
                "status": "TRIGGER PENDING",
                "variety": "regular",
                "filled_quantity": 0,
                "average_price": 0,
            },
        ]
        output = StringIO()

        with redirect_stdout(output):
            order_info = self.broker.getOrderInfoByOrderId("order-123")

        self.assertEqual(output.getvalue(), "")
        self.assertEqual(order_info.stock, "NIFTY26N1725300PE")
        self.assertEqual(order_info.status, DEFINE_TRADE_OPEN)


if __name__ == "__main__":
    unittest.main()
