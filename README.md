# DiapStash for Home Assistant

Custom Home Assistant integration for DiapStash Cloud Sync.

> Development preview. Version 1.0.1 exposes diaper images as entity pictures to reduce DiapStash API load.

## Features

- OAuth2 login through Home Assistant
- Uses Home Assistant Application Credentials for user-provided Client ID and Client Secret
- Rotating refresh-token handling through Home Assistant's OAuth2 helper
- Current diaper sensor
- Wearing binary sensor
- Wearing duration sensor
- Stock overview sensor
- Stock total sensor
- Stock entries sensor
- Reusable diapers to wash sensor
- Stock breakdown by brand, diaper type and stock location
- Auto-created per-brand stock sensors
- Auto-created per-diaper-type stock sensors
- Change counters for month, year and total
- Current streak sensor
- Catalog lookup for `type_id` through the official DiapStash types API
- Local Home Assistant brand images

## Installation for development

Copy the folder:

```text
custom_components/diapstash
```

to:

```text
/config/custom_components/diapstash
```

Restart Home Assistant.

## DiapStash API client setup

Create an API client in DiapStash Account.

Recommended settings:

```text
Application type: API Server
Scopes:
  cloud-sync.history
  cloud-sync.stock
  cloud-sync.types
  offline_access
```

Redirect URL:

```text
https://my.home-assistant.io/redirect/oauth
```

If your Home Assistant does not use My Home Assistant for OAuth redirects, use the callback URL shown by Home Assistant in the Application Credentials setup dialog.

## Home Assistant setup

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **DiapStash**.
3. Enter your DiapStash Client ID and Client Secret when Home Assistant asks for Application Credentials.
4. Log in to DiapStash and approve access.
5. The integration creates entities automatically.

## Entities

- `sensor.diapstash_current_diaper`
- `sensor.diapstash_wearing_duration`
- `sensor.diapstash_stock_overview`
- `sensor.diapstash_stock_total`
- `sensor.diapstash_stock_entries`
- `sensor.diapstash_stock_to_wash`
- `sensor.diapstash_stock_brands`
- `sensor.diapstash_stock_types`
- `sensor.diapstash_stock_locations`
- `sensor.diapstash_month_changes`
- `sensor.diapstash_year_changes`
- `sensor.diapstash_total_changes`
- `sensor.diapstash_current_streak`
- `binary_sensor.diapstash_wearing`

## Stock implementation

The integration uses these DiapStash Cloud Sync API endpoints:

```text
/api/v1/stock/stocks
/api/v1/stock/disposables
/api/v1/stock/reusables
```

Stock total is calculated from disposable stock batches by summing `left` per stock location. Reusable diapers are excluded from the available disposable count. Reusable items with `state = DIRTY` or `needWash = true` are counted in `sensor.diapstash_stock_to_wash`. The `stock_brands`, `stock_types` and `stock_locations` sensors expose detailed lists in their attributes for dashboards and automations.

## Polling interval

The integration polls DiapStash every 15 minutes by default. One coordinator update may use several API calls because it fetches current history, stock locations, disposable stock and reusable stock.

## Notes

DiapStash refresh tokens rotate. Do not use the same refresh token in multiple tools at the same time. Once this integration is configured, Home Assistant should be the only client using the token.

## HACS

This repository layout is HACS-compatible:

```text
custom_components/diapstash/manifest.json
hacs.json
README.md
```

Before publishing, update:

- `manifest.json` code owner
- documentation URL
- issue tracker URL
- README screenshots
- GitHub release/tag

## Brand images

Home Assistant 2026.3+ can load local brand images from:

```text
custom_components/diapstash/brand/icon.png
custom_components/diapstash/brand/logo.png
```

The included images are the PNG assets provided by the project maintainer.


## Dynamic stock detail entities

When stock data is loaded, the integration automatically creates additional entities like:

