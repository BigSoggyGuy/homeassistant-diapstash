"""Application credentials support for DiapStash."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, cast

from aiohttp import ClientError, ClientResponseError
from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    LocalOAuth2ImplementationWithPkce,
)

from .const import (
    COMMON_HEADERS,
    DIAPSTASH_API_CLIENT_PREFILL_URL,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_REDIRECT_URL,
    OAUTH2_SCOPES,
    OAUTH2_TOKEN,
)
from .oauth import (
    classify_token_error,
    merge_refresh_token_response,
    safe_oauth_error_code,
)

_LOGGER = logging.getLogger(__name__)


class DiapStashOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """DiapStash OAuth implementation with PKCE, scopes and integration headers."""

    last_refresh_at: float | None = None
    last_refresh_token_rotated: bool | None = None
    last_refresh_error_code: str | None = None
    last_refresh_error_status: int | None = None

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
        is_refresh = data.get("grant_type") == "refresh_token"

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
                error_code = "unknown_error"
                try:
                    error_data = json.loads(await resp.text())
                    error_code = safe_oauth_error_code(error_data.get("error"))
                except (ClientError, ValueError, AttributeError):
                    pass

                if is_refresh:
                    self.last_refresh_error_code = error_code
                    self.last_refresh_error_status = resp.status

                _LOGGER.warning(
                    "DiapStash token request failed (HTTP %s, OAuth error %s)",
                    resp.status,
                    error_code,
                )

                error_kind = classify_token_error(resp.status, error_code)
                if error_kind == "transient":
                    raise OAuth2TokenRequestTransientError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=resp.status,
                        message=error_code,
                        headers=resp.headers,
                        domain=DOMAIN,
                    )

                if error_kind == "reauth":
                    raise OAuth2TokenRequestReauthError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=resp.status,
                        message=error_code,
                        headers=resp.headers,
                        domain=DOMAIN,
                    )

                raise OAuth2TokenRequestError(
                    request_info=resp.request_info,
                    history=resp.history,
                    status=resp.status,
                    message=error_code,
                    headers=resp.headers,
                    domain=DOMAIN,
                )

        except ClientResponseError as err:
            if is_refresh:
                self.last_refresh_error_code = "http_error"
                self.last_refresh_error_status = err.status

            error_kind = classify_token_error(err.status, "unknown_error")
            if error_kind == "transient":
                raise OAuth2TokenRequestTransientError(
                    request_info=err.request_info,
                    history=err.history,
                    status=err.status,
                    message=err.message,
                    headers=err.headers,
                    domain=DOMAIN,
                ) from err

            if error_kind == "reauth":
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

    async def _async_refresh_token(self, token: dict[str, Any]) -> dict[str, Any]:
        """Refresh and safely retain or replace the rotating refresh token."""
        response_token = await self._token_request(
            {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": token["refresh_token"],
            }
        )
        if not response_token.get("access_token") or response_token.get("expires_in") in (
            None,
            "",
        ):
            raise OAuth2TokenRequestConnectionError(domain=self.service_domain)

        self.last_refresh_at = time.time()
        self.last_refresh_token_rotated = bool(response_token.get("refresh_token"))
        self.last_refresh_error_code = None
        self.last_refresh_error_status = None
        token_type = str(response_token.get("token_type") or token.get("token_type") or "unknown")
        if token_type.casefold() not in {"bearer", "dpop"}:
            token_type = "unknown"
        _LOGGER.debug(
            "DiapStash token refresh succeeded "
            "(refresh token rotated: %s, token type: %s, expires in: %s)",
            self.last_refresh_token_rotated,
            token_type,
            response_token.get("expires_in"),
        )
        return merge_refresh_token_response(token, response_token)


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
        "api_client_url": DIAPSTASH_API_CLIENT_PREFILL_URL,
        "redirect_url": OAUTH2_REDIRECT_URL,
        "scopes": OAUTH2_SCOPES,
    }
