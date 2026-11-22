import unittest
from datetime import date

from BrokerUtility.broker_platform.kite.test.list_option_contracts import (
    extract_option_contracts,
    parse_expiry,
)


class OptionContractListingTests(unittest.TestCase):
    def test_extracts_only_the_requested_underlying_option_contracts(self):
        instruments = [
            {"tradingsymbol": "NIFTY26N2424000CE", "expiry": date(2026, 11, 24), "strike": 24000},
            {"tradingsymbol": "NIFTY26N2424000PE", "expiry": date(2026, 11, 24), "strike": 24000},
            {"tradingsymbol": "BANKNIFTY26N2450000CE", "expiry": date(2026, 11, 24), "strike": 50000},
            {"tradingsymbol": "NIFTY26NOVFUT", "expiry": date(2026, 11, 24), "strike": 0},
        ]

        contracts = extract_option_contracts(instruments, "NIFTY50-INDEX")

        self.assertEqual(
            [(contract["option_type"], contract["strike_price"]) for contract in contracts],
            [("CE", 24000), ("PE", 24000)],
        )

    def test_parses_iso_and_kite_expiry_formats(self):
        self.assertEqual(parse_expiry("2026-11-24"), date(2026, 11, 24))
        self.assertEqual(parse_expiry("24-NOV-2026"), date(2026, 11, 24))


if __name__ == "__main__":
    unittest.main()
