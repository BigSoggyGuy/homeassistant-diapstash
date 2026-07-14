# Changelog

## v1.1.5

### Added

- Add current change tags to the current diaper sensor.
- Add current change notes to the current diaper sensor.
- New current diaper attributes:
  - `change_tags`
  - `change_tags_label`
  - `change_note`
  - `change_has_note`

### Notes

- Tags and notes are read from the DiapStash history change fields `tags` and `note`.
- `change_tags` is exposed as a list so dashboards can render tags as chips or badges.

## v1.1.4

### Fixed

- Add repository-level brand assets in the root `brand/` directory so HACS and Home Assistant update cards can display the DiapStash icon correctly.
- Keep the existing integration-level brand assets under `custom_components/diapstash/brand/` for Home Assistant's local custom integration brand support.

## v1.1.3

### Documentation / setup

- Add a pre-filled DiapStash API client creation link to the README.
- Show the pre-filled API client creation link during Home Assistant setup.
- Document the recommended API Server application type, redirect URL and required scopes more clearly.

## v1.1.2

### Added

- Add support for additional current change items such as boosters.
- The current diaper sensor can now expose:
  - `current_items`
  - `boosters`
  - `boosters_count`
  - `boosters_label`

### Fixed

- Avoid unnecessary integration reloads when OAuth token data changes.
- This prevents entities from briefly becoming unavailable during token refreshes.
- Keep entities available with their last known good values during temporary DiapStash API or network update failures.
- Reduce noisy Home Assistant history entries where sensors briefly changed to unavailable and back on the next successful poll.

### Notes

- The integration still uses the primary diaper as the main state of the current diaper sensor. Additional items such as boosters are exposed as attributes.

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
