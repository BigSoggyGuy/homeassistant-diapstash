"""Sensor platform for DiapStash."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha1

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import slugify

from .api import DiapStashCurrentDiaper, DiapStashStockItem, DiapStashStockLocation
from .const import (
    ATTR_BRAND,
    ATTR_CATALOG_URL,
    ATTR_CHANGE_ID,
    ATTR_DIAPER_NAME,
    ATTR_DURATION_TEXT,
    ATTR_IMAGE_URL,
    ATTR_SIZE,
    ATTR_START_TIME,
    ATTR_TYPE_ID,
    ATTR_VARIANT,
    ATTR_WEARING,
    CONF_ENABLE_DYNAMIC_STOCK_ENTITIES,
    CONF_LIVE_DURATION_INTERVAL,
    DEFAULT_ENABLE_DYNAMIC_STOCK_ENTITIES,
    DEFAULT_LIVE_DURATION_INTERVAL,
    DOMAIN,
)
from .coordinator import DiapStashCoordinator
from .entity import DiapStashEntity


@dataclass(frozen=True, kw_only=True)
class DiapStashSensorEntityDescription(SensorEntityDescription):
    """DiapStash sensor description."""

    value_fn: Callable[[DiapStashCurrentDiaper], str | int | float | None] | None = None


SENSOR_DESCRIPTIONS: tuple[DiapStashSensorEntityDescription, ...] = (
    DiapStashSensorEntityDescription(
        key="current_diaper",
        translation_key="current_diaper",
        icon="mdi:human-baby-changing-table",
        value_fn=lambda data: data.label,
    ),
    DiapStashSensorEntityDescription(
        key="wearing_duration",
        translation_key="wearing_duration",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data: data.duration_minutes,
    ),
    DiapStashSensorEntityDescription(
        key="wearing_duration_text",
        translation_key="wearing_duration_text",
        icon="mdi:timer-outline",
        value_fn=lambda data: data.duration_text,
    ),
    DiapStashSensorEntityDescription(
        key="stock_overview",
        translation_key="stock_overview",
        icon="mdi:package-variant-closed",
        value_fn=lambda data: data.stock_label,
    ),
    DiapStashSensorEntityDescription(
        key="stock_total",
        translation_key="stock_total",
        icon="mdi:counter",
        native_unit_of_measurement="diapers",
        value_fn=lambda data: data.stock_total,
    ),
    DiapStashSensorEntityDescription(
        key="stock_entries",
        translation_key="stock_entries",
        icon="mdi:format-list-numbered",
        native_unit_of_measurement="entries",
        value_fn=lambda data: data.stock_entries,
    ),
    DiapStashSensorEntityDescription(
        key="stock_to_wash",
        translation_key="stock_to_wash",
        icon="mdi:washing-machine",
        native_unit_of_measurement="diapers",
        value_fn=lambda data: data.stock_to_wash,
    ),
    DiapStashSensorEntityDescription(
        key="stock_brands",
        translation_key="stock_brands",
        icon="mdi:tag-multiple",
        native_unit_of_measurement="brands",
        value_fn=lambda data: len(data.stock_by_brand) if data.stock_error is None else None,
    ),
    DiapStashSensorEntityDescription(
        key="stock_types",
        translation_key="stock_types",
        icon="mdi:package-variant",
        native_unit_of_measurement="types",
        value_fn=lambda data: len(data.stock_by_type) if data.stock_error is None else None,
    ),
    DiapStashSensorEntityDescription(
        key="stock_locations",
        translation_key="stock_locations",
        icon="mdi:warehouse",
        native_unit_of_measurement="locations",
        value_fn=lambda data: data.stock_locations_count if data.stock_error is None else None,
    ),
    DiapStashSensorEntityDescription(
        key="month_changes",
        translation_key="month_changes",
        icon="mdi:calendar-month",
        native_unit_of_measurement="changes",
        value_fn=lambda data: data.month_count,
    ),
    DiapStashSensorEntityDescription(
        key="year_changes",
        translation_key="year_changes",
        icon="mdi:calendar",
        native_unit_of_measurement="changes",
        value_fn=lambda data: data.year_count,
    ),
    DiapStashSensorEntityDescription(
        key="total_changes",
        translation_key="total_changes",
        icon="mdi:counter",
        native_unit_of_measurement="changes",
        value_fn=lambda data: data.total_changes,
    ),
    DiapStashSensorEntityDescription(
        key="current_streak",
        translation_key="current_streak",
        icon="mdi:fire",
        native_unit_of_measurement="changes",
        value_fn=lambda data: data.streak_count,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DiapStash sensors."""
    coordinator: DiapStashCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        DiapStashSensor(coordinator, entry.entry_id, description)
        for description in SENSOR_DESCRIPTIONS
    )

    if not entry.options.get(CONF_ENABLE_DYNAMIC_STOCK_ENTITIES, DEFAULT_ENABLE_DYNAMIC_STOCK_ENTITIES):
        return

    known_detail_ids: set[str] = set()

    @callback
    def add_stock_detail_entities() -> None:
        """Add per-brand and per-type stock sensors discovered in coordinator data."""
        data = coordinator.data
        if data is None or data.stock_error is not None:
            return

        entities: list[SensorEntity] = []

        for brand in data.stock_by_brand:
            brand_name = str(brand.get("brand") or "Unknown")
            unique = f"{entry.entry_id}_stock_brand_{slugify(brand_name)}"
            if unique in known_detail_ids:
                continue
            known_detail_ids.add(unique)
            entities.append(DiapStashStockBrandSensor(coordinator, unique, brand_name))

        for stock_type in data.stock_by_type:
            key = _stock_type_key(stock_type)
            unique = f"{entry.entry_id}_stock_type_{key}"
            if unique in known_detail_ids:
                continue
            known_detail_ids.add(unique)
            entities.append(DiapStashStockTypeSensor(coordinator, unique, stock_type))

        if entities:
            async_add_entities(entities)

    add_stock_detail_entities()

    @callback
    def coordinator_updated() -> None:
        add_stock_detail_entities()

    entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))


