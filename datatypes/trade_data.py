# -*- coding: utf-8 -*-
"""
Zerodha Kite Connect - Historical Data

"""
import time
from dataclasses import dataclass, field

#defines
DEFINE_NOT_TRADED = "Not Traded"
DEFINE_TRADE_OPEN = "Open"
DEFINE_TRADE_COMPLETE = "Complete"
DEFINE_TRADE_TYPE_BUY = "Buy"
DEFINE_TRADE_TYPE_SELL = "Sell"

@dataclass
class trade_data:
    stock: str = ""
    transaction_type: str = ""
    entry_price: float = 0.0
    stop_loss_price: float = 0.0
    target_price: float = 0.0
    start_time: str = ""
    end_time: str = ""

    def __str__(self):
        return ("Stock: " + self.stock + "\ntransaction_type: " + self.transaction_type + "\nEntry Price: " + str(self.entry_price) + "\nSL Price: " + str(self.stop_loss_price) + "\nTarget Price: " + str(self.target_price))

@dataclass
class order_info:
    stock: str = ""
    transaction_type: str = ""
    price: float = 0.0
    status: str = ""
    variety: str = ""

@dataclass
class order_data:
    stock: str = ""
    status: str = ""
    price: float = 0.0
    quantity: int = 0
    trans_type: str = ""
    order_no: str = ""

@dataclass
class logic_data:
    max_loss: float = 0.0
    max_stop_loss: float = 0.0

@dataclass
class cpr_data:
    top: float = 0.0
    pivot: float = 0.0
    bottom: float = 0.0

@dataclass
class pivot_points_data:
    rvalues: []
    svalues: []
    pivot: float = 0.0

@dataclass
class exit_data:
    target: float = 0.0
    stoploss: float = 0.0
    max_stoploss_perc: float = 0.0
    st_period: int = 0
    st_multiplier: int = 0

@dataclass
class quote_data():
    ask: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    prev_close: float = 0.0
    ltp: float = 0.0
    volume: int = 0

    def __init__(self, p_ask=0.0, p_open=0.0, p_high=0.0, p_low=0.0, p_prev_close=0.0, p_ltp=0.0, p_volume=0.0):
        self.ask = p_ask
        self.open = p_open
        self.high = p_high
        self.low = p_low
        self.prev_close = p_prev_close
        self.ltp = p_ltp
        self.volume = p_volume

@dataclass
class trade_details():
    entry_time: str = ""
    exit_time: str = ""
    exit_type: str = ""
    profit_loss_value: float = ""

    def __init__(self, p_entry_time, p_exit_time, \
                       p_exit_type, p_profit_loss_value, \
                       p_day_open = 0.0, p_day_high = 0.0, \
                       p_day_low = 0.0, p_day_close = 0.0):
        self.entry_time = p_entry_time
        self.exit_time = p_exit_time
        self.exit_type = p_exit_type
        self.profit_loss_value = p_profit_loss_value
        self.day_open = p_day_open
        self.day_high = p_day_high
        self.day_low = p_day_low
        self.day_close = p_day_close

@dataclass
class get_quote_request_data():
    symbol: str = ""
    market_type: str = ""

    def __init__(self, p_symbol, p_market_type=""):
        self.symbol = p_symbol
        self.market_type = p_market_type

class pivot_point_data():
    r1values = [0.0,0.0,0.0,0.0,0.0,0.0]
    s1values = [0.0,0.0,0.0,0.0,0.0,0.0]
    pivot: float = 0.0

class option_expiry_data:
    def __init__(self, p_current_expiry_data, p_next_week_expiry_date, p_monthly_expiry_data, \
                 p_is_current_week_monthly_expiry, p_is_next_week_monthly_expiry):
        self.current_expiry_data = p_current_expiry_data
        self.next_week_expiry_date = p_next_week_expiry_date
        self.monthly_expiry_data = p_monthly_expiry_data
        self.is_current_week_monthly_expiry = p_is_current_week_monthly_expiry
        self.is_next_week_monthly_expiry = p_is_next_week_monthly_expiry

@dataclass
class option_wall_data():
    strike_price: int = 0
    oi: float = 0.0

@dataclass
class greek_data:
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    iv: float = 0.0

@dataclass
class option_chain_data:
    date_time: str = ""
    atm_strike: int = 0
    atm_straddle_price: float = 0.0
    pcr: float = 0.0
    max_pain: float = 0.0
    put_wall_data: option_wall_data = field(default_factory=option_wall_data)
    call_wall_data: option_wall_data = field(default_factory=option_wall_data)
    put_greeks: greek_data = field(default_factory=greek_data)
    call_greeks: greek_data = field(default_factory=greek_data)