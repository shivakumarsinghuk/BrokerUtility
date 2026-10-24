# Run (dry run, nothing is sent) -- credentials come from the yml passed with --config:
#   python -m BrokerUtility.broker_platform.kite.test.test_kite_place_order --config <path.yml> --order_type LIMIT --price 5
# Any credential flag (--user_id, --password...) overrides the yml.
# Place a REAL order: add --confirm
# -*- coding: utf-8 -*-
"""
test_kite_place_order.py

Logs in to Kite (Selenium or manual, via kite_utitlity) and places one order. The symbol is checked
against the Kite instrument list first, so a wrong symbol fails before anything is sent. Without
--confirm it only logs in and prints what it would send.

Kite option symbols: weekly NIFTY26O1322500PE (YY, month code 1-9/O/N/D, DD, strike, CE/PE),
monthly NIFTY26OCT22500PE.
"""
import argparse
import os

import yaml
from kiteconnect.exceptions import PermissionException

from BrokerUtility.broker_platform.kite.kite_utility import kite_utitlity

# command-line flag -> key in the yml (same keys as the kite_utitlity constructor)
CONFIG_KEYS = {"user_id": "user_name", "api_key": "client_id", "api_secret_key": "secret_id",
               "password": "pin", "totp_key": "totp", "phone_no": "phone_no"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Place one Kite order")
    parser.add_argument("--config", type=str, required=True, help="Path to the yml with the Kite credentials")
    parser.add_argument("--user_id", type=str, help="Zerodha user id")
    parser.add_argument("--api_key", type=str, help="Kite Connect API key")
    parser.add_argument("--api_secret_key", type=str, help="Kite Connect API secret")
    parser.add_argument("--password", type=str)
    parser.add_argument("--totp_key", type=str, help="TOTP base32 secret")
    parser.add_argument("--phone_no", type=str, help="Not used by Kite login")
    parser.add_argument("--manual-login", action="store_true",
                        help="Print the Kite login URL and prompt for the redirect URL instead of using Selenium")
    parser.add_argument("--symbol", type=str, default="NIFTY26O1322500PE", help="Kite trading symbol")
    parser.add_argument("--exchange", type=str, default="NFO", choices=["NSE", "NFO", "BSE", "BFO"])
    parser.add_argument("--side", type=str, default="BUY", choices=["BUY", "SELL"])
    parser.add_argument("--quantity", type=int, default=65, help="Must be a multiple of the lot size (NIFTY: 65)")
    parser.add_argument("--order_type", type=str, default="MARKET", choices=["LIMIT", "MARKET"])
    parser.add_argument("--price", type=float, default=0.0, help="Limit price (required for LIMIT)")
    parser.add_argument("--product", type=str, default="MIS", choices=["MIS", "NRML", "CNC"])
    parser.add_argument("--amo", action="store_true", help="Send as an after-market order")
    parser.add_argument("--confirm", action="store_true", help="Actually place the order (default is a dry run)")
    args = parser.parse_args()

    if not os.path.isfile(args.config):
        parser.error(f"config file not found: {args.config}")
    with open(args.config) as f:
        config = yaml.safe_load(f) or {}
    for flag, key in CONFIG_KEYS.items():
        if getattr(args, flag) is None:
            setattr(args, flag, str(config.get(key, "") or ""))
    missing = [flag for flag in ("user_id", "api_key", "api_secret_key", "password", "totp_key")
               if not getattr(args, flag)]
    if missing:
        parser.error(f"missing {', '.join(missing)} -- set them in {args.config} or pass --<name>")

    if args.order_type == "LIMIT" and args.price <= 0:
        parser.error("--price is required for a LIMIT order")

    print("Logging in as:", args.user_id)
    broker = kite_utitlity(user_name=args.user_id,
                           client_id=args.api_key,
                           secret_id=args.api_secret_key,
                           pin=args.password,
                           totp=args.totp_key,
                           phone_no=args.phone_no,
                           manual_login=args.manual_login)
    # the constructor swallows login errors, so check the session was actually created
    if not getattr(broker, "access_token", None):
        raise SystemExit("Kite login failed -- see the output above")
    print("Logged in, profile:", broker.kite.profile().get("user_name"))

    # look the symbol up in the instrument dump -- ltp/quote need the market data add-on, this does not
    instrument = next((i for i in broker.kite.instruments(args.exchange)
                       if i["tradingsymbol"] == args.symbol), None)
    if instrument is None:
        raise SystemExit(f"{args.exchange}:{args.symbol} not found in the Kite instrument list")
    print("Symbol found:", f"{args.exchange}:{args.symbol}", "lot size:", instrument["lot_size"],
          "expiry:", instrument.get("expiry"))
    if args.quantity % instrument["lot_size"]:
        parser.error(f"--quantity {args.quantity} is not a multiple of the lot size {instrument['lot_size']}")
    try:
        ltp = broker.kite.ltp(f"{args.exchange}:{args.symbol}")
        print("ltp:", ltp[f"{args.exchange}:{args.symbol}"]["last_price"])
    except PermissionException:
        print("ltp: not available (API app has no market data subscription)")

    order = dict(tradingsymbol=args.symbol, transaction_type=args.side, quantity=args.quantity,
                 product=args.product, order_type=args.order_type,
                 price=args.price if args.order_type == "LIMIT" else None,
                 exchange=args.exchange, market_type="OPT", amo="Yes" if args.amo else "No")
    if not args.confirm:
        print("DRY RUN -- would place:", order)
        print("Re-run with --confirm to send it.")
        raise SystemExit(0)

    # market_type "OPT": the symbol and exchange are used as-is
    order_id = broker.place_order(**order)
    print("Order id:", order_id or "(none -- order failed, see responses above)")
