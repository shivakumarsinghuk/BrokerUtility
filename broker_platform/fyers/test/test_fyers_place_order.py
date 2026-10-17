# Run (dry run, nothing is sent):
#   python -m BrokerUtility.broker_platform.fyers.test.test_fyers_place_order --config <path.yml>
# Place a REAL order: add --confirm
# -*- coding: utf-8 -*-
"""Log in to Fyers and exercise fyers_utitlity.place_order."""
import argparse
import os

import yaml

from BrokerUtility.broker_platform.fyers.fyers_utility import fyers_utitlity

CONFIG_KEYS = {
    "user_id": "user_name",
    "api_key": "client_id",
    "api_secret_key": "secret_id",
    "password": "pin",
    "totp_key": "totp",
    "phone_no": "phone_no",
}


def main():
    parser = argparse.ArgumentParser(description="Place one Fyers order")
    parser.add_argument("--config", required=True, help="YAML file with Fyers credentials")
    parser.add_argument("--user_id", help="Fyers user name")
    parser.add_argument("--api_key", help="Fyers app/client ID")
    parser.add_argument("--api_secret_key", help="Fyers app secret")
    parser.add_argument("--password", help="Fyers PIN")
    parser.add_argument("--totp_key", help="Fyers TOTP secret")
    parser.add_argument("--phone_no", help="Phone number used for Fyers login")
    parser.add_argument("--symbol", required=True, help="Complete Fyers trading symbol")
    parser.add_argument("--exchange", default="NSE", help="Exchange prefix, e.g. NSE or NFO")
    parser.add_argument("--side", default="BUY", choices=["BUY", "SELL"])
    parser.add_argument("--quantity", type=int, required=True)
    parser.add_argument("--order_type", default="MARKET", choices=["LIMIT", "MARKET", "SL", "SL-M"])
    parser.add_argument("--price", type=float, default=0.0, help="Limit price; required for LIMIT")
    parser.add_argument("--product", default="MIS", choices=["MIS", "NRML", "CO", "BO"])
    parser.add_argument(
        "--market_type",
        default="",
        help="Suffix for simple symbols (default empty for complete option/future symbols; use EQ for equities)",
    )
    parser.add_argument("--amo", action="store_true", help="Place as an after-market order")
    parser.add_argument("--confirm", action="store_true", help="Actually send the order (default is dry run)")
    args = parser.parse_args()

    if not os.path.isfile(args.config):
        parser.error(f"config file not found: {args.config}")
    with open(args.config, encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}
    for flag, key in CONFIG_KEYS.items():
        if getattr(args, flag) is None:
            setattr(args, flag, str(config.get(key, "") or ""))

    required_credentials = ("user_id", "api_key", "api_secret_key", "password", "totp_key", "phone_no")
    missing = [flag for flag in required_credentials if not getattr(args, flag)]
    if missing:
        parser.error(f"missing {', '.join(missing)}; set them in {args.config} or pass the matching option")
    if args.quantity <= 0:
        parser.error("--quantity must be greater than zero")
    if args.order_type == "LIMIT" and args.price <= 0:
        parser.error("--price must be greater than zero for a LIMIT order")

    print("Logging in as:", args.user_id)
    broker = fyers_utitlity(
        user_name=args.user_id,
        client_id=args.api_key,
        secret_id=args.api_secret_key,
        pin=args.password,
        totp=args.totp_key,
        phone_no=args.phone_no,
    )
    if not broker.get_running_status():
        raise SystemExit("Fyers login failed; see the output above")

    order = {
        "tradingsymbol": args.symbol,
        "transaction_type": args.side,
        "quantity": args.quantity,
        "product": args.product,
        "order_type": args.order_type,
        "price": args.price if args.order_type == "LIMIT" else 0,
        "exchange": args.exchange,
        "market_type": args.market_type,
        "amo": "Yes" if args.amo else "No",
    }
    if not args.confirm:
        print("DRY RUN -- would place:", order)
        print("Re-run with --confirm to send it.")
        return

    order_id = broker.place_order(**order)
    print("Order id:", order_id or "(none -- order failed, see responses above)")


if __name__ == "__main__":
    main()
