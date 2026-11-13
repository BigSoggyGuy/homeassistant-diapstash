"""Small isolated tests requiring no Home Assistant installation."""

from __future__ import annotations

import base64
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "diapstash" / "token.py"
SPEC = spec_from_file_location("diapstash_token_isolated", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_dummy_token(subject: str) -> str:
    """Create a fake unsigned JWT-format token only for isolated decoder tests."""
    payload = base64.urlsafe_b64encode(json.dumps({"sub": subject}).encode()).decode().rstrip("=")
    return f"dummy.{payload}.dummy"


class TestSubjectDecoder(unittest.TestCase):
    def test_extracts_subject(self) -> None:
        self.assertEqual(MODULE.sub_from_access_token(make_dummy_token("example-account")), "example-account")

    def test_missing_or_invalid_access_token(self) -> None:
        for token in (None, "", "invalid", "not.jwt", "a.****.b"):
            self.assertIsNone(MODULE.sub_from_access_token(token))

    def test_extracts_subject_from_flow_data(self) -> None:
        data = {"token": {"access_token": make_dummy_token("account-two")}}
        self.assertEqual(MODULE.sub_from_flow_data(data), "account-two")

    def test_missing_token_in_flow_data(self) -> None:
        self.assertIsNone(MODULE.sub_from_flow_data({}))
        self.assertIsNone(MODULE.sub_from_flow_data({"token": "unexpected"}))


if __name__ == "__main__":
    unittest.main()
