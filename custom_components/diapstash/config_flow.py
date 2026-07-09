"""Config flow for DiapStash."""

from __future__ import annotations

from hashlib import sha1
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import callback
from homeassistant.util import slugify
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    async_get_implementations,
    async_get_config_entry_implementation,
)

from .application_credentials import DiapStashOAuth2Implementation
from .token import sub_from_flow_data

from .const import (
    CONF_ENABLE_DYNAMIC_STOCK_ENTITIES,
    CONF_ENABLE_LOW_STOCK_BINARY_SENSORS,
    CONF_ENABLE_STATS,
    CONF_ENABLE_STOCK,
    CONF_LOW_STOCK_THRESHOLD,
    CONF_LIVE_DURATION_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_ENABLE_DYNAMIC_STOCK_ENTITIES,
    DEFAULT_ENABLE_LOW_STOCK_BINARY_SENSORS,
    DEFAULT_ENABLE_STATS,
    DEFAULT_ENABLE_STOCK,
    DEFAULT_LOW_STOCK_THRESHOLD,
    DEFAULT_LIVE_DURATION_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DATA_USE_ACCOUNT_DEVICE_IDENTIFIER,
    DIAPSTASH_API_CLIENT_PREFILL_URL,
    OAUTH2_REDIRECT_URL,
    OAUTH2_SCOPES,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)

_LOGGER = logging.getLogger(__name__)


class DiapStashConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle a DiapStash config flow."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> DiapStashOptionsFlow:
        """Return the options flow."""
        return DiapStashOptionsFlow()

    def __init__(self) -> None:
        """Initialize the flow."""
        super().__init__()
        self._manual_credentials: dict[str, str] = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Collect DiapStash API credentials for this account."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("name", default="DiapStash"): str,
                        vol.Required("client_id"): str,
                        vol.Required("client_secret"): str,
                    }
                ),
                description_placeholders={
                    "api_client_url": DIAPSTASH_API_CLIENT_PREFILL_URL,
                    "redirect_url": OAUTH2_REDIRECT_URL,
                    "scopes": OAUTH2_SCOPES,
                },
            )

        name = str(user_input["name"]).strip() or "DiapStash"
        client_id = str(user_input["client_id"]).strip()
        client_secret = str(user_input["client_secret"]).strip()
        auth_domain = f"{DOMAIN}_{slugify(name)}_{sha1(client_id.encode('utf-8')).hexdigest()[:8]}"

        self._manual_credentials = {
            "credential_name": name,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        self.flow_impl = DiapStashOAuth2Implementation(
            self.hass,
            auth_domain,
            client_id,
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
            client_secret=client_secret,
            code_verifier_length=128,
        )
        return await self.async_step_auth()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthentication when DiapStash tokens are invalid or expired."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Ask the user to reauthenticate an existing DiapStash account."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )

        entry = self._get_reauth_entry()

        if entry.data.get("client_id") and entry.data.get("client_secret"):
            self._manual_credentials = {
                "credential_name": str(entry.data.get("credential_name") or entry.title or "DiapStash"),
                "client_id": str(entry.data["client_id"]),
                "client_secret": str(entry.data["client_secret"]),
            }
            self.flow_impl = DiapStashOAuth2Implementation(
                self.hass,
                str(entry.data.get("auth_implementation") or f"{DOMAIN}_{entry.entry_id}"),
                str(entry.data["client_id"]),
                authorize_url=OAUTH2_AUTHORIZE,
                token_url=OAUTH2_TOKEN,
                client_secret=str(entry.data["client_secret"]),
                code_verifier_length=128,
            )
            return await self.async_step_auth()

        try:
            self.flow_impl = await async_get_config_entry_implementation(self.hass, entry)
        except ImplementationUnavailableError as err:
            self.logger.error("OAuth2 implementation unavailable during reauth: %s", err)
            return self.async_abort(reason="oauth_implementation_unavailable")

        return await self.async_step_auth()


    async def async_step_pick_implementation(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Let the user explicitly select the DiapStash API credentials."""
        try:
            implementations = await async_get_implementations(self.hass, self.DOMAIN)
        except ImplementationUnavailableError as err:
            self.logger.error("No OAuth2 implementations available: %s", err)
            return self.async_abort(reason="oauth_implementation_unavailable")

        if user_input is not None:
            self.flow_impl = implementations[user_input["implementation"]]
            return await self.async_step_auth()

        if not implementations:
            return self.async_abort(reason="missing_configuration")

        return self.async_show_form(
            step_id="pick_implementation",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "implementation",
                        default=list(implementations)[0],
                    ): vol.In({key: impl.name for key, impl in implementations.items()})
                }
            ),
        )


    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Create an entry for the flow."""
        account_id = sub_from_flow_data(data)
        if not account_id:
            _LOGGER.warning("DiapStash access token does not contain a sub claim; falling back to single-account mode")
            account_id = DOMAIN

        if self._manual_credentials:
            data = {**data, **self._manual_credentials}

        auth_implementation = data.get("auth_implementation")

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            await self.async_set_unique_id(account_id)
            self._abort_if_unique_id_mismatch(reason="wrong_account")

            new_data = {**dict(reauth_entry.data), **dict(data)}
            if self._manual_credentials:
                new_data.update(self._manual_credentials)
            new_data["account_id"] = account_id
            new_data.setdefault(
                DATA_USE_ACCOUNT_DEVICE_IDENTIFIER,
                reauth_entry.data.get(DATA_USE_ACCOUNT_DEVICE_IDENTIFIER, True),
            )

            return self.async_update_reload_and_abort(
                reauth_entry,
                data_updates=new_data,
            )

        # Be explicit here in addition to Home Assistant's unique_id check.
        # Existing entries created before v0.10 may have been migrated to the
        # token subject and store it in entry.data["account_id"]. Checking both
        # fields prevents adding the same DiapStash account twice.
        for entry in self._async_current_entries():
            if entry.unique_id == account_id or entry.data.get("account_id") == account_id:
                return self.async_abort(reason="already_configured")
            if auth_implementation and entry.data.get("auth_implementation") == auth_implementation:
                return self.async_abort(reason="credentials_already_configured")
            if data.get("client_id") and entry.data.get("client_id") == data.get("client_id"):
                return self.async_abort(reason="credentials_already_configured")

        await self.async_set_unique_id(account_id)
        self._abort_if_unique_id_configured()

        data = dict(data)
        data["account_id"] = account_id
        data[DATA_USE_ACCOUNT_DEVICE_IDENTIFIER] = True
        title = str(data.get("credential_name") or "DiapStash")
        if not title.lower().startswith("diapstash"):
            title = f"DiapStash - {title}"
        return self.async_create_entry(
            title=title,
            data=data,
            options=_default_options(),
        )


class DiapStashOptionsFlow(config_entries.OptionsFlow):
    """Handle DiapStash options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage DiapStash options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {**_default_options(), **dict(self.config_entry.options)}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=options[CONF_SCAN_INTERVAL],
                    ): vol.All(vol.Coerce(int), vol.In([15, 30, 60])),
                    vol.Optional(
                        CONF_ENABLE_STOCK,
                        default=options[CONF_ENABLE_STOCK],
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_STATS,
                        default=options[CONF_ENABLE_STATS],
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_DYNAMIC_STOCK_ENTITIES,
                        default=options[CONF_ENABLE_DYNAMIC_STOCK_ENTITIES],
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_LOW_STOCK_BINARY_SENSORS,
                        default=options[CONF_ENABLE_LOW_STOCK_BINARY_SENSORS],
                    ): bool,
                    vol.Optional(
                        CONF_LOW_STOCK_THRESHOLD,
                        default=options[CONF_LOW_STOCK_THRESHOLD],
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=999)),
                    vol.Optional(
                        CONF_LIVE_DURATION_INTERVAL,
                        default=options[CONF_LIVE_DURATION_INTERVAL],
                    ): vol.All(vol.Coerce(int), vol.In([0, 1, 5, 15])),
                }
            ),
        )


def _default_options() -> dict[str, Any]:
    """Return default integration options."""
    return {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_ENABLE_STOCK: DEFAULT_ENABLE_STOCK,
        CONF_ENABLE_STATS: DEFAULT_ENABLE_STATS,
        CONF_ENABLE_DYNAMIC_STOCK_ENTITIES: DEFAULT_ENABLE_DYNAMIC_STOCK_ENTITIES,
        CONF_ENABLE_LOW_STOCK_BINARY_SENSORS: DEFAULT_ENABLE_LOW_STOCK_BINARY_SENSORS,
        CONF_LOW_STOCK_THRESHOLD: DEFAULT_LOW_STOCK_THRESHOLD,
        CONF_LIVE_DURATION_INTERVAL: DEFAULT_LIVE_DURATION_INTERVAL,
    }
