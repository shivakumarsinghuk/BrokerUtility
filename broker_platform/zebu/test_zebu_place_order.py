# Run (dry run, nothing is sent) -- credentials come from zebu_test_config.yml next to this file:
#   python -m BrokerUtility.broker_platform.zebu.test_zebu_place_order --price 5
# Other config file: --config <path.yml>. Any credential flag (--user_id, --password...) overrides it.
# Place a REAL order: add --confirm
# -*- coding: utf-8 -*-
"""
test_zebu_place_order.py

Places one order on Zebu Mynt for a Fyers-style option symbol (default NSE:NIFTY26O0622500PE).
The Fyers symbol is converted to Zebu's NFO format (NIFTY06OCT26P22500) and looked up with
searchscrip first, so a wrong conversion fails before anything is sent. Without --confirm it only
logs in and prints what it would send.
"""
import argparse
import os
import re

import yaml

from BrokerUtility.broker_platform.zebu.zebumynt_utility import zebumynt_utitlity

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
# Fyers weekly expiries code the month as 1-9, O, N, D
WEEKLY_MONTH_CODES = {**{str(m): m for m in range(1, 10)}, "O": 10, "N": 11, "D": 12}
DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zebu_test_config.yml")
# command-line flag -> key in the yml (same keys as IntradayAlgo/UtilityData/zebumynt_*.yml)
CONFIG_KEYS = {"user_id": "user_name", "api_key": "client_id", "api_secret_key": "secret_id",
               "password": "pin", "totp_key": "totp", "phone_no": "phone_no"}


def fyers_weekly_to_zebu(fyers_symbol):
    # NSE:NIFTY26O0622500PE -> NIFTY06OCT26P22500 (underlying, YY, month code, DD, strike, CE/PE)
    match = re.fullmatch(r"(?:NSE:)?([A-Z]+)(\d{2})([1-9OND])(\d{2})(\d+)(CE|PE)", fyers_symbol)
    if not match:
        raise ValueError(f"Not a Fyers weekly option symbol: {fyers_symbol} (pass --zebu_symbol instead)")
    underlying, yy, month_code, dd, strike, option_type = match.groups()
    month = MONTHS[WEEKLY_MONTH_CODES[month_code] - 1]
    return f"{underlying}{dd}{month}{yy}{option_type[0]}{strike}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Place one Zebu Mynt option order")
    parser.add_argument("--config", type=str, default=DEFAULT_CONFIG, help="yml with the Zebu credentials")
    parser.add_argument("--user_id", type=str, help="Zebu client id")
    parser.add_argument("--api_key", type=str, help="Not used by Zebu login")
    parser.add_argument("--api_secret_key", type=str)
    parser.add_argument("--password", type=str)
    parser.add_argument("--totp_key", type=str, help="Zebu twoFA value, sent as-is")
    parser.add_argument("--phone_no", type=str, help="Sent as imei")
    parser.add_argument("--symbol", type=str, default="NSE:NIFTY26O0622500PE", help="Fyers weekly option symbol")
    parser.add_argument("--zebu_symbol", type=str, help="Zebu NFO symbol, overrides the converted --symbol")
    parser.add_argument("--side", type=str, default="BUY", choices=["BUY", "SELL"])
    parser.add_argument("--quantity", type=int, default=65, help="Must be a multiple of the lot size (NIFTY: 65)")
    parser.add_argument("--order_type", type=str, default="MARKET", choices=["LIMIT", "MARKET"])
    parser.add_argument("--price", type=float, default=0.0, help="Limit price (required for LIMIT)")
    parser.add_argument("--product", type=str, default="MIS", choices=["MIS", "CNC"])
    parser.add_argument("--amo", action="store_true", help="Send as an after-market order")
    parser.add_argument("--confirm", action="store_true", help="Actually place the order (default is a dry run)")
    args = parser.parse_args()

    config = {}
    if os.path.exists(args.config):
        with open(args.config) as f:
            config = yaml.safe_load(f) or {}
    elif args.config != DEFAULT_CONFIG:
        parser.error(f"config file not found: {args.config}")
    for flag, key in CONFIG_KEYS.items():
        if getattr(args, flag) is None:
            setattr(args, flag, str(config.get(key, "") or ""))
    missing = [flag for flag in ("user_id", "api_secret_key", "password", "totp_key") if not getattr(args, flag)]
    if missing:
        parser.error(f"missing {', '.join(missing)} -- set them in {args.config} or pass --<name>")

    if args.order_type == "LIMIT" and args.price <= 0:
        parser.error("--price is required for a LIMIT order")

    zebu_symbol = args.zebu_symbol or fyers_weekly_to_zebu(args.symbol)
    print("Fyers symbol:", args.symbol, "-> Zebu symbol:", zebu_symbol)

    print("Logging in as:", args.user_id)
    broker = zebumynt_utitlity(user_name=args.user_id,
                               client_id=args.api_key,
                               secret_id=args.api_secret_key,
                               pin=args.password,
                               totp=args.totp_key,
                               phone_no=args.phone_no)
    print("get_running_status():", broker.get_running_status())

    search = broker.zebumynt.searchscrip(exchange="NFO", searchtext=zebu_symbol)
    found = [v["tsym"] for v in (search or {}).get("values", [])]
    if zebu_symbol not in found:
        raise SystemExit(f"{zebu_symbol} not found on NFO (searchscrip returned {found})")
    print("Symbol found on NFO:", zebu_symbol)

    order = dict(tradingsymbol=zebu_symbol, transaction_type=args.side, quantity=args.quantity,
                 product=args.product, order_type=args.order_type, price=args.price,
                 market_type="OPT", amo="Yes" if args.amo else "No")
    if not args.confirm:
        print("DRY RUN -- would place:", order)
        print("Re-run with --confirm to send it.")
        raise SystemExit(0)

    # market_type "OPT": the symbol is used as-is on NFO
    order_id = broker.place_order(**order)
    print("Order id:", order_id or "(none -- order failed, see responses above)")
