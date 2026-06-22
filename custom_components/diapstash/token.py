"""Token helpers for DiapStash."""

from __future__ import annotations

import base64
import json
from typing import Any


def sub_from_access_token(access_token: str | None) -> str | None:
    """Extract the OIDC subject claim from a JWT access token.

    The token has already been obtained through the OAuth flow. We only decode
    the payload locally to get a stable account identifier for Home Assistant's
    config entry unique_id; this helper does not validate the token signature.
    """
    if not access_token or not isinstance(access_token, str):
        return None
    parts = access_token.split(".")
    if len(parts) < 2:
        return None
    try:
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        data = json.loads(decoded.decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    sub = data.get("sub")
    if sub is None:
        return None
    sub = str(sub).strip()
    return sub or None


def sub_from_flow_data(data: dict[str, Any]) -> str | None:
    """Extract the account subject from Home Assistant OAuth flow data."""
    token = data.get("token")
    if not isinstance(token, dict):
        return None
    return sub_from_access_token(token.get("access_token"))
