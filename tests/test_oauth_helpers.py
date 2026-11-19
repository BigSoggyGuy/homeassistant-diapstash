"""Tests for DiapStash OAuth refresh helpers."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "diapstash"
    / "oauth.py"
)
SPEC = spec_from_file_location("diapstash_oauth_isolated", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
OAUTH = module_from_spec(SPEC)
SPEC.loader.exec_module(OAUTH)


class TestOAuthTokenHelpers(unittest.TestCase):
    """Verify refresh rotation and safe error classification."""

    def test_omitted_refresh_token_keeps_current_value(self) -> None:
        current = {
            "access_token": "old-access",
            "refresh_token": "old-refresh",
            "expires_in": 3600,
        }
        response = {"access_token": "new-access", "expires_in": 3600}

        merged = OAUTH.merge_refresh_token_response(current, response)

        self.assertEqual(merged["access_token"], "new-access")
        self.assertEqual(merged["refresh_token"], "old-refresh")

    def test_returned_refresh_token_replaces_current_value(self) -> None:
        current = {"access_token": "old-access", "refresh_token": "old-refresh"}
        response = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
        }

        merged = OAUTH.merge_refresh_token_response(current, response)

        self.assertEqual(merged["refresh_token"], "new-refresh")

    def test_empty_refresh_token_keeps_current_value(self) -> None:
        current = {"access_token": "old-access", "refresh_token": "old-refresh"}
        response = {
            "access_token": "new-access",
            "refresh_token": "",
            "expires_in": 3600,
        }

        merged = OAUTH.merge_refresh_token_response(current, response)

        self.assertEqual(merged["refresh_token"], "old-refresh")

    def test_transient_token_failures_do_not_require_reauth(self) -> None:
        self.assertEqual(OAUTH.classify_token_error(429, "unknown_error"), "transient")
        self.assertEqual(OAUTH.classify_token_error(503, "server_error"), "transient")
        self.assertEqual(
            OAUTH.classify_token_error(400, "temporarily_unavailable"),
            "transient",
        )

    def test_invalid_grant_requires_reauth(self) -> None:
        self.assertEqual(OAUTH.classify_token_error(400, "invalid_grant"), "reauth")
        self.assertEqual(OAUTH.classify_token_error(401, "unknown_error"), "reauth")

    def test_other_bad_requests_are_not_mislabeled_as_expired_tokens(self) -> None:
        self.assertEqual(OAUTH.classify_token_error(400, "invalid_request"), "error")

    def test_error_code_is_bounded_before_logging(self) -> None:
        self.assertEqual(OAUTH.safe_oauth_error_code("invalid_grant"), "invalid_grant")
        self.assertEqual(
            OAUTH.safe_oauth_error_code("invalid_grant token=secret"),
            "unknown_error",
        )


if __name__ == "__main__":
    unittest.main()
