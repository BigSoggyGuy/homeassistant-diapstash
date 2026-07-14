"""Constants for the DiapStash integration."""

from homeassistant.const import Platform

DOMAIN = "diapstash"
NAME = "DiapStash"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

OAUTH2_AUTHORIZE = "https://account.diapstash.com/oidc/auth"
OAUTH2_TOKEN = "https://account.diapstash.com/oidc/token"
OAUTH2_SCOPES = "cloud-sync.history cloud-sync.stock cloud-sync.types offline_access"

OAUTH2_REDIRECT_URL = "https://my.home-assistant.io/redirect/oauth"
DIAPSTASH_API_CLIENT_PREFILL_URL = (
    "https://account.diapstash.com/account/api/create?clientName=Home+Assistant+DiapStash&mode=backend&redirectUri=https%3A%2F%2Fmy.home-assistant.io%2Fredirect%2Foauth&scope=cloud-sync.history&scope=cloud-sync.stock&scope=cloud-sync.types&scope=offline_access"
)

API_BASES = (
    "https://api.diapstash.com/api/v1",
    "https://api.diapstash.com/api",
)

MAX_PAGE_SIZE = 50

STOCKS_PATH = "/stock/stocks"
DISPOSABLES_PATH = "/stock/disposables"
REUSABLES_PATH = "/stock/reusables"

TYPE_PATH = "/type/types/{type_id}"
BRAND_PATH = "/brand/brands/{brand_code}"

CATALOG_TYPE_URL = "https://diapstash.com/catalog/types/{type_id}"

UPDATE_INTERVAL_MINUTES = 15
INTEGRATION_VERSION = "1.1.5"

ATTR_BRAND = "brand"
ATTR_CHANGE_ID = "change_id"
ATTR_CATALOG_URL = "catalog_url"
ATTR_DIAPER_NAME = "diaper_name"
ATTR_DURATION_TEXT = "duration_text"
ATTR_IMAGE_URL = "image_url"
ATTR_SIZE = "size"
ATTR_START_TIME = "start_time"
ATTR_TYPE_ID = "type_id"
ATTR_VARIANT = "variant"
ATTR_WEARING = "wearing"

COMMON_HEADERS = {
    "User-Agent": (
        f"HomeAssistant-DiapStash/{INTEGRATION_VERSION} "
        "(+https://github.com/BigSoggyGuy/homeassistant-diapstash)"
    ),
    "Accept": "application/json",
}

CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENABLE_STOCK = "enable_stock"
CONF_ENABLE_STATS = "enable_stats"
CONF_ENABLE_DYNAMIC_STOCK_ENTITIES = "enable_dynamic_stock_entities"
CONF_ENABLE_LOW_STOCK_BINARY_SENSORS = "enable_low_stock_binary_sensors"
CONF_LOW_STOCK_THRESHOLD = "low_stock_threshold"
CONF_LIVE_DURATION_INTERVAL = "live_duration_interval"
DATA_USE_ACCOUNT_DEVICE_IDENTIFIER = "use_account_device_identifier"

DEFAULT_SCAN_INTERVAL = 15
DEFAULT_ENABLE_STOCK = True
DEFAULT_ENABLE_STATS = True
DEFAULT_ENABLE_DYNAMIC_STOCK_ENTITIES = True
DEFAULT_ENABLE_LOW_STOCK_BINARY_SENSORS = True
DEFAULT_LOW_STOCK_THRESHOLD = 10
DEFAULT_LIVE_DURATION_INTERVAL = 5

ADD_URL = "https://diapstash.com/app/catalog/add?typeId={type_id}"
