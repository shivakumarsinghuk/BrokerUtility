# BrokerUtility

BrokerUtility is a broker abstraction repository used by AI-Trading as a Git submodule. It contains utility classes for FYERS, Zebu/Mynt, and Zerodha Kite. For the AI-Trading integration, the read-only FYERS market-data path is now the primary path.

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
│   │   ├── ai_trading_market_data.py
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
    ├── test_ai_trading_market_data.py
    ├── test_fyers_ai_trading_market_data.py
    └── test_fyers_utility_quotes.py
```

## Credential Handling

BrokerUtility does not own or store live credentials for AI-Trading. The caller
passes credentials into `fyers_utitlity` or `FyersMarketDataAdapter`.

In AI-Trading, credentials are stored in the parent repo's ignored local file:

```text
config/credentials.json
```

That file is loaded by `config/settings.py`, and the resolved values are passed
into BrokerUtility at runtime. Keep real app secrets, TOTP keys, PINs, access
tokens, and refresh tokens outside version control.

## File-By-File Analysis

### `broker_platform/fyers/fyers_utility.py`

Primary FYERS broker utility.

What it does:

- Imports `fyers_apiv3.fyersModel`.
- Builds a FYERS access token through either an existing access token, a refresh token, or the manual authorization-code flow.
- Creates a `FyersModel` client.
- Fetches historical candles through `fyers.history()`.
- Fetches quotes through `fyers.quotes()`.
- Fetches option-chain data through `fyers.optionchain()`.
- Contains order APIs for place, modify, cancel, order book, and order status.
- Converts FYERS quote responses into the shared `quote_data` type.

Important market-data methods:

- `fetchOHLC(ticker, str_from_date, str_to_date, interval, all_data=False, exchange="NSE", market_type="EQ")`
- `fetchCandleMultipleStocks(lst_stocks, str_from_date, str_to_date, interval, ...)`
- `get_quotes(p_lst_stocks)`
- `getOptionChain(symbol, exchange="NSE")`

FYERS History request shape:

```python
fyers.history({
    "symbol": "NSE:RPOWER-EQ",
    "resolution": "1",
    "date_format": "1",
    "range_from": "YYYY-MM-DD",
    "range_to": "YYYY-MM-DD",
    "cont_flag": "1",
})
```

FYERS History response is converted into:

```text
date, open, high, low, close, volume
```

FYERS Quotes request shape:

```python
fyers.quotes({
    "symbols": "NSE:RPOWER-EQ"
})
```

Quote fields captured when present:

```text
lp                -> ltp
open_price        -> open
high_price        -> high
low_price         -> low
prev_close_price  -> previous close
volume            -> volume
bid               -> bid
ask               -> ask
ch                -> change
chp               -> change percent
spread            -> spread
atp/vwap          -> average traded price
tt                -> last trade time
```

### `broker_platform/fyers/ai_trading_market_data.py`

AI-Trading FYERS adapter.

What it does:

- Keeps AI-Trading independent from raw FYERS field names.
- Creates `fyers_utitlity` when a real utility object is not injected.
- Converts FYERS History candles into AI-Trading candle dictionaries.
- Calculates VWAP locally from OHLCV because the History API returns OHLCV candles, not every derived indicator.
- Converts FYERS Quotes snapshots into metadata keys compatible with AI-Trading.
- Appends the latest quote as a live candle when quote LTP is fresher than the last completed candle.

AI-Trading candle format produced:

```python
{
    "timestamp": "2026-06-04 09:15:00",
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
    "bid": 103.95,
    "ask": 104.05,
    "spread": 0.10,
    "change": 5.5,
    "changePercent": 5.58,
    "averageTradedPrice": 102.5,
    "lastTradeTime": 1780557300,
}
```

### `broker_platform/fyers/__init__.py`

Exports the FYERS utility and AI-Trading market-data adapter. The utility import is guarded so adapter tests can run without `fyers-apiv3` installed.

### `broker_platform/zebu/zebumynt_utility.py`

Zebu/Mynt broker utility.

It can log in to Mynt, fetch time-price-series candles, fetch quotes, and call order APIs. AI-Trading no longer uses this path, but it remains available for other submodule consumers.

### `broker_platform/zebu/ai_trading_market_data.py`

Legacy AI-Trading Zebu adapter. It remains in the submodule for compatibility, but AI-Trading now uses the FYERS adapter.

### `broker_platform/kite/kite_utility.py`

Zerodha Kite utility.

It logs in through Kite Connect, fetches historical candles and quotes, and contains order APIs. AI-Trading does not use this connector.

### `broker_platform/__init__.py`

Package marker for broker platform modules.

### `broker_platform/zebu/__init__.py`

Exports the Zebu utility and legacy Zebu AI-Trading adapter.

### `broker_platform/kite/__init__.py`

Exports the Kite utility.

### `datatypes/defines.py`

Shared constants used by broker utilities, including OHLC column names, indicator names, success/failure labels, order status labels, symbol type labels, and lot-size constants.

### `datatypes/login_types.py`

Defines `LogInData`, a simple credential container used by `pal/utility_manager.py`.

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

For AI-Trading, `quote_data` and `get_quote_request_data` are the important classes because they carry FYERS quote responses into a stable internal shape.

### `datatypes/__init__.py`

Exports login types, constants, and trade data classes.

### `pal/utility_manager.py`

Factory/registry for broker utility objects.

What it does:

- Accepts a `LogInData` object.
- Chooses a broker-specific factory based on `broker`.
- Creates and caches a utility object for each user id.
- Supports `fyers`, `zerodha`, and `zebumynt`.

Broker-specific imports are lazy so one broker path does not require every broker dependency to be installed.

### `pal/__init__.py`

Exports `utility_manager`.

### `testing/test.py`

Manual example script showing how to create `LogInData` for Zebu, Fyers, and Zerodha.

### `testing/test_fyers_ai_trading_market_data.py`

Unit test for the AI-Trading FYERS adapter using fake utility responses.

### `testing/test_fyers_utility_quotes.py`

Unit test for FYERS v3 quote payload mapping into the shared `quote_data` type.

### `testing/test_ai_trading_market_data.py`

Legacy unit test for the AI-Trading Zebu adapter using fake utility responses.

### `.gitkeep` Files

Placeholder files that keep otherwise empty directories in version control.

## Testing

Run the FYERS-focused automated tests from the BrokerUtility directory:

```bash
python3 -m unittest testing.test_fyers_ai_trading_market_data testing.test_fyers_utility_quotes
```

`testing/test.py` is a manual/example script and is not part of the automated
test command.

### `.gitignore`

Ignores generated Python cache files such as `__pycache__/` and `*.pyc`.

## Is FYERS An Alternative Market Data Source?

Yes. FYERS is now the primary source for AI-Trading market data.

It provides:

- Historical/intraday OHLCV candles through the History API.
- Real-time quote snapshots through the Quotes API.
- Market depth and option-chain endpoints in the broader FYERS API surface, though AI-Trading currently uses only History and Quotes.

AI-Trading uses it as a polling feed:

1. Poll FYERS at the configured interval.
2. Fetch today's 1-minute OHLCV candles.
3. Fetch the latest quote snapshot.
4. Calculate missing analytics such as VWAP from OHLCV.
5. Convert both sources into AI-Trading's common candle and metadata format.
6. Pass normalized data into the existing signal and Claude analysis pipeline.

## Running The Adapter Tests

From inside this submodule:

```bash
python3 -m unittest testing.test_fyers_ai_trading_market_data testing.test_fyers_utility_quotes
```

The tests use fake utility objects and do not log in to FYERS.
