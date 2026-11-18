"""Isolated tests for API request optimization helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType
import unittest


def _install_import_stubs() -> None:
    """Install the minimum dependency surface needed to import api.py."""
    aiohttp = ModuleType("aiohttp")

    class ClientError(Exception):
        """aiohttp client error stub."""

    class ClientResponseError(ClientError):
        """aiohttp response error stub."""

    aiohttp.ClientError = ClientError
    aiohttp.ClientResponseError = ClientResponseError
    sys.modules.setdefault("aiohttp", aiohttp)

    homeassistant = ModuleType("homeassistant")
    homeassistant.__path__ = []
    core = ModuleType("homeassistant.core")
    exceptions = ModuleType("homeassistant.exceptions")
    helpers = ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    aiohttp_client = ModuleType("homeassistant.helpers.aiohttp_client")
    oauth2_flow = ModuleType("homeassistant.helpers.config_entry_oauth2_flow")
    const = ModuleType("homeassistant.const")

    class HomeAssistant:
        """Home Assistant stub."""

    class ConfigEntryAuthFailed(Exception):
        """Authentication failure stub."""

    class OAuth2Session:
        """OAuth session stub."""

    class Platform(str, Enum):
        """Platform enum stub."""

        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"

    core.HomeAssistant = HomeAssistant
    exceptions.ConfigEntryAuthFailed = ConfigEntryAuthFailed
    aiohttp_client.async_get_clientsession = lambda _hass: None
    oauth2_flow.OAuth2Session = OAuth2Session
    const.Platform = Platform

    sys.modules.setdefault("homeassistant", homeassistant)
    sys.modules.setdefault("homeassistant.core", core)
    sys.modules.setdefault("homeassistant.exceptions", exceptions)
    sys.modules.setdefault("homeassistant.helpers", helpers)
    sys.modules.setdefault("homeassistant.helpers.aiohttp_client", aiohttp_client)
    sys.modules.setdefault("homeassistant.helpers.config_entry_oauth2_flow", oauth2_flow)
    sys.modules.setdefault("homeassistant.const", const)


_install_import_stubs()
INTEGRATION_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "diapstash"
PACKAGE_NAME = "diapstash_api_testpkg"
PACKAGE = ModuleType(PACKAGE_NAME)
PACKAGE.__path__ = [str(INTEGRATION_PATH)]
sys.modules[PACKAGE_NAME] = PACKAGE
SPEC = spec_from_file_location(f"{PACKAGE_NAME}.api", INTEGRATION_PATH / "api.py")
assert SPEC is not None and SPEC.loader is not None
API = module_from_spec(SPEC)
sys.modules[SPEC.name] = API
SPEC.loader.exec_module(API)


class TestApiOptimizationHelpers(unittest.TestCase):
    """Test request-control helpers without Home Assistant installed."""

    def test_rate_limit_delay_prefers_retry_after(self) -> None:
        headers = {"Retry-After": "45", "RateLimit": "r=0, w=900"}
        self.assertEqual(API._rate_limit_retry_after(headers), 45)

    def test_rate_limit_delay_reads_window(self) -> None:
        self.assertEqual(API._rate_limit_retry_after({"RateLimit": "r=0; w=321"}), 321)

    def test_integer_counter_validation(self) -> None:
        self.assertEqual(API._int_value(12), 12)
        self.assertEqual(API._int_value("13"), 13)
        self.assertIsNone(API._int_value(True))
        self.assertIsNone(API._int_value(1.5))


class TestApiRequestFlow(unittest.IsolatedAsyncioTestCase):
    """Test optimized async request behavior."""

    async def test_rate_limit_does_not_try_fallback_base(self) -> None:
        client = object.__new__(API.DiapStashApiClient)
        urls: list[str] = []

        async def rate_limited(url: str):
            urls.append(url)
            raise API.DiapStashApiError("limited", status=429, retry_after=60)

        client._get_json_url = rate_limited
        with self.assertRaises(API.DiapStashApiError):
            await client._api_get("/history/latest-change")
        self.assertEqual(len(urls), 1)

    async def test_embedded_type_details_skip_catalog_request(self) -> None:
        client = object.__new__(API.DiapStashApiClient)

        async def unexpected_catalog_request(_type_id):
            self.fail("embedded details should avoid a catalog request")

        client.async_resolve_catalog_type = unexpected_catalog_request
        info = await client._resolve_diaper_info(
            {
                "typeId": 27,
                "size": "L",
                "type": {
                    "name": "LittlePawz",
                    "brand": {"name": "ABUniverse"},
                    "variant": {"name": "Blue", "primaryImage": {"url": "https://example.test/variant.png"}},
                },
            }
        )
        self.assertEqual(info["name"], "LittlePawz")
        self.assertEqual(info["brand"], "ABUniverse")
        self.assertEqual(info["variant"], "Blue")
        self.assertEqual(info["image_url"], "https://example.test/variant.png")

    async def test_latest_change_404_means_no_recorded_change(self) -> None:
        client = object.__new__(API.DiapStashApiClient)

        async def not_found(_path, _query=None, *, fallback_on_not_found=True):
            self.assertFalse(fallback_on_not_found)
            raise API.DiapStashApiError("not found", status=404)

        client._api_get = not_found
        change, url = await client.async_get_latest_change()
        self.assertIsNone(change)
        self.assertIsNone(url)

    async def test_current_change_uses_aggregate_endpoints(self) -> None:
        client = object.__new__(API.DiapStashApiClient)
        start = datetime.now(timezone.utc) - timedelta(minutes=10)
        previous_end = start - timedelta(minutes=5)

        async def latest_change():
            return (
                {
                    "id": 123,
                    "startTime": start.isoformat(),
                    "endTime": None,
                    "tags": ["night"],
                    "note": "test note",
                    "diapers": [
                        {
                            "order": 0,
                            "typeId": 27,
                            "size": "L",
                            "type": {"name": "LittlePawz", "brand": {"name": "ABUniverse"}},
                        },
                        {
                            "order": 1,
                            "typeId": 99,
                            "size": "Boost",
                            "type": {"name": "Booster", "brand": {"name": "Example"}},
                        },
                    ],
                },
                "https://api.diapstash.com/api/v1/history/latest-change",
            )

        async def history_stats():
            return {
                "changeCount": 42,
                "changesByPeriod": {"monthToDate": 7, "yearToDate": 30},
            }

        async def history_streak():
            return {
                "changeCount": 2,
                "totalTimeInDiaperMinutes": 60,
                "endAt": previous_end.isoformat(),
            }

        async def unexpected_history_paging():
            self.fail("full history paging must not be used")

        client.async_get_latest_change = latest_change
        client.async_get_history_stats = history_stats
        client.async_get_history_streak = history_streak
        client.async_get_all_history = unexpected_history_paging
        data = await client.async_get_current_diaper(enable_stock=False, enable_stats=True)

        self.assertTrue(data.wearing)
        self.assertEqual(data.total_changes, 42)
        self.assertEqual(data.month_count, 7)
        self.assertEqual(data.year_count, 30)
        self.assertEqual(data.streak_count, 3)
        self.assertEqual(data.boosters_count, 1)
        self.assertEqual(data.change_tags, ["night"])
        self.assertEqual(data.change_note, "test note")


if __name__ == "__main__":
    unittest.main()
