"""Data update coordinator for DiapStash."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import DiapStashApiClient, DiapStashCurrentDiaper
from .const import (
    CONF_ENABLE_STATS,
    CONF_ENABLE_STOCK,
    CONF_LOW_STOCK_THRESHOLD,
    CONF_SCAN_INTERVAL,
    DEFAULT_ENABLE_STATS,
    DEFAULT_ENABLE_STOCK,
    DEFAULT_LOW_STOCK_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class DiapStashCoordinator(DataUpdateCoordinator[DiapStashCurrentDiaper]):
    """DiapStash data update coordinator."""

    def __init__(self, hass: HomeAssistant, api: DiapStashApiClient, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=self.scan_interval_minutes),
        )
        self.api = api

    @property
    def scan_interval_minutes(self) -> int:
        """Return configured scan interval."""
        return int(self.entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    @property
    def enable_stock(self) -> bool:
        """Return whether stock polling is enabled."""
        return bool(self.entry.options.get(CONF_ENABLE_STOCK, DEFAULT_ENABLE_STOCK))

    @property
    def enable_stats(self) -> bool:
        """Return whether statistics are enabled."""
        return bool(self.entry.options.get(CONF_ENABLE_STATS, DEFAULT_ENABLE_STATS))

    @property
    def low_stock_threshold(self) -> int:
        """Return configured low-stock threshold fallback."""
        return int(self.entry.options.get(CONF_LOW_STOCK_THRESHOLD, DEFAULT_LOW_STOCK_THRESHOLD))

    async def _async_update_data(self) -> DiapStashCurrentDiaper:
        """Fetch data from DiapStash."""
        self.update_interval = timedelta(minutes=self.scan_interval_minutes)
        return await self.api.async_get_current_diaper(
            enable_stock=self.enable_stock,
            enable_stats=self.enable_stats,
            low_stock_threshold=self.low_stock_threshold,
        )
