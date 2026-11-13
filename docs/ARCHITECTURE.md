# Architecture — DiapStash v1.1.5

## Data flow

```text
Home Assistant config flow
  └─ DiapStash API credentials / OAuth2 PKCE / reauth
       └─ __init__.py → OAuth2Session → DiapStashApiClient
            └─ DiapStashCoordinator (periodic cloud poll)
                 ├─ /history/changes → current diaper, boosters, tags, note, stats
                 ├─ /stock/* → stock, by type/brand/location, reusables to wash
                 └─ /type/types/* and /brand/brands/* → metadata and images
                      ├─ sensor.py
                      └─ binary_sensor.py
```

## Startup, update, teardown

- `async_setup_entry` creates the OAuth implementation, coordinator and entities after a first refresh.
- Tokens may be refreshed by Home Assistant; the config entry update listener **must not reload** for `entry.data`-only token changes. It compares saved/current `entry.options`.
- Polling interval from Options Flow is applied by the coordinator. Local duration updates are scheduled in sensor classes independently and should not fetch API data.
- `CoordinatorEntity.available` is overridden in `entity.py` to keep last good data on short fetch failures; initial data missing should remain unavailable.
- `async_unload_entry` unloads platforms and removes coordinator state.

## API object shape

`DiapStashCurrentDiaper` (`api.py`) supplies current values and stock aggregates to the coordinator. Core fields are:

- `wearing`, `label`, `brand`, `diaper_name`, `size`, `variant`, `start_time`, `change_id`, `type_id`, image/catalog URL.
- `current_items`, `boosters`, `boosters_count`, `boosters_label`.
- `change_tags: list[str]`, `change_tags_label: str|None`, `change_note: str|None`, `change_has_note: bool`.
- stats `month_count`, `year_count`, `total_changes`, `streak_count`, `streak_minutes`, `streak_text`.
- stock `stock_total`, `stock_entries`, `stock_to_wash`, `stock_locations`, `stock_by_brand`, `stock_by_type`, `stock_items`.

The `current_diaper` sensor exposes attributes by mapping these fields in `sensor.py`; the primary diaper remains the native sensor value.

## Auth and error handling

- OAuth2 PKCE and manually supplied API client credentials are managed in `config_flow.py` and `application_credentials.py`.
- Read API requests retry on HTTP 401 after refresh and must surface persistent auth issues to HA reauthentication.
- OIDC `sub` is decoded locally (`token.py`) for *identification only*; do not use this unverified decoding for authorization or JWT cryptographic validation.
- Preserve stable config entry and device identifiers, especially migration of older installs.

## Entity names and translations

- Existing users may retain older German-generated entity IDs; **never rename HA unique IDs without migration**.
- UI strings: `strings.json` plus translations `en.json`, `de.json`, `fr.json`, `es.json`.
- New settings/sensors require translation parity and regression checks.

## Branding and distribution

- Integration code is under `custom_components/diapstash/`.
- Root `brand/` and integration-level `brand/` assets exist in source. Missing logo in HACS/update cards remains an unverified issue.
- `hacs.json`, manifest, `README.md`, `CHANGELOG.md`, `.github/workflows/` are delivery and validation metadata.

## Compatibility

- Baseline `manifest.json`: `version: 1.1.5`.
- Baseline `hacs.json`: `homeassistant: 2026.6.0`.
- No external requirements listed in the integration manifest; Home Assistant provides its runtime dependencies.
