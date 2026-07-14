# DiapStash for Home Assistant

Custom Home Assistant integration for DiapStash Cloud Sync.

Current stable version: **1.1.5**

## Features

- OAuth2 / PKCE login through Home Assistant
- Direct setup of DiapStash API Client ID and Client Secret
- Multi-account support with separate API credentials per DiapStash account
- Stable account identification through the `sub` claim from the DiapStash access token
- Token refresh handling and Home Assistant reauthentication support
- Current diaper sensor
- Additional current change item attributes, including boosters
- Current change tags and notes as sensor attributes
- Wearing binary sensor
- Wearing duration sensor
- Local live wearing-duration updates without additional DiapStash API calls
- Entity picture support for the current diaper and dynamic stock type sensors
- Stock overview sensor
- Stock total sensor
- Stock entries sensor
- Reusable diapers to wash sensor
- Stock breakdown by brand, diaper type and stock location
- Auto-created per-brand stock sensors
- Auto-created per-diaper-type stock sensors
- Dynamic low-stock binary sensors
- Change counters for month, year and total
- Current streak sensor
- Type metadata through the official DiapStash types API
- Translations for English, German, French and Spanish
- Local Home Assistant brand images

## DiapStash API client

Each DiapStash account should use its own DiapStash API client credentials.

You can open a pre-filled DiapStash API client creation form here:

[Create pre-filled DiapStash API client](https://account.diapstash.com/account/api/create?clientName=Home+Assistant+DiapStash&mode=backend&redirectUri=https%3A%2F%2Fmy.home-assistant.io%2Fredirect%2Foauth&scope=cloud-sync.history&scope=cloud-sync.stock&scope=cloud-sync.types&scope=offline_access)

The form is only pre-filled. You still have to review and submit it in your DiapStash Account.

Recommended application type:

```text
API Server
```

Required scopes:

```text
cloud-sync.history
cloud-sync.stock
cloud-sync.types
offline_access
```

Redirect URL:

```text
https://my.home-assistant.io/redirect/oauth
```

If your Home Assistant instance does not use My Home Assistant for OAuth redirects, use the callback URL shown by Home Assistant during setup.

## Installation

### HACS custom repository

Add this repository as a custom HACS integration repository:

```text
https://github.com/BigSoggyGuy/homeassistant-diapstash
```

Category:

```text
Integration
```

Then install **DiapStash** through HACS and restart Home Assistant.

### Manual installation

Copy the folder:

```text
custom_components/diapstash
```

to:

```text
/config/custom_components/diapstash
```

Restart Home Assistant.

## Home Assistant setup

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **DiapStash**.
3. Use the pre-filled API client creation link if needed, then enter a name, OAuth Client ID and OAuth Client Secret from your DiapStash API client.
4. Log in to DiapStash and approve access.
5. The integration creates entities automatically.

## Multi-account setup

Each DiapStash account should use its own DiapStash API client credentials.

For example:

```text
Account A → API Client A → DiapStash entry A
Account B → API Client B → DiapStash entry B
```

The integration uses the `sub` claim from the access token as a stable DiapStash account identifier. This allows multiple DiapStash accounts to run side by side in one Home Assistant instance.

The same DiapStash account or the same API Client ID should not be added twice.

## Entities

Typical entity IDs for new installations:

```text
sensor.diapstash_current_diaper
sensor.diapstash_wearing_duration
sensor.diapstash_wearing_duration_text
binary_sensor.diapstash_wearing

sensor.diapstash_stock_overview
sensor.diapstash_stock_total
sensor.diapstash_stock_entries
sensor.diapstash_stock_to_wash
sensor.diapstash_stock_brands
sensor.diapstash_stock_types
sensor.diapstash_stock_locations

sensor.diapstash_month_changes
sensor.diapstash_year_changes
sensor.diapstash_total_changes
sensor.diapstash_current_streak
```

Existing installations may keep older entity IDs through Home Assistant's entity registry.

## Current diaper

The current diaper sensor exposes attributes such as:

```yaml
wearing: true
brand: ABUniverse
diaper_name: LittlePawz
size: L
start_time: "2026-07-05T11:07:00.000Z"
duration_text: "42m"
duration_minutes: 42
type_id: 27
catalog_url: "https://diapstash.com/catalog/types/27"
image_url: "https://..."
entity_picture: "https://..."
```

The duration attributes are refreshed locally on the configured live update interval. This does not trigger additional DiapStash API requests.

### Additional current change items and boosters

If the current change contains additional items such as boosters, the current diaper sensor can expose them as attributes:

```yaml
current_items:
  - index: 0
    role: diaper
    label: ABUniverse LittlePawz Size L
    type_id: 27
    brand: ABUniverse
    diaper_name: LittlePawz
    size: L
    image_url: "https://..."
  - index: 1
    role: booster
    label: Tena Rectangular Pads
    type_id: 123
    brand: Tena
    diaper_name: Rectangular Pads
    size: Boost
    image_url: "https://..."

boosters:
  - index: 1
    role: booster
    label: Tena Rectangular Pads
    type_id: 123
    brand: Tena
    diaper_name: Rectangular Pads
    size: Boost

boosters_count: 1
boosters_label: Tena Rectangular Pads
```

The main sensor state remains the primary diaper. Additional items are exposed as attributes for dashboards and automations.

## Stock implementation

The integration uses these DiapStash Cloud Sync API endpoints:

```text
/api/v1/stock/stocks
/api/v1/stock/disposables
/api/v1/stock/reusables
```

Stock total is calculated from disposable stock batches by summing `left` per stock location.

Reusable diapers are not included in the disposable stock total. Reusable diapers are only used for the reusable diapers to wash sensor.

Clean or washed reusable states do not count as needing wash, even if legacy or string-based API flags are present.

## Stock locations

Stock location names are resolved from the DiapStash API.

Dynamic stock type sensors can expose attributes like:

```yaml
stock_locations:
  - stock_id: "..."
    stock_name: Bedroom
    available: 12
  - stock_id: "..."
    stock_name: Storage
    available: 8

stock_location_names:
  - Bedroom
  - Storage
```

## Polling and local duration updates

The integration polls DiapStash every 15 minutes by default. One coordinator update may use several API calls because it fetches current history, stock locations, disposable stock and reusable stock.

The wearing duration can be refreshed locally without extra API calls. The live duration update interval can be configured in the integration options.

Temporary DiapStash API or network update failures keep the last known values available after the first successful data update. This avoids noisy short `unavailable` state changes in Home Assistant history.

OAuth token refresh updates do not reload the whole integration, so entities should remain available during token refreshes.

## Reauthentication

DiapStash refresh tokens rotate and may eventually expire or be rejected by the token endpoint.

If token refresh fails with a permanent authentication error, Home Assistant will start a reauthentication flow for the existing config entry.

During reauthentication, log in with the same DiapStash account. The integration checks the account identifier and updates the existing entry instead of creating a new one.

## Notes

DiapStash refresh tokens rotate. Do not use the same refresh token in multiple tools at the same time. Once this integration is configured, Home Assistant should be the only client using the token.

The integration is read-only. Stock additions are handled through DiapStash deep links, not API write access.


## Development notes

This development build adds diagnostic attributes for current change tags and notes.
