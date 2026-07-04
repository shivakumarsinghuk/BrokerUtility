# -*- coding: utf-8 -*-
"""
Zerodha Kite Connect - Historical Data

"""

import logging
import os

#cwd = os.chdir("C:/1Ravee/PythonAlgo/src")
#defines
TRADE_START_MIN = 15
FIFTY_NINE_MIN = 59
SIXTY_MIN = 60

#logics
LOGIC_REVERSE_CANDLE = "reversecandle"
LOGIC_VWAP_HFOUR = "vwaph4"
LOGIC_BANK_NIFTY_CAMARILLA = "banknifty_camarilla"
LOGIC_BANK_NIFTY_ORB = "banknifty_orb"

#Define
DATE_TIME = "date"
OPEN_PRICE = "open"
CLOSE_PRICE = "close"
HIGH_PRICE = "high"
LOW_PRICE = "low"
VOLUME_DATA = "volume"
CANDLE_TYPE = "candle_type"
SUPER_TREND_SIGNAL = "signal"
VWAP = "vwap"
SSBOE = "ssboe"
RSI = "rsi"
SL_SUPER_TREND_UP = "SL_SuperTrendUp"
SL_SUPER_TREND_DOWN = "SL_SuperTrendDown"
SUCCESS = 'SUCCESS'
FAILED = 'FAILED'

#Order status define
ORDER_STATUS_PENDING = "PENDING"
ORDER_STATUS_CANCELED = "CANCELED"
ORDER_STATUS_OPEN = "OPEN"
ORDER_STATUS_REJECTED = "REJECTED"
ORDER_STATUS_COMPLETE = "COMPLETE"
ORDER_STATUS_TRIGGER_PENDING = "TRIGGER_PENDING"
ORDER_STATUS_INVALID_STATUS_TYPE = "INVALID"

#symbol type
SYMBOL_TYPE_STOCK = "Stock"
SYMBOL_TYPE_OPTION = "Option"
SYMBOL_TYPE_INDEX = "Index"

#Lot sizes
LOT_SIZE_BANK_NIFTY = 15