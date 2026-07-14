"""DiapStash API client."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import (
    ADD_URL,
    API_BASES,
    BRAND_PATH,
    CATALOG_TYPE_URL,
    COMMON_HEADERS,
    DISPOSABLES_PATH,
    MAX_PAGE_SIZE,
    REUSABLES_PATH,
    STOCKS_PATH,
    TYPE_PATH,
)

_LOGGER = logging.getLogger(__name__)


class DiapStashApiError(Exception):
    """Raised when the DiapStash API fails."""


@dataclass(slots=True)
class DiapStashStockItem:
    """Resolved stock item."""

    label: str
    quantity: int | float | None
    type_id: int | str | None = None
    brand: str | None = None
    diaper_name: str | None = None
    size: str | None = None
    variant: str | None = None
    catalog_url: str | None = None
    add_url: str | None = None
    image_url: str | None = None
    raw_id: int | str | None = None
    stock_id: str | None = None
    stock_name: str | None = None


@dataclass(slots=True)
class DiapStashStockLocation:
    """Resolved stock location."""

    id: str
    name: str
    available: int | float
    threshold: int | float | None = None
    low: bool = False
    masked: bool = False
    principal: bool = False
    order: int | None = None


@dataclass(slots=True)
class DiapStashCurrentDiaper:
    """Current diaper and stock data."""

    wearing: bool
    label: str
    diaper_name: str | None = None
    brand: str | None = None
    size: str | None = None
    variant: str | None = None
    start_time: str | None = None
    change_id: int | str | None = None
    type_id: int | str | None = None
    catalog_url: str | None = None
    image_url: str | None = None
    current_items: list[dict[str, Any]] = field(default_factory=list)
    boosters: list[dict[str, Any]] = field(default_factory=list)
    boosters_count: int | None = None
    boosters_label: str | None = None
    change_tags: list[str] = field(default_factory=list)
    change_tags_label: str | None = None
    change_note: str | None = None
    change_has_note: bool = False
    debug_count: int | None = None
    debug_total_count: int | None = None
    debug_url: str | None = None
    month_count: int | None = None
    year_count: int | None = None
    total_changes: int | None = None
    streak_count: int | None = None
    streak_minutes: int | None = None
    streak_text: str | None = None
    stock_total: int | float | None = None
    stock_entries: int | None = None
    stock_locations_count: int | None = None
    stock_to_wash: int | None = None
    stock_reusables: list[dict[str, Any]] = field(default_factory=list)
    stock_items: list[DiapStashStockItem] = field(default_factory=list)
    stock_locations: list[DiapStashStockLocation] = field(default_factory=list)
    stock_by_brand: list[dict[str, Any]] = field(default_factory=list)
    stock_by_type: list[dict[str, Any]] = field(default_factory=list)
    stock_error: str | None = None
    stock_debug_url: str | None = None

    @property
    def duration_minutes(self) -> int:
        """Return duration in minutes."""
        if not self.wearing or not self.start_time:
            return 0
        try:
            value = self.start_time.replace("Z", "+00:00")
            start = datetime.fromisoformat(value).astimezone(timezone.utc)
        except (ValueError, TypeError):
            return 0
        return max(0, int((datetime.now(timezone.utc) - start).total_seconds() / 60))

    @property
    def duration_text(self) -> str:
        """Return duration as human text."""
        minutes = self.duration_minutes
        if not self.wearing:
            return "Not worn"
        return _humanize_minutes(minutes)

    @property
    def stock_label(self) -> str:
        """Return stock overview text."""
        if self.stock_error:
            return "Stock unavailable"
        if self.stock_total is None:
            return "Unknown stock"
        locations = self.stock_locations_count or 0
        return f"{_format_number(self.stock_total)} diapers / {locations} locations"


@dataclass(slots=True)
class CatalogType:
    """Resolved catalog type."""

    brand: str | None
    name: str | None
    image_url: str | None = None


class DiapStashApiClient:
    """DiapStash API client."""

    def __init__(self, hass: HomeAssistant, oauth_session: OAuth2Session) -> None:
        """Initialize client."""
        self.hass = hass
        self.oauth_session = oauth_session
        self._catalog_cache: dict[str, CatalogType] = {}
        self._type_cache: dict[str, dict[str, Any] | None] = {}
        self._brand_cache: dict[str, dict[str, Any] | None] = {}

    @property
    def client_id(self) -> str:
        """Return the OAuth client ID for DS-API-CLIENT-ID header."""
        implementation = self.oauth_session.implementation
        client_id = getattr(implementation, "client_id", "")
        if not client_id:
            raise DiapStashApiError("OAuth implementation does not expose client_id")
        return str(client_id)

    async def _headers(self, *, force_refresh: bool = False) -> dict[str, str]:
        """Return authenticated headers."""
        if force_refresh:
            await self._force_refresh_token()
        else:
            await self.oauth_session.async_ensure_token_valid()
        access_token = self.oauth_session.token["access_token"]
        return {
            **COMMON_HEADERS,
            "Authorization": f"Bearer {access_token}",
            "DS-API-CLIENT-ID": self.client_id,
        }

    async def _force_refresh_token(self) -> None:
        """Force a token refresh after an API 401 response."""
        try:
            refresh = getattr(self.oauth_session, "async_refresh_token", None)
            if refresh is not None:
                await refresh()
                return
            self.oauth_session.token["expires_at"] = 0
            await self.oauth_session.async_ensure_token_valid()
        except Exception as err:  # Home Assistant will start re-auth for this exception.
            raise ConfigEntryAuthFailed("DiapStash authentication failed") from err

    async def _get_json_url(self, url: str) -> Any:
        """GET JSON from a full URL."""
        session = async_get_clientsession(self.hass)
        headers = await self._headers()
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 401:
                    _LOGGER.debug("DiapStash API returned 401; refreshing token and retrying once")
                    headers = await self._headers(force_refresh=True)
                    async with session.get(url, headers=headers) as retry_resp:
                        if retry_resp.status == 401:
                            text = await retry_resp.text()
                            raise ConfigEntryAuthFailed(
                                f"DiapStash authentication failed: HTTP 401: {text[:200]}"
                            )
                        if retry_resp.status >= 400:
                            text = await retry_resp.text()
                            raise DiapStashApiError(f"GET {url} failed: HTTP {retry_resp.status}: {text[:300]}")
                        return await retry_resp.json()
                if resp.status >= 400:
                    text = await resp.text()
                    raise DiapStashApiError(f"GET {url} failed: HTTP {resp.status}: {text[:300]}")
                return await resp.json()
        except ConfigEntryAuthFailed:
            raise
        except ClientResponseError as err:
            raise DiapStashApiError(f"GET {url} failed: {err}") from err
        except ClientError as err:
            raise DiapStashApiError(f"GET {url} failed: {err}") from err

    async def _api_get(self, path: str, query: dict[str, Any] | None = None) -> tuple[Any, str]:
        """GET JSON from the first working API base."""
        errors: list[str] = []
        for base in API_BASES:
            url = _build_url(base + path, query)
            try:
                return await self._get_json_url(url), url
            except DiapStashApiError as err:
                message = str(err)
                if "HTTP 401" in message or "HTTP 403" in message:
                    raise
                errors.append(message)
        raise DiapStashApiError("API request failed. " + " | ".join(errors))

    @staticmethod
    def _extract_data(response: Any) -> list[dict[str, Any]]:
        """Extract list data from API response."""
        if isinstance(response, dict):
            data = response.get("data", [])
            if isinstance(data, list):
                return data
        if isinstance(response, list):
            return response
        return []

    @staticmethod
    def _total_count(response: Any) -> int | None:
        """Extract total count."""
        if isinstance(response, dict) and isinstance(response.get("totalCount"), int):
            return response["totalCount"]
        if isinstance(response, dict) and isinstance(response.get("count"), int):
            return response["count"]
        return None

    async def async_get_all_history(self) -> tuple[list[dict[str, Any]], int | None, str | None]:
        """Fetch all available history pages."""
        changes, total_count, last_url = await self._get_all_paginated(
            "/history/changes",
            {"sort": "startTime,desc"},
        )
        return changes, total_count or len(changes), last_url

    async def _get_all_paginated(self, path: str, query: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], int | None, str | None]:
        """Fetch all pages from a paginated DiapStash endpoint."""
        out: list[dict[str, Any]] = []
        total_count: int | None = None
        last_url: str | None = None
        base_query = dict(query or {})
        page = 0

        while True:
            page_query = {**base_query, "size": MAX_PAGE_SIZE, "page": page}
            response, last_url = await self._api_get(path, page_query)
            data = self._extract_data(response)
            if total_count is None:
                total_count = self._total_count(response)
            if not data:
                break
            out.extend(data)
            if total_count is not None and len(out) >= total_count:
                break
            if len(data) < MAX_PAGE_SIZE:
                break
            page += 1

        return out, total_count or len(out), last_url

    async def async_get_stocks(self) -> tuple[list[dict[str, Any]], int | None, str | None]:
        """Fetch stock locations."""
        return await self._get_all_paginated(STOCKS_PATH)

    async def async_get_disposables(self) -> tuple[list[dict[str, Any]], int | None, str | None]:
        """Fetch disposable stock batches with remaining items."""
        return await self._get_all_paginated(DISPOSABLES_PATH, {"left.gt": 0})

    async def async_get_reusables(self) -> tuple[list[dict[str, Any]], int | None, str | None]:
        """Fetch reusable stock items."""
        return await self._get_all_paginated(REUSABLES_PATH)

    async def async_get_type(self, type_id: int | str | None) -> dict[str, Any] | None:
        """Fetch an official DiapStash type if the token has access."""
        if type_id is None:
            return None
        key = str(type_id)
        if key in self._type_cache:
            return self._type_cache[key]
        try:
            response, _ = await self._api_get(TYPE_PATH.format(type_id=key))
            if isinstance(response, dict):
                type_data = response.get("type") or response
                if isinstance(type_data, dict):
                    self._type_cache[key] = type_data
                    return type_data
        except DiapStashApiError:
            _LOGGER.debug("Could not resolve API type %s", key, exc_info=True)
        self._type_cache[key] = None
        return None

    async def async_get_brand(self, brand_code: str | None) -> dict[str, Any] | None:
        """Fetch an official DiapStash brand if available."""
        if not brand_code:
            return None
        key = str(brand_code)
        if key in self._brand_cache:
            return self._brand_cache[key]
        try:
            response, _ = await self._api_get(BRAND_PATH.format(brand_code=key))
            if isinstance(response, dict):
                brand = response.get("brand") or response
                if isinstance(brand, dict):
                    self._brand_cache[key] = brand
                    return brand
        except DiapStashApiError:
            _LOGGER.debug("Could not resolve API brand %s", key, exc_info=True)
        self._brand_cache[key] = None
        return None

    async def async_resolve_catalog_type(self, type_id: int | str | None) -> CatalogType:
        """Resolve catalog type ID to brand and model through the official API."""
        if type_id is None:
            return CatalogType(None, None)
        type_id_str = str(type_id)
        if type_id_str in self._catalog_cache:
            return self._catalog_cache[type_id_str]

        api_type = await self.async_get_type(type_id_str)
        if api_type:
            brand = _brand_name_from_type(api_type)
            if not brand:
                brand_code = api_type.get("brand_code") or api_type.get("brandCode")
                brand_data = await self.async_get_brand(brand_code)
                if brand_data:
                    brand = str(brand_data.get("name") or brand_code)
            catalog_type = CatalogType(
                brand=brand,
                name=str(api_type.get("name")) if api_type.get("name") else None,
                image_url=_image_url_from_type(api_type),
            )
            self._catalog_cache[type_id_str] = catalog_type
            return catalog_type

        catalog_type = CatalogType(brand=None, name=f"type_id {type_id_str}")
        self._catalog_cache[type_id_str] = catalog_type
        return catalog_type

    async def async_get_current_diaper(
        self,
        *,
        enable_stock: bool = True,
        enable_stats: bool = True,
        low_stock_threshold: int | float | None = None,
    ) -> DiapStashCurrentDiaper:
        """Fetch the current worn diaper and stock summary."""
        changes, total_count, debug_url = await self.async_get_all_history()
        current = _find_current_change(changes)
        if current is None:
            data = DiapStashCurrentDiaper(
                wearing=False,
                label="No diaper",
                debug_count=len(changes),
                debug_total_count=total_count,
                debug_url=debug_url,
                total_changes=total_count,
            )
        else:
            data = await self._build_current_diaper(current, len(changes), total_count, debug_url)
        if enable_stats:
            self._attach_change_stats(data, changes, total_count)
        if enable_stock:
            await self._attach_stock(data, low_stock_threshold=low_stock_threshold)
        else:
            data.stock_error = "Stock polling disabled in options"
        return data

    async def _build_current_diaper(
        self,
        current: dict[str, Any],
        debug_count: int,
        total_count: int | None,
        debug_url: str | None,
    ) -> DiapStashCurrentDiaper:
        """Build current diaper object."""
        diapers = current.get("diapers") or []
        sorted_diapers = sorted(diapers, key=lambda item: item.get("order") or 0)
        resolved_items: list[dict[str, Any]] = []
        for index, diaper_item in enumerate(sorted_diapers):
            item_info = await self._resolve_diaper_info(diaper_item)
            resolved_items.append(_current_change_item_to_dict(diaper_item, item_info, index))

        first_item = resolved_items[0] if resolved_items else {}
        additional_items = resolved_items[1:]
        label_parts = []
        if first_item.get("brand"):
            label_parts.append(str(first_item["brand"]))
        if first_item.get("diaper_name"):
            label_parts.append(str(first_item["diaper_name"]))
        if first_item.get("size"):
            label_parts.append(f"Size {first_item['size']}")
        change_tags = _extract_change_tags(current)
        change_note = _extract_change_note(current)

        return DiapStashCurrentDiaper(
            wearing=current.get("endTime") is None,
            label=" ".join(label_parts) or "Unknown diaper",
            diaper_name=first_item.get("diaper_name"),
            brand=first_item.get("brand"),
            size=first_item.get("size"),
            variant=first_item.get("variant"),
            start_time=current.get("startTime"),
            change_id=current.get("id"),
            type_id=first_item.get("type_id"),
            catalog_url=first_item.get("catalog_url"),
            image_url=first_item.get("image_url"),
            current_items=resolved_items,
            boosters=additional_items,
            boosters_count=len(additional_items),
            boosters_label=", ".join(str(item.get("label")) for item in additional_items if item.get("label")) or None,
            change_tags=change_tags,
            change_tags_label=", ".join(change_tags) or None,
            change_note=change_note,
            change_has_note=change_note is not None,
            debug_count=debug_count,
            debug_total_count=total_count,
            debug_url=debug_url,
            total_changes=total_count,
        )

    def _attach_change_stats(
        self,
        data: DiapStashCurrentDiaper,
        changes: list[dict[str, Any]],
        total_count: int | None,
    ) -> None:
        """Attach change counters and current streak from loaded history."""
        now = datetime.now(timezone.utc)
        start_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        start_year = datetime(now.year, 1, 1, tzinfo=timezone.utc)
        data.month_count = sum(1 for change in changes if (_parse_time(change.get("startTime")) or now) >= start_month)
        data.year_count = sum(1 for change in changes if (_parse_time(change.get("startTime")) or now) >= start_year)
        data.total_changes = total_count or len(changes)
        streak_count, streak_minutes = _build_streak(changes, now)
        data.streak_count = streak_count
        data.streak_minutes = streak_minutes
        data.streak_text = _humanize_minutes(streak_minutes)

    async def _attach_stock(
        self,
        data: DiapStashCurrentDiaper,
        *,
        low_stock_threshold: int | float | None = None,
    ) -> None:
        """Attach stock data to current diaper data."""
        try:
            stocks, _, stocks_url = await self.async_get_stocks()
            disposables, disposable_count, disposables_url = await self.async_get_disposables()
            reusables, reusable_count, reusables_url = await self.async_get_reusables()

            stock_name_by_id = {
                str(stock.get("id")): str(stock.get("name") or stock.get("id"))
                for stock in stocks
                if stock.get("id") is not None
            }

            resolved_items = [await self._build_stock_item(item, stock_name_by_id) for item in disposables]

            per_stock: dict[str, int | float] = {}
            for item in disposables:
                stock_id = item.get("stockId") or item.get("stock_id")
                qty = item.get("left")
                if not stock_id or not isinstance(qty, (int, float)) or qty <= 0:
                    continue
                per_stock[str(stock_id)] = per_stock.get(str(stock_id), 0) + qty

            stock_locations = []
            for stock in sorted(stocks, key=lambda item: item.get("order") or 0):
                stock_id = str(stock.get("id") or "")
                if not stock_id:
                    continue
                masked = bool(stock.get("masked", False))
                # Match the TRMNL behaviour: hidden/masked locations are not
                # part of the public overview by default.
                if masked:
                    continue
                available = per_stock.get(stock_id, 0)
                threshold = stock.get("thresholdLowStock")
                effective_threshold = threshold if isinstance(threshold, (int, float)) else low_stock_threshold
                low = isinstance(effective_threshold, (int, float)) and available <= effective_threshold
                stock_locations.append(
                    DiapStashStockLocation(
                        id=stock_id,
                        name=str(stock.get("name") or stock_id),
                        available=available,
                        threshold=effective_threshold if isinstance(effective_threshold, (int, float)) else None,
                        low=low,
                        masked=masked,
                        principal=bool(stock.get("principal", False)),
                        order=stock.get("order") if isinstance(stock.get("order"), int) else None,
                    )
                )

            to_wash = sum(
                1
                for item in reusables
                if _needs_wash(item)
            )

            data.stock_items = resolved_items
            data.stock_reusables = [_reusable_debug_item(item) for item in reusables]
            data.stock_locations = stock_locations
            data.stock_locations_count = len(stock_locations)
            data.stock_entries = len(disposables) if disposable_count is None else disposable_count
            data.stock_total = sum(location.available for location in stock_locations)
            data.stock_to_wash = to_wash
            data.stock_by_brand = _group_stock_by_brand(resolved_items)
            data.stock_by_type = _group_stock_by_type(resolved_items)
            data.stock_debug_url = f"stocks={stocks_url}; disposables={disposables_url}; reusables={reusables_url}"
            _ = reusable_count  # kept for future diagnostics
        except DiapStashApiError as err:
            data.stock_error = str(err)

    async def _build_stock_item(
        self,
        item: dict[str, Any],
        stock_name_by_id: dict[str, str] | None = None,
    ) -> DiapStashStockItem:
        """Build a stock item from raw API data."""
        info = await self._resolve_diaper_info(item)
        quantity = _extract_quantity(item)
        label_parts = []
        if info["brand"]:
            label_parts.append(str(info["brand"]))
        if info["name"]:
            label_parts.append(str(info["name"]))
        if info["size"]:
            label_parts.append(f"Size {info['size']}")
        label = " ".join(label_parts) or (f"type_id {info['type_id']}" if info["type_id"] else "Unknown stock item")
        stock_id = item.get("stockId") or item.get("stock_id")
        stock_id_key = str(stock_id) if stock_id is not None else None
        stock_name = (stock_name_by_id or {}).get(stock_id_key) if stock_id_key else None
        return DiapStashStockItem(
            label=label,
            quantity=quantity,
            type_id=info["type_id"],
            brand=info["brand"],
            diaper_name=info["name"],
            size=info["size"],
            variant=info["variant"],
            catalog_url=CATALOG_TYPE_URL.format(type_id=info["type_id"]) if info["type_id"] else None,
            add_url=_add_url(info["type_id"], info["size"]),
            image_url=info["image_url"],
            raw_id=item.get("id"),
            stock_id=stock_id,
            stock_name=stock_name,
        )

    async def _resolve_diaper_info(self, item: dict[str, Any]) -> dict[str, Any]:
        """Resolve diaper fields from history or stock item."""
        type_obj = item.get("type") or item.get("diaperType") or item.get("diaper_type") or {}
        brand_obj = type_obj.get("brand") or item.get("brand") or {}
        variant_obj = item.get("variant") or {}
        type_id = (
            item.get("type_id")
            or item.get("typeId")
            or item.get("diaperTypeId")
            or item.get("diaper_type_id")
        )
        catalog = await self.async_resolve_catalog_type(type_id)
        name = (
            item.get("diaperName")
            or item.get("name")
            or item.get("typeName")
            or type_obj.get("name")
            or catalog.name
            or (f"type_id {type_id}" if type_id else None)
        )
        brand = item.get("diaperBrand") or brand_obj.get("name") or catalog.brand
        size = item.get("size") or item.get("diaperSize")
        variant = item.get("variantName") or variant_obj.get("name")
        image_url = (
            item.get("imageUrl")
            or _image_url_from_type(type_obj)
            or catalog.image_url
        )
        return {
            "type_id": type_id,
            "name": str(name) if name else None,
            "brand": str(brand) if brand else None,
            "size": str(size) if size else None,
            "variant": str(variant) if variant else None,
            "image_url": str(image_url) if image_url else None,
        }



def _extract_change_tags(change: dict[str, Any]) -> list[str]:
    """Extract human-readable tags from a history change."""
    tags: list[str] = []
    for key in (
        "tags",
        "tag",
        "tagNames",
        "tag_names",
        "tagName",
        "tag_name",
        "changeTags",
        "change_tags",
        "labels",
        "label",
    ):
        if key in change:
            tags.extend(_normalize_tag_values(change.get(key)))
    return _unique_preserve_order(tags)


def _normalize_tag_values(value: Any) -> list[str]:
    """Normalize tag values that may be strings, dicts or lists."""
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    if isinstance(value, dict):
        for key in ("name", "label", "title", "text", "value"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return [nested.strip()]
        return []
    if isinstance(value, list):
        tags: list[str] = []
        for item in value:
            tags.extend(_normalize_tag_values(item))
        return tags
    return []


def _extract_change_note(change: dict[str, Any]) -> str | None:
    """Extract a user note/comment from a history change."""
    for key in (
        "note",
        "notes",
        "comment",
        "comments",
        "description",
        "memo",
        "text",
    ):
        value = change.get(key)
        note = _normalize_note_value(value)
        if note:
            return note
    return None


def _normalize_note_value(value: Any) -> str | None:
    """Normalize a note value that may be a string or nested object."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, dict):
        for key in ("text", "value", "note", "comment", "description"):
            note = _normalize_note_value(value.get(key))
            if note:
                return note
    return None


