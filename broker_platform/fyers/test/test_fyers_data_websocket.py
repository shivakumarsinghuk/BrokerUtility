# -*- coding: utf-8 -*-
"""Unit tests for the FYERS data WebSocket wrapper, without live credentials."""

import threading
import time
import unittest
from unittest.mock import patch

import pandas as pd

import BrokerUtility.broker_platform.fyers.fyers_utility as fyers_utility_module
from BrokerUtility.broker_platform.fyers.fyers_utility import (
    fyers_data_websocket,
    fyers_utitlity,
)


class FakeFyersDataSocket:
    def __init__(self, **kwargs):
        self.on_message = kwargs["on_message"]
        self.on_error = kwargs["on_error"]
        self.on_connect = kwargs["on_connect"]
        self.on_close = kwargs["on_close"]
        self.subscriptions = []
        self.unsubscriptions = []
        self.closed = False
        self.connected_event = threading.Event()

    def connect(self):
        self.on_connect()

    def keep_running(self):
        pass

    def subscribe(self, symbols, data_type="SymbolUpdate"):
        self.subscriptions.append((list(symbols), data_type))
        self.connected_event.set()

    def unsubscribe(self, symbols, data_type="SymbolUpdate"):
        self.unsubscriptions.append((list(symbols), data_type))

    def is_connected(self):
        return not self.closed

    def close_connection(self):
        self.closed = True
        self.on_close({"code": 200, "message": "closed", "s": "ok"})


class FyersDataWebsocketTests(unittest.TestCase):
    def setUp(self):
        self.socket = FakeFyersDataSocket.__new__(FakeFyersDataSocket)
        self.socket.on_message = None
        self.socket.on_error = None
        self.socket.on_connect = None
        self.socket.on_close = None
        self.socket.subscriptions = []
        self.socket.unsubscriptions = []
        self.socket.closed = False
        self.socket.connected_event = threading.Event()

        def create_fake_socket(**kwargs):
            FakeFyersDataSocket.__init__(self.socket, **kwargs)
            return self.socket

        self.socket_factory = patch(
            "BrokerUtility.broker_platform.fyers.fyers_utility.data_ws.FyersDataSocket",
            side_effect=create_fake_socket,
        )
        self.socket_factory.start()
        self.addCleanup(self.socket_factory.stop)

        self.websocket = fyers_data_websocket("APP-100", "token", "/tmp/Logs")
        self.addCleanup(self.websocket.close)

    def _wait_for_subscriptions(self, count):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if len(self.socket.subscriptions) >= count:
                return
            time.sleep(0.01)
        self.fail(f"Expected at least {count} subscribe calls, got {self.socket.subscriptions}")

    def test_retains_full_message_fields_and_subscribes_on_connect(self):
        self.websocket.subscribe(["NSE:SBIN-EQ"])
        self._wait_for_subscriptions(1)

        message = {
            "symbol": "NSE:SBIN-EQ",
            "ltp": 700.25,
            "last_traded_time": 1793072700,
            "vol_traded_today": 1200,
            "bid_price": 700.2,
            "custom_future_field": "kept",
        }
        self.socket.on_message(message)
        ticks = self.websocket.get_tick_data()

        self.assertEqual(self.socket.subscriptions[0],
                         (["NSE:SBIN-EQ"], "SymbolUpdate"))
        self.assertEqual(ticks.loc[0, "custom_future_field"], "kept")
        self.assertEqual(ticks.loc[0, "ltp"], 700.25)
        self.assertIn("received_at", ticks.columns)
        self.assertIsInstance(ticks.loc[0, "received_at"], pd.Timestamp)

    def test_symbol_filtered_and_latest_tick_snapshots(self):
        self.websocket._on_message({
            "symbol": "NSE:SBIN-EQ", "ltp": 100.0, "last_traded_time": 1793072700,
        })
        self.websocket._on_message({
            "symbol": "NSE:INFY-EQ", "ltp": 200.0, "last_traded_time": 1793072701,
        })
        self.websocket._on_message({
            "symbol": "NSE:SBIN-EQ", "ltp": 101.0, "last_traded_time": 1793072702,
        })

        sbin_ticks = self.websocket.get_tick_data_for_symbols(["NSE:SBIN-EQ"])
        latest_ticks = self.websocket.get_latest_tick_data(["NSE:SBIN-EQ", "NSE:INFY-EQ"])
        all_ticks = self.websocket.get_tick_data()

        self.assertEqual(sbin_ticks["symbol"].tolist(), ["NSE:SBIN-EQ", "NSE:SBIN-EQ"])
        self.assertEqual(sbin_ticks["ltp"].tolist(), [100.0, 101.0])
        self.assertEqual(latest_ticks["ltp"].tolist(), [101.0, 200.0])
        self.assertEqual(len(all_ticks), 3)

    def test_updates_unsubscribes_and_resubscribes_after_reconnect(self):
        self.websocket.subscribe(["NSE:SBIN-EQ"])
        self._wait_for_subscriptions(1)

        self.websocket.subscribe(["NSE:INFY-EQ"])
        self._wait_for_subscriptions(2)
        self.assertEqual(self.socket.unsubscriptions[-1],
                         (["NSE:SBIN-EQ"], "SymbolUpdate"))
        self.assertEqual(self.socket.subscriptions[-1],
                         (["NSE:INFY-EQ", "NSE:SBIN-EQ"], "SymbolUpdate"))

        self.websocket.unsubscribe(["NSE:SBIN-EQ"])
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and len(self.socket.unsubscriptions) < 2:
            time.sleep(0.01)
        self.assertEqual(self.socket.subscriptions[-1],
                         (["NSE:INFY-EQ"], "SymbolUpdate"))

        self.socket.on_connect()
        self._wait_for_subscriptions(4)
        self.assertEqual(self.socket.subscriptions[-1],
                         (["NSE:INFY-EQ"], "SymbolUpdate"))

    def test_close_stops_sdk_socket_and_symbol_format_matches_quotes(self):
        self.websocket.subscribe(["NSE:NIFTY26AUGFUT"])
        self._wait_for_subscriptions(1)
        self.websocket.close()

        self.assertTrue(self.socket.closed)
        self.assertEqual(fyers_utitlity.get_data_websocket_symbol("SBIN", "EQ"),
                         "NSE:SBIN-EQ")
        self.assertEqual(fyers_utitlity.get_data_websocket_symbol("NIFTY26AUGFUT", "FUT"),
                         "NSE:NIFTY26AUGFUT")
        index_request = fyers_utitlity.get_nifty_index_quote_request()
        self.assertEqual((index_request.symbol, index_request.market_type),
                         ("NIFTY50-INDEX", ""))

    def test_error_and_close_callbacks_update_connection_state(self):
        self.websocket.subscribe(["NSE:SBIN-EQ"])
        self._wait_for_subscriptions(1)
        self.assertTrue(self.websocket._is_connected)

        self.socket.on_error({"code": 500, "message": "test error"})
        self.socket.on_close({"code": 1006, "message": "connection lost"})

        self.assertFalse(self.websocket._is_connected)

    def test_broker_factory_caches_one_process_socket(self):
        broker = object.__new__(fyers_utitlity)
        broker.data_websocket = None
        broker.app_id = "APP-100"
        broker.access_token = "token"
        broker.logs_path = "/tmp/Logs"

        with patch.object(fyers_utility_module, "_fyers_data_websocket_instance", None):
            websocket = broker.get_data_websocket()
            try:
                self.assertIs(broker.get_data_websocket(), websocket)
            finally:
                websocket.close()


if __name__ == "__main__":
    unittest.main()