class DiapStashSensor(DiapStashEntity, SensorEntity):
    """DiapStash summary sensor."""

    entity_description: DiapStashSensorEntityDescription

    def __init__(
        self,
        coordinator: DiapStashCoordinator,
        entry_id: str,
        description: DiapStashSensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_suggested_object_id = f"diapstash_{description.key}"
        if description.key == "wearing_duration_text":
            self._attr_entity_registry_enabled_default = False

    async def async_added_to_hass(self) -> None:
        """Register local updates for duration related sensor state/attributes."""
        await super().async_added_to_hass()
        if self.entity_description.key in {"current_diaper", "wearing_duration", "wearing_duration_text"}:
            interval = int(
                self.coordinator.entry.options.get(
                    CONF_LIVE_DURATION_INTERVAL,
                    DEFAULT_LIVE_DURATION_INTERVAL,
                )
            )
            if interval <= 0:
                return
            self.async_on_remove(
                async_track_time_interval(
                    self.hass,
                    self._async_update_local_duration,
                    timedelta(minutes=interval),
                )
            )

    @callback
    def _async_update_local_duration(self, _now) -> None:
        """Refresh local duration state/attributes without polling the API."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | int | float | None:
        """Return native value."""
        data = self.coordinator.data
        if data is None or self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(data)


    @property
    def entity_picture(self) -> str | None:
        """Return entity picture for the current diaper when available."""
        if self.entity_description.key != "current_diaper":
            return None
        data = self.coordinator.data
        if data is None:
            return None
        return data.image_url

    @property
    def available(self) -> bool:
        """Return availability."""
        if not super().available:
            return False
        data = self.coordinator.data
        if data is None:
            return False

        if self.entity_description.key == "stock_overview":
            return True

        if self.entity_description.key == "stock_to_wash":
            return data.stock_error is None and data.stock_to_wash is not None

        if self.entity_description.key in {"stock_total", "stock_entries", "stock_brands", "stock_types", "stock_locations"}:
            return data.stock_error is None and data.stock_total is not None

        return True

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return state attributes."""
        data = self.coordinator.data
        if data is None:
            return {}

        if self.entity_description.key == "current_diaper":
            return {
                ATTR_WEARING: data.wearing,
                ATTR_DIAPER_NAME: data.diaper_name,
                ATTR_BRAND: data.brand,
                ATTR_SIZE: data.size,
                ATTR_VARIANT: data.variant,
                ATTR_START_TIME: data.start_time,
                ATTR_DURATION_TEXT: data.duration_text,
                "duration_minutes": data.duration_minutes,
                ATTR_CHANGE_ID: data.change_id,
                ATTR_TYPE_ID: data.type_id,
                ATTR_CATALOG_URL: data.catalog_url,
                ATTR_IMAGE_URL: data.image_url,
                "debug_count": data.debug_count,
                "debug_total_count": data.debug_total_count,
                "debug_url": data.debug_url,
                "month_count": data.month_count,
                "year_count": data.year_count,
                "total_changes": data.total_changes,
                "streak_count": data.streak_count,
                "streak_minutes": data.streak_minutes,
                "streak_text": data.streak_text,
            }

        if self.entity_description.key == "stock_overview":
            return {
                "stock_total": data.stock_total,
                "stock_entries": data.stock_entries,
                "stock_items": [_stock_item_to_dict(item) for item in data.stock_items],
                "stock_locations": [_stock_location_to_dict(location) for location in data.stock_locations],
                "stock_locations_count": data.stock_locations_count,
                "stock_to_wash": data.stock_to_wash,
                "stock_reusables": data.stock_reusables,
                "stock_by_brand": data.stock_by_brand,
                "stock_by_type": data.stock_by_type,
                "stock_debug_url": data.stock_debug_url,
                "stock_error": data.stock_error,
            }

        if self.entity_description.key == "stock_to_wash":
            return {
                "stock_reusables": data.stock_reusables,
                "stock_error": data.stock_error,
            }

        if self.entity_description.key == "stock_brands":
            return {
                "brands": data.stock_by_brand,
                "total": data.stock_total,
                "stock_error": data.stock_error,
            }

        if self.entity_description.key == "stock_types":
            return {
                "types": data.stock_by_type,
                "total": data.stock_total,
                "stock_error": data.stock_error,
            }

        if self.entity_description.key == "stock_locations":
            return {
                "locations": [_stock_location_to_dict(location) for location in data.stock_locations],
                "total": data.stock_total,
                "stock_error": data.stock_error,
            }

        return {}


class DiapStashStockBrandSensor(DiapStashEntity, SensorEntity):
    """Per-brand stock sensor."""

    _attr_icon = "mdi:tag"
    _attr_native_unit_of_measurement = "diapers"

    def __init__(self, coordinator: DiapStashCoordinator, unique_id: str, brand: str) -> None:
        """Initialize brand stock sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_suggested_object_id = f"diapstash_stock_brand_{slugify(brand)}"
        self._attr_translation_key = "stock_brand_detail"
        self._attr_translation_placeholders = {"brand": brand}
        self.brand = brand

    @property
    def native_value(self) -> int | float:
        """Return available diapers for this brand."""
        data = self.coordinator.data
        if data is None:
            return 0
        for row in data.stock_by_brand:
            if row.get("brand") == self.brand:
                return row.get("available") or 0
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return brand details."""
        data = self.coordinator.data
        if data is None:
            return {"brand": self.brand}
        return {
            "brand": self.brand,
            "types": [row for row in data.stock_by_type if row.get("brand") == self.brand],
            "total": self.native_value,
        }


class DiapStashStockTypeSensor(DiapStashEntity, SensorEntity):
    """Per-diaper-type stock sensor."""

    _attr_icon = "mdi:package-variant"
    _attr_native_unit_of_measurement = "diapers"

    def __init__(self, coordinator: DiapStashCoordinator, unique_id: str, stock_type: dict[str, object]) -> None:
        """Initialize type stock sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self.key = _stock_type_key(stock_type)
        self._attr_suggested_object_id = f"diapstash_stock_type_{self.key}"
        label = str(stock_type.get("label") or self.key)
        self._attr_translation_key = "stock_type_detail"
        self._attr_translation_placeholders = {"label": label}

    @property
    def native_value(self) -> int | float:
        """Return available diapers for this diaper type."""
        row = self._current_row()
        if row is None:
            return 0
        return row.get("available") or 0


    @property
    def entity_picture(self) -> str | None:
        """Return stock type image when available."""
        row = self._current_row()
        if row is None:
            return None
        image_url = row.get("image_url")
        return str(image_url) if image_url else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return diaper type details."""
        row = self._current_row()
        if row is None:
            return {"stock_key": self.key}
        return dict(row)

    def _current_row(self) -> dict[str, object] | None:
        """Return current row for this type."""
        data = self.coordinator.data
        if data is None:
            return None
        for row in data.stock_by_type:
            if _stock_type_key(row) == self.key:
                return row
        return None


def _stock_type_key(stock_type: dict[str, object]) -> str:
    """Return a stable key for a stock type row."""
    type_id = stock_type.get("type_id")
    size = stock_type.get("size") or ""
    variant = stock_type.get("variant") or ""
    if type_id is not None:
        return slugify(f"{type_id}_{size}_{variant}")
    label = str(stock_type.get("label") or "unknown")
    digest = sha1(label.encode("utf-8")).hexdigest()[:8]
    return f"{slugify(label)}_{digest}"


def _stock_item_to_dict(item: DiapStashStockItem) -> dict[str, object]:
    """Return stock item as a serializable dict."""
    return {
        "label": item.label,
        "quantity": item.quantity,
        "type_id": item.type_id,
        "brand": item.brand,
        "diaper_name": item.diaper_name,
        "size": item.size,
        "variant": item.variant,
        "catalog_url": item.catalog_url,
        "add_url": item.add_url,
        "image_url": item.image_url,
        "raw_id": item.raw_id,
        "stock_id": item.stock_id,
        "stock_name": item.stock_name,
    }


def _stock_location_to_dict(location: DiapStashStockLocation) -> dict[str, object]:
    """Return stock location as a serializable dict."""
    return {
        "id": location.id,
        "name": location.name,
        "available": location.available,
        "threshold": location.threshold,
        "low": location.low,
        "masked": location.masked,
        "principal": location.principal,
        "order": location.order,
    }