def _unique_preserve_order(values: list[str]) -> list[str]:
    """Deduplicate strings while preserving their first occurrence."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _current_change_item_to_dict(item: dict[str, Any], info: dict[str, Any], index: int) -> dict[str, Any]:
    """Return a compact current-change diaper/booster item for attributes."""
    label_parts: list[str] = []
    if info.get("brand"):
        label_parts.append(str(info["brand"]))
    if info.get("name"):
        label_parts.append(str(info["name"]))
    if info.get("size"):
        label_parts.append(f"Size {info['size']}")
    label = " ".join(label_parts) or (f"type_id {info['type_id']}" if info.get("type_id") else "Unknown item")
    type_id = info.get("type_id")
    return {
        "index": index,
        "role": _current_change_item_role(item, index),
        "label": label,
        "type_id": type_id,
        "brand": info.get("brand"),
        "diaper_name": info.get("name"),
        "size": info.get("size"),
        "variant": info.get("variant"),
        "catalog_url": CATALOG_TYPE_URL.format(type_id=type_id) if type_id else None,
        "image_url": info.get("image_url"),
        "order": item.get("order"),
        "change_item_id": item.get("id"),
        "stock_id": item.get("stockId") or item.get("stock_id"),
    }


def _current_change_item_role(item: dict[str, Any], index: int) -> str:
    """Best-effort role for an item on the current change."""
    explicit = (
        item.get("role")
        or item.get("type")
        or item.get("kind")
        or item.get("category")
        or item.get("usage")
        or item.get("itemType")
        or item.get("item_type")
    )
    if explicit is not None:
        value = str(explicit).strip().lower()
        if "boost" in value:
            return "booster"
        if "diaper" in value or "nappy" in value:
            return "diaper"
    if _api_bool(item.get("booster")) or _api_bool(item.get("isBooster")) or _api_bool(item.get("is_booster")):
        return "booster"
    return "diaper" if index == 0 else "booster"


def _api_bool(value: Any) -> bool:
    """Return a safe boolean for API values that may be bool, number or string."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "on"}
    return False


