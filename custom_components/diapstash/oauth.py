"""OAuth token helpers for DiapStash."""

from __future__ import annotations

import re
from typing import Any, Literal, Mapping

OAuthTokenErrorKind = Literal["transient", "reauth", "error"]

_TRANSIENT_ERROR_CODES = {
    "server_error",
    "slow_down",
    "temporarily_unavailable",
}
_REAUTH_ERROR_CODES = {
    "access_denied",
    "invalid_client",
    "invalid_grant",
    "invalid_scope",
    "invalid_token",
    "unauthorized_client",
}
_SAFE_ERROR_CODE = re.compile(r"[A-Za-z0-9_.-]{1,64}")


def classify_token_error(status: int, error_code: str) -> OAuthTokenErrorKind:
    """Classify a token endpoint failure without exposing response details."""
    normalized = error_code.casefold()
    if status in {408, 425, 429} or status >= 500 or normalized in _TRANSIENT_ERROR_CODES:
        return "transient"
    if status in {401, 403} or normalized in _REAUTH_ERROR_CODES:
        return "reauth"
    return "error"


def safe_oauth_error_code(value: Any) -> str:
    """Return a bounded OAuth error identifier safe for logs and diagnostics."""
    if not isinstance(value, str) or not _SAFE_ERROR_CODE.fullmatch(value):
        return "unknown_error"
    return value


def merge_refresh_token_response(
    current_token: Mapping[str, Any],
    response_token: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge a refresh response while retaining an omitted or empty refresh token."""
    merged = {**current_token, **response_token}
    if response_token.get("refresh_token") in (None, ""):
        if current_refresh_token := current_token.get("refresh_token"):
            merged["refresh_token"] = current_refresh_token
    return merged
