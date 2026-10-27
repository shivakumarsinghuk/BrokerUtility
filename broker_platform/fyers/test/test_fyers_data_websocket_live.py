# -*- coding: utf-8 -*-
"""Optional live-market smoke test for the FYERS data socket.

Run during NSE market hours with the same YAML credential keys used by the
other FYERS test scripts:
    python -m BrokerUtility.broker_platform.fyers.test.test_fyers_data_websocket_live \
        --config <path.yml> --symbol NSE:SBIN-EQ --duration 30
"""

import argparse
import time

import yaml

from BrokerUtility.broker_platform.fyers.fyers_utility import fyers_utitlity


def main():
    parser = argparse.ArgumentParser(description="Smoke-test the FYERS data WebSocket")
    parser.add_argument("--config", required=True, help="YAML file with Fyers credentials")
    parser.add_argument("--symbol", default="NSE:SBIN-EQ", help="Complete FYERS symbol")
    parser.add_argument("--duration", type=int, default=30,
                        help="Seconds to wait for a live tick")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}
    required_keys = ("user_name", "client_id", "secret_id", "pin", "totp", "phone_no")
    missing = [key for key in required_keys if not config.get(key)]
    if missing:
        parser.error(f"missing {', '.join(missing)} in {args.config}")

    broker = fyers_utitlity(
        user_name=config["user_name"],
        client_id=config["client_id"],
        secret_id=config["secret_id"],
        pin=config["pin"],
        totp=config["totp"],
        phone_no=config["phone_no"],
    )
    if not broker.get_running_status():
        raise SystemExit("Fyers login failed; see the output above")

    websocket = broker.get_data_websocket()
    try:
        websocket.subscribe([args.symbol])
        deadline = time.monotonic() + max(args.duration, 1)
        while time.monotonic() < deadline:
            ticks = websocket.get_tick_data()
            if not ticks.empty:
                matching_ticks = ticks.loc[ticks["symbol"] == args.symbol]
                if not matching_ticks.empty:
                    print(matching_ticks.tail(5).to_string(index=False))
                    return
            time.sleep(0.25)
        raise SystemExit(f"No tick received for {args.symbol} within {args.duration} seconds")
    finally:
        websocket.close()


if __name__ == "__main__":
    main()