def _needs_wash(item: dict[str, Any]) -> bool:
    """Return whether a reusable diaper needs washing."""
    state = str(item.get("state") or item.get("status") or "").strip().upper()
    # Some API payloads can keep a legacy needWash flag while the item state
    # already says it is clean/washed. In that conflict, the explicit clean
    # state should win because it matches what the app shows to the user.
    if state in {"CLEAN", "WASHED", "AVAILABLE", "IN_STOCK", "READY"}:
        return False
    if state in {"DIRTY", "TO_WASH", "NEED_WASH", "NEEDS_WASH"}:
        return True
    return _api_bool(item.get("needWash")) or _api_bool(item.get("need_wash"))


def _reusable_debug_item(item: dict[str, Any]) -> dict[str, Any]:
    """Return a compact reusable diagnostic object for Home Assistant attributes."""
    type_obj = item.get("type") or item.get("diaperType") or item.get("diaper_type") or {}
    return {
        "id": item.get("id"),
        "type_id": item.get("typeId") or item.get("type_id") or item.get("diaperTypeId"),
        "name": item.get("name") or item.get("typeName") or type_obj.get("name"),
        "state": item.get("state"),
        "status": item.get("status"),
        "needWash": item.get("needWash"),
        "need_wash": item.get("need_wash"),
        "needs_wash": _needs_wash(item),
    }

