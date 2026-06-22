"""Application credentials support for DiapStash."""

from __future__ import annotations

import json
import logging
import time
from http import HTTPStatus
from typing import Any, cast

from aiohttp import ClientError, ClientResponseError
from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    LocalOAuth2ImplementationWithPkce,
)

from .const import COMMON_HEADERS, DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_SCOPES, OAUTH2_TOKEN

_LOGGER = logging.getLogger(__name__)


class DiapStashOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """DiapStash OAuth implementation with PKCE, scopes and integration headers."""

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Return extra authorize data."""
        data: dict[str, str] = {
            "scope": OAUTH2_SCOPES,
            "prompt": "login consent",
        }
        data.update(super().extra_authorize_data)
        return data

    async def _token_request(self, data: dict[str, Any]) -> dict[str, Any]:
        """Make a token request with DiapStash integration headers."""
        session = async_get_clientsession(self.hass)

        data["client_id"] = self.client_id
        if self.client_secret:
            data["client_secret"] = self.client_secret

        _LOGGER.debug("Sending DiapStash token request to %s", self.token_url)

        try:
            resp = await session.post(
                self.token_url,
                data=data,
                headers={
                    **COMMON_HEADERS,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            if resp.status >= 400:
                error_body = ""
                try:
                    error_body = await resp.text()
                    error_data = json.loads(error_body)
                    error_code = error_data.get("error", "unknown error")
                    error_description = error_data.get("error_description")
                    detail = (
                        f"{error_code}: {error_description}"
                        if error_description
                        else str(error_code)
                    )
                except (ClientError, ValueError, AttributeError):
                    detail = error_body[:200] if error_body else "unknown error"

                _LOGGER.debug(
                    "DiapStash token request failed (%s): %s",
                    resp.status,
                    detail,
                )
                resp.raise_for_status()

        except ClientResponseError as err:
            if err.status == HTTPStatus.TOO_MANY_REQUESTS or 500 <= err.status <= 599:
                raise OAuth2TokenRequestTransientError(
                    request_info=err.request_info,
                    history=err.history,
                    status=err.status,
                    message=err.message,
                    headers=err.headers,
                    domain=DOMAIN,
                ) from err

            if 400 <= err.status <= 499:
                raise OAuth2TokenRequestReauthError(
                    request_info=err.request_info,
                    history=err.history,
                    status=err.status,
                    message=err.message,
                    headers=err.headers,
                    domain=DOMAIN,
                ) from err

            raise OAuth2TokenRequestError(
                request_info=err.request_info,
                history=err.history,
                status=err.status,
                message=err.message,
                headers=err.headers,
                domain=DOMAIN,
            ) from err

        token = cast(dict[str, Any], await resp.json())
        expires_in = token.get("expires_in") or token.get("expiresIn")
        if expires_in is not None:
            token["expires_in"] = int(expires_in)
            # Refresh slightly before the server-side expiry to avoid API 401s.
            token["expires_at"] = time.time() + max(0, int(expires_in) - 60)
        return token


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> AbstractOAuth2Implementation:
    """Return custom OAuth implementation."""
    return DiapStashOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
        client_secret=credential.client_secret,
        code_verifier_length=128,
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "oauth_creds_url": "https://account.diapstash.com",
        "more_info_url": "https://docs.diapstash.com/api",
        "redirect_url": "https://my.home-assistant.io/redirect/oauth",
        "scopes": OAUTH2_SCOPES,
    }
