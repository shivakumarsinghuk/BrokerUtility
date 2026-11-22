"""List Kite NFO CE/PE contracts for an underlying and expiry.

Example:
    python -m BrokerUtility.broker_platform.kite.test.list_option_contracts \
        --config /path/to/zerodha.yml --expiry 24-NOV-2026 --manual-login
"""
import argparse
from collections import Counter
from datetime import date, datetime
import re

import yaml

from BrokerUtility.broker_platform.kite.kite_utility import kite_utitlity


def parse_expiry(value):
    for date_format in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(value.upper(), date_format).date()
        except ValueError:
            pass
    raise argparse.ArgumentTypeError("expiry must be YYYY-MM-DD or DD-MMM-YYYY")


def normalize_underlying(value):
    underlying = value.upper().split(":")[-1].replace("-INDEX", "").strip()
    return {"NIFTY50": "NIFTY", "NIFTYBANK": "BANKNIFTY"}.get(underlying, underlying)


def extract_option_contracts(instruments, underlying):
    underlying = normalize_underlying(underlying)
    contracts = []
    for instrument in instruments:
        symbol = str(instrument.get("tradingsymbol", ""))
        match = re.search(r"(\d+)(CE|PE)$", symbol)
        if not symbol.startswith(underlying) or not match:
            continue

        expiry_value = instrument.get("expiry")
        try:
            if isinstance(expiry_value, datetime):
                expiry = expiry_value.date()
            elif isinstance(expiry_value, date):
                expiry = expiry_value
            else:
                try:
                    expiry = date.fromisoformat(str(expiry_value)[:10])
                except ValueError:
                    expiry = datetime.strptime(str(expiry_value).upper(), "%d-%b-%Y").date()
            strike = int(float(instrument["strike"]))
        except (KeyError, TypeError, ValueError):
            continue

        contracts.append({
            "symbol": symbol,
            "option_type": match.group(2),
            "strike_price": strike,
            "expiry": expiry,
        })

    return sorted(contracts, key=lambda contract: (
        contract["expiry"], contract["option_type"], contract["strike_price"]))


def load_credentials(path):
    with open(path, encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    if not isinstance(config, dict):
        raise ValueError("YAML config must contain a mapping")

    credentials = {
        "user_name": config.get("user_name", config.get("user_id", "")),
        "client_id": config.get("client_id", config.get("api_key", "")),
        "secret_id": config.get("secret_id", config.get("api_secret_key", "")),
        "pin": config.get("pin", config.get("password", "")),
        "totp": config.get("totp", config.get("totp_key", "")),
        "phone_no": config.get("phone_no", ""),
    }
    missing = [key for key in ("user_name", "client_id", "secret_id", "pin", "totp")
               if not credentials[key]]
    if missing:
        raise ValueError(f"YAML config is missing required fields: {', '.join(missing)}")
    return {key: str(value or "") for key, value in credentials.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description="List Kite NFO CE/PE option contracts")
    parser.add_argument("--config", required=True, help="Path to Kite login YAML")
    parser.add_argument("--underlying", default="NIFTY",
                        help="Underlying symbol (default: NIFTY)")
    parser.add_argument("--expiry", type=parse_expiry,
                        help="Expiry to list (YYYY-MM-DD or DD-MMM-YYYY); defaults to nearest listed expiry")
    parser.add_argument("--manual-login", action="store_true",
                        help="Print Kite login URL and prompt for the redirect URL")
    args = parser.parse_args(argv)

    try:
        credentials = load_credentials(args.config)
    except (OSError, yaml.YAMLError, ValueError) as error:
        parser.error(str(error))

    broker = kite_utitlity(**credentials, manual_login=args.manual_login)
    if not getattr(broker, "access_token", None):
        raise SystemExit("Kite login failed; see the error above")

    underlying = normalize_underlying(args.underlying)
    instruments = broker.kite.instruments("NFO")
    contracts = extract_option_contracts(instruments, underlying)
    if not contracts:
        raise SystemExit(f"No NFO CE/PE contracts found for {underlying}")

    expiry_counts = {}
    for contract in contracts:
        counts = expiry_counts.setdefault(contract["expiry"], Counter())
        counts[contract["option_type"]] += 1
    print(f"Available {underlying} option expiries (CE / PE):")
    for expiry, counts in sorted(expiry_counts.items()):
        print(f"  {expiry.isoformat()}: CE={counts['CE']} PE={counts['PE']}")

    target_expiry = args.expiry
    if target_expiry is None:
        today = datetime.now().date()
        target_expiry = next((expiry for expiry in sorted(expiry_counts) if expiry >= today), None)
    if target_expiry is None:
        raise SystemExit(f"No listed {underlying} option expiry on or after today")

    selected = [contract for contract in contracts if contract["expiry"] == target_expiry]
    print(f"\n{underlying} contracts for {target_expiry.isoformat()}:")
    if not selected:
        print("  No CE/PE contracts listed for this expiry.")
        return 1

    print("  TYPE  STRIKE  SYMBOL")
    for contract in selected:
        print(f"  {contract['option_type']:>2}  {contract['strike_price']:>6}  {contract['symbol']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
