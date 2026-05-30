# BrokerUtility

BrokerUtility is a broker abstraction repository used by AI-Trading as a Git submodule. It contains utility classes for Zebu/Mynt, Zerodha Kite, and Fyers. For the AI-Trading integration, only the read-only Zebu market-data path is used.

## Repository Layout

```text
BrokerUtility/
├── .gitignore
├── README.md
├── broker_platform/
│   ├── __init__.py
│   ├── .gitkeep
│   ├── fyers/
│   │   ├── __init__.py
│   │   ├── .gitkeep
│   │   └── fyers_utility.py
│   ├── kite/
│   │   ├── __init__.py
│   │   ├── .gitkeep
│   │   └── kite_utility.py
│   └── zebu/
│       ├── __init__.py
│       ├── .gitkeep
│       ├── ai_trading_market_data.py
│       └── zebumynt_utility.py
├── datatypes/
│   ├── __init__.py
│   ├── .gitkeep
│   ├── defines.py
│   ├── login_types.py
│   └── trade_data.py
├── pal/
│   ├── __init__.py
│   ├── .gitkeep
│   └── utility_manager.py
└── testing/
    ├── .gitkeep
    ├── test.py
    └── test_ai_trading_market_data.py
```

## File-By-File Analysis

### `broker_platform/zebu/zebumynt_utility.py`

Primary Zebu/Mynt broker utility.

What it does:

- Imports `myntapi.app` and creates a Zebu/Mynt API session.
- Logs in with user id, password, two-factor value, vendor code, API secret, and IMEI/phone identifier.
- Stores known index tokens for `NIFTYBANK-INDEX`, `NIFTY50-INDEX`, and `INDIAVIX-INDEX`.
- Fetches historical or intraday OHLC data through:
  - `get_time_price_series()` for minute intervals.
  - `get_daily_price_series()` for daily intervals.
- Normalizes Mynt OHLC fields into common column names from `datatypes/defines.py`.
- Adds candle color classification through `candle_type`.
- Fetches quote snapshots through `get_quotes()`.
- Converts quote snapshots into `quote_data` objects through `__extract_quote_data()`.
- Contains order APIs for place, modify, cancel, order book, and single-order history.
- Contains helper functions for exchange/token selection and option symbol formatting.

Important market-data methods:

- `fetchOHLC(ticker, str_from_date, str_to_date, interval, all_data=False, exchange="NSE", market_type="EQ")`
- `fetchCandleMultipleStocks(lst_stocks, str_from_date, str_to_date, interval, ...)`
- `get_quote(p_get_quote_req, p_exchange="NSE")`
- `get_quotes(p_lst_get_quote_data_req, p_exchange="NSE")`
- `getTimeFrame(...)`
- `getTimeFrameMultiDays(...)`

Zebu API request/response shape:

- Minute candles call:

```python
self.zebumynt.get_time_price_series(
    exchange="NSE",
    token="RPOWER-EQ",
    starttime="epoch_seconds",
    endtime="epoch_seconds",
    interval=1,
)
```

- Mynt minute candle fields are renamed as:

```text
time    -> date
into    -> open
inth    -> high
intl    -> low
intc    -> close
intv    -> volume
intvwap -> vwap
```

- Quote call:

```python
self.zebumynt.get_quotes(exchange="NSE", token="RPOWER-EQ")
```

- Quote fields are converted approximately as:

```text
o  -> open
h  -> high
l  -> low
c  -> previous close
lp -> last traded price
v  -> volume
```

### `broker_platform/zebu/ai_trading_market_data.py`

AI-Trading adapter added for this integration.

What it does:

- Keeps AI-Trading independent from raw Zebu/Mynt field names.
- Creates `zebumynt_utitlity` lazily when a real utility object is not injected.
- Converts Zebu OHLC DataFrames into AI-Trading candle dictionaries.
- Converts Zebu quote objects into metadata keys compatible with the existing AI-Trading flow.
- Provides `market_epoch_range()` to produce IST epoch seconds for Zebu's time-price API.

AI-Trading candle format produced:

```python
{
    "timestamp": "2026-05-30 09:15:00",
    "price": 101.0,
    "open": 100.0,
    "high": 102.0,
    "low": 99.0,
    "volume": 1000.0,
    "vwap": 100.5,
}
```

AI-Trading metadata format produced:

