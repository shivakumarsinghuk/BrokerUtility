# -*- coding: utf-8 -*-
"""FYERS token verification and refresh helpers."""

import base64
import datetime as dt
import hashlib
import json
from dataclasses import dataclass

import requests


AUTHENTICATED = "authenticated"
EXPIRED_BUT_REFRESHED = "expired-but-refreshed"
FAILED_NEEDS_REGENERATION = "failed-needs-regeneration"
FYERS_REFRESH_URL = "https://api-t1.fyers.in/api/v3/validate-refresh-token"


@dataclass
class FyersAuthResult:
    status: str
    message: str
    access_token: str = ""
    refreshed: bool = False
    needs_regeneration: bool = False
    access_token_expired: bool = False
    refresh_token_expired: bool = False


def token_expiry(token):
    """Return the JWT expiry timestamp, or None when the token is unusable."""
    if not token or not isinstance(token, str) or token.startswith("YOUR_"):
        return None
    try:
        payload_part = token.split(".")[1]
        payload_part += "=" * (-len(payload_part) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_part))
        return dt.datetime.fromtimestamp(int(payload["exp"]), dt.timezone.utc)
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def is_token_expired(token, now=None, skew_seconds=60):
    expiry = token_expiry(token)
    if expiry is None:
        return True
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    return expiry <= now.astimezone(dt.timezone.utc) + dt.timedelta(seconds=skew_seconds)


def refresh_access_token(client_id, secret_key, pin, refresh_token, post=None):
    if not all([client_id, secret_key, pin, refresh_token]):
        raise RuntimeError("FYERS refresh requires client_id, secret_key, pin, and refresh_token.")

    hash_val = hashlib.sha256(f"{client_id}:{secret_key}".encode())
    data = {
        "grant_type": "refresh_token",
        "appIdHash": hash_val.hexdigest(),
        "refresh_token": refresh_token,
        "pin": str(pin),
    }
    post = post or requests.post
    response = post(FYERS_REFRESH_URL, json=data, timeout=15)
    response_data = response.json()
    if response_data.get("s") == "ok" and response_data.get("access_token"):
        return response_data["access_token"]

    message = response_data.get("message", "refresh token validation failed")
    code = response_data.get("code", "unknown")
    raise RuntimeError(f"FYERS refresh-token authentication failed: {code} - {message}")


def verify_fyers_auth(client_id, secret_key, pin, access_token, refresh_token, now=None, post=None):
    access_expired = is_token_expired(access_token, now=now)
    refresh_expired = is_token_expired(refresh_token, now=now)

    if refresh_expired:
        return FyersAuthResult(
            status=FAILED_NEEDS_REGENERATION,
            message="FYERS refresh token is missing, invalid, or expired.",
            needs_regeneration=True,
            access_token_expired=access_expired,
            refresh_token_expired=True,
        )

    if not access_expired:
        return FyersAuthResult(
            status=AUTHENTICATED,
            message="FYERS access and refresh tokens are valid.",
            access_token=access_token,
        )

    try:
        refreshed_access_token = refresh_access_token(
            client_id=client_id,
            secret_key=secret_key,
            pin=pin,
            refresh_token=refresh_token,
            post=post,
        )
    except Exception as exc:
        return FyersAuthResult(
            status=FAILED_NEEDS_REGENERATION,
            message=str(exc),
            needs_regeneration=True,
            access_token_expired=True,
            refresh_token_expired=False,
        )

    if is_token_expired(refreshed_access_token, now=now):
        return FyersAuthResult(
            status=FAILED_NEEDS_REGENERATION,
            message="FYERS refresh returned an invalid or expired access token.",
            needs_regeneration=True,
            access_token_expired=True,
            refresh_token_expired=False,
        )

    return FyersAuthResult(
        status=EXPIRED_BUT_REFRESHED,
        message="FYERS access token was expired and has been refreshed.",
        access_token=refreshed_access_token,
        refreshed=True,
        access_token_expired=True,
        refresh_token_expired=False,
    )
