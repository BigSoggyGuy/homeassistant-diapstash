"""Base entity for DiapStash."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_USE_ACCOUNT_DEVICE_IDENTIFIER, DOMAIN, NAME
from .coordinator import DiapStashCoordinator


class DiapStashEntity(CoordinatorEntity[DiapStashCoordinator]):
    """Base DiapStash entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DiapStashCoordinator) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        if coordinator.entry.data.get(DATA_USE_ACCOUNT_DEVICE_IDENTIFIER):
            device_identifier = coordinator.entry.unique_id or coordinator.entry.entry_id
        else:
            device_identifier = "cloud"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_identifier)},
            manufacturer="DiapStash",
            name=coordinator.entry.title or NAME,
        )