def _group_stock_by_brand(items: list[DiapStashStockItem]) -> list[dict[str, Any]]:
    """Group stock batches by brand."""
    grouped: dict[str, float] = {}
    for item in items:
        if item.quantity is None:
            continue
        brand = item.brand or "Unknown"
        grouped[brand] = grouped.get(brand, 0) + float(item.quantity)
    return [
        {"brand": brand, "available": _normalize_number(available)}
        for brand, available in sorted(grouped.items(), key=lambda row: (-row[1], row[0].lower()))
    ]


def _group_stock_by_type(items: list[DiapStashStockItem]) -> list[dict[str, Any]]:
    """Group stock batches by diaper type, size, variant and location."""
    grouped: dict[tuple[Any, str | None, str | None], dict[str, Any]] = {}
    for item in items:
        if item.quantity is None:
            continue
        key = (item.type_id, item.size, item.variant)
        row = grouped.setdefault(
            key,
            {
                "label": item.label,
                "available": 0.0,
                "type_id": item.type_id,
                "brand": item.brand,
                "diaper_name": item.diaper_name,
                "size": item.size,
                "variant": item.variant,
                "catalog_url": item.catalog_url,
                "add_url": item.add_url,
                "image_url": item.image_url,
                "_locations": {},
            },
        )
        quantity = float(item.quantity)
        row["available"] += quantity
        location_key = str(item.stock_id) if item.stock_id is not None else "unknown"
        location_name = item.stock_name or (str(item.stock_id) if item.stock_id is not None else "Unknown")
        locations = row["_locations"]
        location = locations.setdefault(
            location_key,
            {
                "stock_id": item.stock_id,
                "stock_name": location_name,
                "available": 0.0,
            },
        )
        location["available"] += quantity
    out = []
    for row in grouped.values():
        row = dict(row)
        row["available"] = _normalize_number(row["available"])
        locations = []
        for location in row.pop("_locations", {}).values():
            location = dict(location)
            location["available"] = _normalize_number(location["available"])
            locations.append(location)
        locations.sort(key=lambda item: str(item.get("stock_name") or "").lower())
        row["stock_locations"] = locations
        row["stock_location_names"] = [
            str(location.get("stock_name"))
            for location in locations
            if location.get("stock_name")
        ]
        out.append(row)
    return sorted(out, key=lambda row: (-float(row["available"]), str(row.get("label") or "").lower()))