```text
sensor.diapstash_stock_brand_molicare
sensor.diapstash_stock_brand_abuniverse
sensor.diapstash_stock_type_98_l
```

If a new brand or diaper type appears later, the entity is added automatically on the next coordinator update. Existing detail entities report `0` when the item is no longer in stock.

## Version 0.7.0

This release adds:

- Live local wearing-duration updates every minute without extra DiapStash API calls
- Options flow under **Settings → Devices & services → DiapStash → Configure**
- Configurable API polling interval: 15, 30 or 60 minutes
- Toggles for stock sensors, statistics, dynamic stock entities and low-stock binary sensors
- Configurable low-stock threshold
- `add_url` and `image_url` attributes for stock type entities where available
- Dynamic low-stock binary sensors for stock types

The API polling interval remains 15 minutes by default.


## Version 0.7.1

Fixes the options flow for Home Assistant versions where `self.config_entry` is injected by Home Assistant and must not be assigned manually.


## Version 0.7.2

Normalizes entity names and options to English by default, including dynamic stock entities.


## Version 0.8.0

Adds multilingual translations for English, German, French and Spanish, including dynamic stock entity names via translation placeholders.


## Version 0.8.1

Adds stable English `suggested_object_id` values so new installations get consistent entity IDs regardless of Home Assistant UI language. Existing installations keep their current entity IDs through Home Assistant's entity registry.


## Version 0.8.2

Fixes `hacs.json` validation by removing unsupported `domains` and deprecated `render_readme` keys.


## Version 0.9.0

API cleanup based on DiapStash maintainer feedback:

- Adds the `cloud-sync.types` OAuth scope so custom user types can be resolved through the official API.
- Removes public catalog page scraping for type metadata.
- Uses a dedicated `HomeAssistant-DiapStash/<version>` User-Agent instead of a browser-like User-Agent.
- Removes the unnecessary `Accept-Language` header from API and OAuth requests.
- Uses the shared paginated loader for history.
- Replaces fixed pagination ranges with a `while True` pagination loop that stops on empty pages, short pages or total count.
- Keeps reusable items out of disposable stock totals; reusables are only used for the to-wash count.
- Updates remaining README examples to stable English entity IDs.

Existing installations may need to re-authenticate so DiapStash can grant the new `cloud-sync.types` scope.


## Version 0.9.1

Test build for API pagination according to the DiapStash API documentation:

- Uses page numbers starting at `1` instead of `0`.
- Uses a maximum page size of `50` instead of `200`.
- Stops trying fallback API base URLs after authentication errors to avoid misleading secondary `404` messages.


## Version 0.9.2

Adjusts pagination based on live API behaviour:

- Uses page numbers starting at `0`, because live testing showed page `1` can return an empty history page.
- Keeps the maximum page size at `50`.
- Does not fail setup when history is empty; the integration reports no current diaper instead.


## Version 0.9.3

Reduces Home Assistant recorder churn from live duration updates:

- Adds an options-flow setting for the local live duration update interval: `0`, `1`, `5` or `15` minutes.
- Defaults local duration updates to every `5` minutes instead of every minute.
- Keeps DiapStash API polling unchanged.
- Disables the redundant text duration sensor by default for new installations. Existing installations keep their current entity registry setting.


## Version 0.9.4

Fixes options-flow validation for the live duration update interval by coercing submitted values to integers before validation.


## Version 0.9.5

Applies the same integer coercion to the API polling interval options.


## Version 1.0.1

Adds image support from API type data:

- Adds `image_url` to the current diaper sensor attributes.
- Sets `entity_picture` for the current diaper sensor when an image URL is available.
- Sets `entity_picture` for dynamic stock type sensors when an image URL is available.
- Adds `add_url` and `image_url` to serialized stock item attributes.


## v1.0.1

- Fix reusable diaper wash counting when API boolean fields are returned as strings such as `"false"`.
- Reusable stock items are only counted as needing wash when `needWash` is truthy or the reusable state explicitly indicates a wash/dirty state.
