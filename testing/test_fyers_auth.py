import base64
import datetime as dt
import json
import unittest

from broker_platform.fyers.fyers_auth import (
    AUTHENTICATED,
    EXPIRED_BUT_REFRESHED,
    FAILED_NEEDS_REGENERATION,
    verify_fyers_auth,
)


def _jwt(expiry):
    def encode(payload):
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{encode({'alg': 'none'})}.{encode({'exp': int(expiry.timestamp())})}.signature"


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FyersAuthTest(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 6, 21, 9, 0, tzinfo=dt.timezone.utc)
        self.valid_access = _jwt(self.now + dt.timedelta(hours=2))
        self.expired_access = _jwt(self.now - dt.timedelta(minutes=5))
        self.valid_refresh = _jwt(self.now + dt.timedelta(days=5))
        self.expired_refresh = _jwt(self.now - dt.timedelta(minutes=5))

    def test_valid_access_and_refresh_token_is_authenticated(self):
        result = verify_fyers_auth(
            client_id="client",
            secret_key="secret",
            pin="1234",
            access_token=self.valid_access,
            refresh_token=self.valid_refresh,
            now=self.now,
        )

        self.assertEqual(result.status, AUTHENTICATED)
        self.assertFalse(result.refreshed)
        self.assertFalse(result.needs_regeneration)

    def test_expired_access_token_refreshes_with_valid_refresh_token(self):
        refreshed_access = _jwt(self.now + dt.timedelta(hours=2))

        def post(url, json, timeout):
            return _Response({"s": "ok", "access_token": refreshed_access})

        result = verify_fyers_auth(
            client_id="client",
            secret_key="secret",
            pin="1234",
            access_token=self.expired_access,
            refresh_token=self.valid_refresh,
            now=self.now,
            post=post,
        )

        self.assertEqual(result.status, EXPIRED_BUT_REFRESHED)
        self.assertEqual(result.access_token, refreshed_access)
        self.assertTrue(result.refreshed)
        self.assertFalse(result.needs_regeneration)

    def test_expired_refresh_token_requests_regeneration(self):
        result = verify_fyers_auth(
            client_id="client",
            secret_key="secret",
            pin="1234",
            access_token=self.expired_access,
            refresh_token=self.expired_refresh,
            now=self.now,
        )

        self.assertEqual(result.status, FAILED_NEEDS_REGENERATION)
        self.assertTrue(result.needs_regeneration)
        self.assertTrue(result.refresh_token_expired)


if __name__ == "__main__":
    unittest.main()
