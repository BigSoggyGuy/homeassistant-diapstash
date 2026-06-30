# Changelog

## v1.0.2

### Fixes

- Add Home Assistant reauthentication flow for expired, invalid or revoked DiapStash OAuth tokens.
- Fix an issue where token refresh failures could leave the integration in a setup error state.
- Fix `Handler DiapStashConfigFlow doesn't support step reauth`.
- Reauthentication now updates the existing config entry instead of creating a new one.
- Reauthentication verifies that the same DiapStash account is used.
- Improve token request error handling and logging.

## v1.0.1

### Fixes

- Keep the `duration_minutes` and `duration_text` attributes on the current diaper sensor in sync with the dedicated wearing duration sensors.
- The current diaper sensor now refreshes its duration attributes on the configured live duration interval.
- No additional DiapStash API calls are made for these local duration updates.

## v1.0.0

### Highlights

- Multi-account support.
- Direct DiapStash API credential setup during integration setup.
- Separate API credentials per DiapStash account.
- Stable account identification via the `sub` claim from the access token.
- OAuth2 / PKCE authentication.
- Improved OAuth token refresh handling.
- Custom DiapStash type support via `cloud-sync.types`.
- Current diaper, wearing duration and wearing binary sensors.
- Entity picture support for current diaper and stock type sensors.
- Stock overview, stock totals, stock by brand, stock by type and stock locations.
- Low-stock binary sensors.
- Reusable diaper “to wash” sensor.
- Options Flow.
- Translations for English, German, French and Spanish.
