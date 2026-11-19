"""Diagnostics support for DiapStash."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    "access_token",
    "refresh_token",
    "client_secret",
    "token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    token = entry.data.get("token")
    token_data = token if isinstance(token, dict) else {}
    token_type = str(token_data.get("token_type") or "unknown")
    if token_type.casefold() not in {"bearer", "dpop"}:
        token_type = "unknown"

    data: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "account_id": entry.data.get("account_id"),
        "unique_id": entry.unique_id,
        "use_account_device_identifier": entry.data.get("use_account_device_identifier"),
        "authentication": {
            "client_id_configured": bool(entry.data.get("client_id")),
            "client_secret_configured": bool(entry.data.get("client_secret")),
            "refresh_token_present": bool(token_data.get("refresh_token")),
            "token_type": token_type,
            "expires_in": token_data.get("expires_in"),
            "expires_at": token_data.get("expires_at"),
        },
    }

    if coordinator:
        implementation = coordinator.api.oauth_session.implementation
        data["authentication"].update(
            {
                "last_refresh_at": getattr(implementation, "last_refresh_at", None),
                "last_refresh_token_rotated": getattr(
                    implementation,
                    "last_refresh_token_rotated",
                    None,
                ),
                "last_refresh_error_code": getattr(
                    implementation,
                    "last_refresh_error_code",
                    None,
                ),
                "last_refresh_error_status": getattr(
                    implementation,
                    "last_refresh_error_status",
                    None,
                ),
            }
        )

    if coordinator and coordinator.data:
        data["coordinator_data"] = {
            "wearing": coordinator.data.wearing,
            "label": coordinator.data.label,
            "type_id": coordinator.data.type_id,
            "debug_count": coordinator.data.debug_count,
            "debug_total_count": coordinator.data.debug_total_count,
            "debug_url": coordinator.data.debug_url,
            "stock_total": coordinator.data.stock_total,
            "stock_entries": coordinator.data.stock_entries,
            "stock_error": coordinator.data.stock_error,
            "stock_debug_url": coordinator.data.stock_debug_url,
        }

    return data
