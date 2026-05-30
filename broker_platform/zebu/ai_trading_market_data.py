# -*- coding: utf-8 -*-
"""
Read-only Zebu market-data adapter for AI-Trading.

The core ``zebumynt_utitlity`` class exposes broker-shaped methods and raw Mynt
field names. This adapter keeps that class unchanged for existing callers while
returning the candle and metadata format expected by AI-Trading.
"""

import datetime as dt
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


class ZebuMarketDataAdapter:
    """Convert Zebu/Mynt OHLC and quote responses into AI-Trading data shapes."""

    def __init__(
        self,
        user_id="",
        password="",
        api_secret_key="",
        phone_no="",
        totp_key="",
        utility=None,
    ):
        self.utility = utility
        if self.utility is None:
            from broker_platform.zebu.zebumynt_utility import zebumynt_utitlity

            self.utility = zebumynt_utitlity(
                user_name=user_id,
                client_id="",
                secret_id=api_secret_key,
                pin=password,
                totp=totp_key,
                phone_no=phone_no,
            )

    @staticmethod
    def market_epoch_range(
        start_time="09:15:00",
        end_time=None,
        date=None,
    ) -> tuple[str, str]:
        """Return IST epoch-second strings accepted by Zebu's time-price API."""
        market_date = date or dt.datetime.now(IST).date()
        end_time = end_time or dt.datetime.now(IST).strftime("%H:%M:%S")

        start_dt = dt.datetime.strptime(
            f"{market_date.isoformat()} {start_time}", "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=IST)
        end_dt = dt.datetime.strptime(
            f"{market_date.isoformat()} {end_time}", "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=IST)
        return str(int(start_dt.timestamp())), str(int(end_dt.timestamp()))

    def fetch_market_data(
        self,
        symbol: str,
        start_epoch: str,
        end_epoch: str,
        interval: str = "1minute",
        exchange: str = "NSE",
        market_type: str = "EQ",
        include_quote: bool = True,
    ) -> tuple[list[dict], dict]:
        """Fetch candles plus optional quote metadata for one symbol."""
        frame = self.utility.fetchOHLC(
            ticker=symbol,
            str_from_date=start_epoch,
            str_to_date=end_epoch,
            interval=interval,
            all_data=True,
            exchange=exchange,
            market_type=market_type,
        )
        candles = self._frame_to_candles(frame)
        meta = self._meta_from_candles(candles)

        if include_quote:
            quote_meta = self.fetch_quote_meta(symbol, exchange=exchange, market_type=market_type)
            meta.update({key: value for key, value in quote_meta.items() if value is not None})
            self._append_quote_candle(candles, meta)

        return candles, meta

    def fetch_quote_meta(self, symbol: str, exchange: str = "NSE", market_type: str = "EQ") -> dict:
        """Fetch the latest quote snapshot and convert it to yFinance-like metadata."""
        from datatypes.trade_data import get_quote_request_data

        response = self.utility.get_quotes(
            [get_quote_request_data(symbol, market_type)],
            p_exchange=exchange,
        )
        quote = response.get(symbol) if response else None
        if quote is None:
            return {}

        return {
            "regularMarketPrice": self._positive_or_none(getattr(quote, "ltp", None)),
            "regularMarketDayHigh": self._positive_or_none(getattr(quote, "high", None)),
            "regularMarketDayLow": self._positive_or_none(getattr(quote, "low", None)),
            "regularMarketVolume": self._positive_or_none(getattr(quote, "volume", None)),
            "previousClose": self._positive_or_none(getattr(quote, "prev_close", None)),
            "regularMarketOpen": self._positive_or_none(getattr(quote, "open", None)),
        }

    @staticmethod
    def _frame_to_candles(frame) -> list[dict]:
        if frame is None or getattr(frame, "empty", False):
            return []

        candles = []
        for _, row in frame.iterrows():
            close_price = ZebuMarketDataAdapter._to_float(row.get("close"))
            if close_price is None:
                continue
            candles.append(
                {
                    "timestamp": row.get("date"),
                    "price": close_price,
                    "open": ZebuMarketDataAdapter._to_float(row.get("open"), close_price),
                    "high": ZebuMarketDataAdapter._to_float(row.get("high"), close_price),
                    "low": ZebuMarketDataAdapter._to_float(row.get("low"), close_price),
                    "volume": ZebuMarketDataAdapter._to_float(row.get("volume"), 0.0),
                    "vwap": ZebuMarketDataAdapter._to_float(row.get("vwap")),
                }
            )
        return candles

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
        number = ZebuMarketDataAdapter._to_float(value)
        return number if number is not None and number >= 0 else None