def _normalize_number(value: float) -> int | float:
    """Return int for integer-like floats."""
    return int(value) if float(value).is_integer() else value


def _add_url(type_id: int | str | None, size: str | None = None) -> str | None:
    """Return DiapStash add-to-stock URL."""
    if type_id is None:
        return None
    url = ADD_URL.format(type_id=type_id)
    if size:
        url += f"&size={size}"
    return url


def _build_url(url: str, query: dict[str, Any] | None = None) -> str:
    """Build URL with query params."""
    if not query:
        return url
    from yarl import URL

    return str(URL(url).with_query({key: str(value) for key, value in query.items()}))


def _parse_time(value: str | None) -> datetime | None:
    """Parse an ISO timestamp to UTC."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _find_current_change(changes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the most recent active change."""
    active = [change for change in changes if change.get("endTime") is None and change.get("diapers")]
    if not active:
        return None
    return max(active, key=lambda change: _parse_time(change.get("startTime")) or datetime.min.replace(tzinfo=timezone.utc))


def _extract_quantity(item: dict[str, Any]) -> int | float | None:
    """Extract remaining count from a disposable stock batch."""
    for key in ("left", "quantity", "count", "remaining", "amount", "available"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return value
    return None


def _format_number(value: int | float) -> str:
    """Format an integer-like number cleanly."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _humanize_minutes(total: int) -> str:
    """Compact duration format."""
    if total < 60:
        return f"{total}m"
    days = total // 1440
    hours = (total % 1440) // 60
    mins = total % 60
    if days > 0:
        return f"{days}d {hours}h"
    return f"{hours}h {mins}m"


def _build_streak(changes_desc: list[dict[str, Any]], now: datetime, gap_threshold_min: int = 15) -> tuple[int, int]:
    """Build current wearing streak from recent changes."""
    count = 0
    duration = 0
    prev_start: datetime | None = None
    sorted_changes = sorted(
        changes_desc,
        key=lambda change: _parse_time(change.get("startTime")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    for change in sorted_changes:
        start = _parse_time(change.get("startTime"))
        if not start:
            continue
        if prev_start:
            end = _parse_time(change.get("endTime")) or now
            gap_min = (prev_start - end).total_seconds() / 60
            if gap_min > gap_threshold_min:
                break
        end = _parse_time(change.get("endTime")) or now
        count += 1
        duration += max(0, int((end - start).total_seconds() / 60))
        prev_start = start
    return count, duration


def _brand_name_from_type(type_data: dict[str, Any]) -> str | None:
    """Extract a brand name from official type data."""
    for key in ("brandName", "brand_name", "brand"):
        value = type_data.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            name = value.get("name")
            if isinstance(name, str) and name:
                return name
    return None


def _image_url_from_type(type_data: dict[str, Any]) -> str | None:
    """Extract an image URL from official type data."""
    primary = type_data.get("primaryImage")
    if isinstance(primary, dict) and primary.get("url"):
        return str(primary["url"])
    images = type_data.get("images")
    if isinstance(images, list) and images and isinstance(images[0], dict) and images[0].get("url"):
        return str(images[0]["url"])
    return None
