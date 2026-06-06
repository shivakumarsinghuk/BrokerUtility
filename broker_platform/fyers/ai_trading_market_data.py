# -*- coding: utf-8 -*-
"""
Read-only FYERS market-data adapter for AI-Trading.

FYERS History API supplies OHLCV candles. FYERS Quotes API supplies the latest
snapshot fields such as LTP, bid/ask, change, percent change, and volume. This
adapter combines both sources and calculates missing analytics such as VWAP from
available OHLCV data before returning AI-Trading's common ``candles, meta``
contract.
"""

import datetime as dt
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


class FyersMarketDataAdapter:
    """Convert FYERS candle and quote responses into AI-Trading data shapes."""

    def __init__(
        self,
        user_id="",
        client_id="",
        secret_key="",
        pin="",
        totp_key="",
        phone_no="",
        access_token="",
        refresh_token="",
        utility=None,
    ):
        self.utility = utility
        if self.utility is None:
            from broker_platform.fyers.fyers_utility import fyers_utitlity

            self.utility = fyers_utitlity(
                user_name=user_id,
                client_id=client_id,
                secret_id=secret_key,
                pin=pin,
                totp=totp_key,
                phone_no=phone_no,
                refresh_token=refresh_token,
                access_token=access_token,
            )

    @staticmethod
    def market_date_range(
        start_time="09:15:00",
        end_time=None,
        date=None,
    ) -> tuple[str, str]:
        """Return IST date-time strings accepted by BrokerUtility's FYERS utility."""
        market_date = date or dt.datetime.now(IST).date()
        end_time = end_time or dt.datetime.now(IST).strftime("%H:%M:%S")
        return (
            f"{market_date.isoformat()} {start_time}",
            f"{market_date.isoformat()} {end_time}",
        )

    def fetch_market_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1minute",
        exchange: str = "NSE",
        market_type: str = "EQ",
        include_quote: bool = True,
    ) -> tuple[list[dict], dict]:
        """Fetch FYERS candles plus optional quote metadata for one symbol."""
        frame = self.utility.fetchOHLC(
            ticker=symbol,
            str_from_date=start_date,
            str_to_date=end_date,
            interval=interval,
            all_data=True,
            exchange=exchange,
            market_type=market_type,
        )
        candles = self._frame_to_candles(frame)
        self._attach_vwap(candles)
        history_candle_count = len(candles)
        meta = self._meta_from_candles(candles)
        meta["historyCandles"] = history_candle_count

        if include_quote:
            quote_meta = self.fetch_quote_meta(symbol, market_type=market_type)
            meta.update({key: value for key, value in quote_meta.items() if value is not None})
            self._append_quote_candle(candles, meta)
        meta["candlesReturned"] = len(candles)

        return candles, meta

    def fetch_quote_meta(self, symbol: str, market_type: str = "EQ") -> dict:
        """Fetch the latest FYERS quote snapshot and normalize metadata."""
        from datatypes.trade_data import get_quote_request_data

        response = self.utility.get_quotes([get_quote_request_data(symbol, market_type)])
        quote = None
        if response:
            quote = (
                response.get(symbol)
                or response.get(f"{symbol}-{market_type}")
                or next(iter(response.values()))
            )
        if quote is None:
            return {}

        return {
            "regularMarketPrice": self._positive_or_none(getattr(quote, "ltp", None)),
            "regularMarketDayHigh": self._positive_or_none(getattr(quote, "high", None)),
            "regularMarketDayLow": self._positive_or_none(getattr(quote, "low", None)),
            "regularMarketVolume": self._positive_or_none(getattr(quote, "volume", None)),
            "previousClose": self._positive_or_none(getattr(quote, "prev_close", None)),
            "regularMarketOpen": self._positive_or_none(getattr(quote, "open", None)),
            "bid": self._positive_or_none(getattr(quote, "bid", None)),
            "ask": self._positive_or_none(getattr(quote, "ask", None)),
            "spread": self._to_float(getattr(quote, "spread", None)),
            "change": self._to_float(getattr(quote, "change", None)),
            "changePercent": self._to_float(getattr(quote, "change_percent", None)),
            "averageTradedPrice": self._positive_or_none(getattr(quote, "avg_trade_price", None)),
            "lastTradeTime": getattr(quote, "last_trade_time", None),
        }

    @staticmethod
    def _frame_to_candles(frame) -> list[dict]:
        if frame is None or getattr(frame, "empty", False):
            return []

        candles = []
        for _, row in frame.iterrows():
            close_price = FyersMarketDataAdapter._to_float(row.get("close"))
            if close_price is None:
                continue
            candles.append(
                {
                    "timestamp": row.get("date"),
                    "price": close_price,
                    "open": FyersMarketDataAdapter._to_float(row.get("open"), close_price),
                    "high": FyersMarketDataAdapter._to_float(row.get("high"), close_price),
                    "low": FyersMarketDataAdapter._to_float(row.get("low"), close_price),
                    "volume": FyersMarketDataAdapter._to_float(row.get("volume"), 0.0),
                }
            )
        return candles

    @staticmethod
    def _attach_vwap(candles: list[dict]) -> None:
        cumulative_tp_volume = 0.0
        cumulative_volume = 0.0
        for candle in candles:
            high = candle.get("high")
            low = candle.get("low")
            close = candle.get("price")
            volume = candle.get("volume") or 0.0
            if high is None or low is None or close is None or volume <= 0:
                candle["vwap"] = None
                continue
            typical_price = (high + low + close) / 3.0
            cumulative_tp_volume += typical_price * volume
            cumulative_volume += volume
            candle["vwap"] = round(cumulative_tp_volume / cumulative_volume, 4) if cumulative_volume else None

    @staticmethod
    def _meta_from_candles(candles: list[dict]) -> dict:
        if not candles:
            return {}
        latest = candles[-1]
        highs = [c["high"] for c in candles if c.get("high") is not None]
        lows = [c["low"] for c in candles if c.get("low") is not None]
        volumes = [c.get("volume") or 0 for c in candles]
        return {
            "regularMarketPrice": latest.get("price"),
            "regularMarketDayHigh": max(highs) if highs else latest.get("price"),
            "regularMarketDayLow": min(lows) if lows else latest.get("price"),
            "regularMarketVolume": volumes[-1] if volumes else 0,
            "previousClose": candles[0].get("open"),
            "averageTradedPrice": latest.get("vwap"),
        }

    @staticmethod
    def _append_quote_candle(candles: list[dict], meta: dict) -> None:
        live_price = meta.get("regularMarketPrice")
        if live_price is None:
            return
        if candles and candles[-1].get("price") == live_price:
            return
        candles.append(
            {
                "timestamp": dt.datetime.now(IST),
                "price": live_price,
                "open": meta.get("regularMarketOpen", live_price),
                "high": meta.get("regularMarketDayHigh", live_price),
                "low": meta.get("regularMarketDayLow", live_price),
                "volume": meta.get("regularMarketVolume", 0),
                "vwap": meta.get("averageTradedPrice"),
            }
        )

    @staticmethod
    def _to_float(value, default=None):
        try:
            if value is None or value == "":
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _positive_or_none(value):
        number = FyersMarketDataAdapter._to_float(value)
        return number if number is not None and number >= 0 else None
