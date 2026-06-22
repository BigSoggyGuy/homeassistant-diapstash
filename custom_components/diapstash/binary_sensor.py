"""Binary sensor platform for DiapStash."""

from __future__ import annotations

from hashlib import sha1

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import (
    CONF_ENABLE_LOW_STOCK_BINARY_SENSORS,
    CONF_LOW_STOCK_THRESHOLD,
    DEFAULT_ENABLE_LOW_STOCK_BINARY_SENSORS,
    DEFAULT_LOW_STOCK_THRESHOLD,
    DOMAIN,
)
from .coordinator import DiapStashCoordinator
from .entity import DiapStashEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DiapStash binary sensors."""
    coordinator: DiapStashCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DiapStashWearingBinarySensor(coordinator, entry.entry_id)])

    if not entry.options.get(
        CONF_ENABLE_LOW_STOCK_BINARY_SENSORS,
        DEFAULT_ENABLE_LOW_STOCK_BINARY_SENSORS,
    ):
        return

    known_detail_ids: set[str] = set()

    @callback
    def add_low_stock_entities() -> None:
        """Add low-stock sensors for known stock types."""
        data = coordinator.data
        if data is None or data.stock_error is not None:
            return

        entities: list[BinarySensorEntity] = []
        for stock_type in data.stock_by_type:
            key = _stock_type_key(stock_type)
            unique = f"{entry.entry_id}_low_stock_{key}"
            if unique in known_detail_ids:
                continue
            known_detail_ids.add(unique)
            entities.append(DiapStashLowStockBinarySensor(coordinator, unique, stock_type, entry))

        if entities:
            async_add_entities(entities)

    add_low_stock_entities()

    @callback
    def coordinator_updated() -> None:
        add_low_stock_entities()

    entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))


class DiapStashWearingBinarySensor(DiapStashEntity, BinarySensorEntity):
    """Wearing state binary sensor."""

    _attr_translation_key = "wearing"
    _attr_icon = "mdi:human-baby-changing-table"

    def __init__(self, coordinator: DiapStashCoordinator, entry_id: str) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_wearing"
        self._attr_suggested_object_id = "diapstash_wearing"

    @property
    def is_on(self) -> bool | None:
        """Return true if a diaper is currently worn."""
        data = self.coordinator.data
        if data is None:
            return None
        return data.wearing


class DiapStashLowStockBinarySensor(DiapStashEntity, BinarySensorEntity):
    """Low-stock binary sensor for a stock type."""

    _attr_icon = "mdi:alert-circle-outline"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: DiapStashCoordinator,
        unique_id: str,
        stock_type: dict[str, object],
        entry: ConfigEntry,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self.key = _stock_type_key(stock_type)
        self._attr_suggested_object_id = f"diapstash_low_stock_{self.key}"
        self.entry = entry
        label = str(stock_type.get("label") or self.key)
        self._attr_translation_key = "low_stock_type"
        self._attr_translation_placeholders = {"label": label}

    @property
    def is_on(self) -> bool | None:
        """Return true if stock is at or below threshold."""
        row = self._current_row()
        if row is None:
            return False
        available = row.get("available") or 0
        threshold = int(self.entry.options.get(CONF_LOW_STOCK_THRESHOLD, DEFAULT_LOW_STOCK_THRESHOLD))
        try:
            return float(available) <= threshold
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return low-stock details."""
        row = self._current_row()
        threshold = int(self.entry.options.get(CONF_LOW_STOCK_THRESHOLD, DEFAULT_LOW_STOCK_THRESHOLD))
        if row is None:
            return {"stock_key": self.key, "threshold": threshold}
        return {**dict(row), "threshold": threshold}

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
