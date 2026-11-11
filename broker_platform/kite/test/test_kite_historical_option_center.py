import threading
import unittest
from unittest.mock import Mock

import pandas as pd

from BrokerUtility.broker_platform.kite.kite_utility import kite_utitlity
from DataTypes.defines import CLOSE_PRICE, DATE_TIME


class HistoricalOptionCenterTests(unittest.TestCase):
    def setUp(self):
        self.broker = kite_utitlity.__new__(kite_utitlity)
        self.broker._historical_option_center_cache = {}
        self.broker._historical_option_center_lock = threading.Lock()
        self.broker.fetchOHLC = Mock(return_value=pd.DataFrame({
            DATE_TIME: pd.to_datetime([
                "2026-11-09 09:15:00",
                "2026-11-09 09:16:00",
            ]),
            CLOSE_PRICE: [24876.0, 24931.0],
        }))

    def test_fetches_full_day_once_and_uses_only_closed_candles(self):
        first_center = self.broker.get_historical_option_center(
            "NIFTY50-INDEX", "26-Nov-2026", "2026-11-09 09:16:00")
        next_center = self.broker.get_historical_option_center(
            "NIFTY50-INDEX", "26-Nov-2026", "2026-11-09 09:17:00")

        self.assertEqual(first_center, 24900)
        self.assertEqual(next_center, 24950)
        self.broker.fetchOHLC.assert_called_once_with(
            "NIFTY26NOVFUT",
            "2026-11-09 09:15:00",
            "2026-11-09 15:30:00",
            interval="minute",
            all_data=True,
            exchange="NFO",
            market_type="FUT",
        )

    def test_fetches_separately_for_a_new_trade_date(self):
        self.broker.get_historical_option_center(
            "NIFTY50-INDEX", "26-Nov-2026", "2026-11-09 09:16:00")
        self.broker.get_historical_option_center(
            "NIFTY50-INDEX", "26-Nov-2026", "2026-11-10 09:16:00")

        self.assertEqual(self.broker.fetchOHLC.call_count, 2)


if __name__ == "__main__":
    unittest.main()
