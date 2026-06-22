"""DiapStash integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import DiapStashApiClient
from .application_credentials import DiapStashOAuth2Implementation
from .const import (
    DATA_USE_ACCOUNT_DEVICE_IDENTIFIER,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    PLATFORMS,
)
from .coordinator import DiapStashCoordinator
from .token import sub_from_flow_data

DiapStashConfigEntry = ConfigEntry[DiapStashCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DiapStashConfigEntry) -> bool:
    """Set up DiapStash from a config entry."""
    if entry.data.get("client_id") and entry.data.get("client_secret"):
        implementation = DiapStashOAuth2Implementation(
            hass,
            entry.data["auth_implementation"],
            entry.data["client_id"],
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
            client_secret=entry.data["client_secret"],
            code_verifier_length=128,
        )
    else:
        implementation = await async_get_config_entry_implementation(hass, entry)
    oauth_session = OAuth2Session(hass, entry, implementation)

    await _async_migrate_unique_id(hass, entry)

    api = DiapStashApiClient(hass, oauth_session)
    coordinator = DiapStashCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_migrate_unique_id(hass: HomeAssistant, entry: DiapStashConfigEntry) -> None:
    """Migrate old single-account config entries to the token subject unique ID."""
    account_id = sub_from_flow_data(entry.data)
    if not account_id:
        return
    new_data = dict(entry.data)
    changed = False

    # Entries that already existed before the multi-account device split should
    # keep the legacy device identifier so existing entities stay on the same
    # Home Assistant device. Newly added accounts store this flag as True in
    # the config flow and get their own account-specific device.
    if DATA_USE_ACCOUNT_DEVICE_IDENTIFIER not in new_data:
        new_data[DATA_USE_ACCOUNT_DEVICE_IDENTIFIER] = False
        changed = True

    if new_data.get("account_id") != account_id:
        new_data["account_id"] = account_id
        changed = True

    if entry.unique_id in (None, DOMAIN):
        hass.config_entries.async_update_entry(entry, unique_id=account_id, data=new_data)
    elif changed:
        hass.config_entries.async_update_entry(entry, data=new_data)


async def _async_update_options(hass: HomeAssistant, entry: DiapStashConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: DiapStashConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