```python
{
    "regularMarketPrice": 104.0,
    "regularMarketDayHigh": 106.0,
    "regularMarketDayLow": 99.0,
    "regularMarketVolume": 12000.0,
    "previousClose": 98.5,
    "regularMarketOpen": 100.0,
}
```

### `broker_platform/kite/kite_utility.py`

Zerodha Kite utility.

What it does:

- Logs in using Kite Connect, Selenium, and TOTP.
- Downloads NSE instruments.
- Fetches historical candles through Kite's `historical_data()`.
- Fetches quotes through Kite's `quote()`.
- Places, modifies, and cancels orders.
- Converts Kite response objects into local `order_data`, `order_info`, and `quote_data` types.

AI-Trading no longer uses this connector directly. It remains in BrokerUtility for other consumers of the submodule.

### `broker_platform/fyers/fyers_utility.py`

Fyers utility.

What it does:

- Generates Fyers access tokens.
- Fetches historical candles through `fyers.history()`.
- Fetches quotes through `fyers.quotes()`.
- Places, modifies, and cancels orders.
- Fetches option-chain data.
- Converts Fyers response fields into common local data classes.

AI-Trading does not use this connector.

### `broker_platform/__init__.py`

Package marker for broker platform modules.

### `broker_platform/zebu/__init__.py`

Exports the Zebu utility and AI-Trading market-data adapter.

### `broker_platform/kite/__init__.py`

Exports the Kite utility.

### `broker_platform/fyers/__init__.py`

Exports the Fyers utility.

### `datatypes/defines.py`

Shared constants used by broker utilities.

Includes:

- Time and OHLC column names.
- Indicator column names.
- Success/failure labels.
- Order status labels.
- Symbol type labels.
- Lot-size constants.

### `datatypes/login_types.py`

Defines `LogInData`, a simple credential container used by `pal/utility_manager.py`.

Fields:

- `broker`
- `user_id`
- `password`
- `api_key`
- `api_secret_key`
- `phone_no`
- `totp_key`

### `datatypes/trade_data.py`

Defines shared data containers.

Important classes:

- `trade_data`
- `order_info`
- `order_data`
- `logic_data`
- `cpr_data`
- `pivot_points_data`
- `exit_data`
- `quote_data`
- `trade_details`
- `get_quote_request_data`
- `option_expiry_data`
- `option_wall_data`
- `greek_data`
- `option_chain_data`

For AI-Trading, `quote_data` and `get_quote_request_data` are the important classes because they carry Zebu quote responses into a stable internal shape.

### `datatypes/__init__.py`

Exports login types, constants, and trade data classes.

### `pal/utility_manager.py`

Factory/registry for broker utility objects.

What it does:

- Accepts a `LogInData` object.
- Chooses a broker-specific factory based on `broker`.
- Creates and caches a utility object for each user id.
- Supports `fyers`, `zerodha`, and `zebumynt`.

The broker-specific imports are lazy so using Zebu does not require Kite or Fyers dependencies to be installed.

### `pal/__init__.py`

Exports `utility_manager`.

### `testing/test.py`

Manual example script showing how to create `LogInData` for Zebu, Fyers, and Zerodha.

### `testing/test_ai_trading_market_data.py`

Unit test for the AI-Trading Zebu adapter using fake utility responses.

### `.gitkeep` Files

Placeholder files that keep otherwise empty directories in version control.

### `.gitignore`

Ignores generated Python cache files such as `__pycache__/` and `*.pyc`.

## Is Zebu An Alternative Market Data Source?

Yes. The Zebu/Mynt utility provides an authenticated alternative to Yahoo Finance and Kite Connect for market data.

It is not currently implemented as a streaming WebSocket in this repository. Instead, it provides:

- Intraday OHLC candles through Mynt time-price-series APIs.
- Daily candles through Mynt daily-price-series APIs.
- Live quote snapshots through Mynt quote APIs.

AI-Trading uses it as a polling feed:

1. Poll Zebu at the configured interval.
2. Fetch today's 1-minute candles.
3. Fetch the latest quote snapshot.
4. Convert both into AI-Trading's common candle and metadata format.
5. Pass the normalized data into the existing signal and Claude analysis pipeline.

## Running The Adapter Tests

From inside this submodule:

```bash
python3 -m unittest testing.test_ai_trading_market_data
```

The test uses fake utility objects and does not log in to Zebu.
