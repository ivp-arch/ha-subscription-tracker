"""Costanti per l'integrazione Subscription Tracker."""
from __future__ import annotations

DOMAIN = "subscription_tracker"

# --- Campi di configurazione ---------------------------------------------
CONF_SERVICE = "service"
CONF_CUSTOM_NAME = "custom_name"
CONF_CUSTOM_ICON = "custom_icon"
CONF_CATEGORY = "category"
CONF_PLAN = "plan"
CONF_COST = "cost"
CONF_CURRENCY = "currency"
CONF_BILLING_CYCLE = "billing_cycle"
CONF_RENEWAL_DATE = "renewal_date"
CONF_SHARED_COUNT = "shared_count"
CONF_PAYMENT_NOTE = "payment_note"
CONF_SUBSCRIBED_SINCE = "subscribed_since"
CONF_PAUSED = "paused"
CONF_NOTES = "notes"
CONF_EXPIRING_SOON_DAYS = "expiring_soon_days"

# Chiave interna (options) per lo storico prezzi: lista di {date, price}
CONF_PRICE_HISTORY = "price_history"

# Voce "hub": possiede il sensore di riepilogo e la soglia di budget.
CONF_HUB = "hub"
CONF_BUDGET = "budget"
HUB_UNIQUE_ID = "hub"
HUB_TITLE = "Riepilogo abbonamenti"

# Versione del contratto attributi (vedi docs/attributes-contract.md).
CONTRACT_VERSION = 1

# Finestra della timeline dei rinnovi nel riepilogo (giorni).
UPCOMING_DAYS = 30

# Segnale interno: ricalcola il riepilogo.
SIGNAL_SUMMARY_UPDATE = f"{DOMAIN}_summary_update"

CUSTOM_SERVICE_KEY = "altro"

# --- Cicli di fatturazione ------------------------------------------------
BILLING_CYCLE_MONTHLY = "monthly"
BILLING_CYCLE_QUARTERLY = "quarterly"
BILLING_CYCLE_YEARLY = "yearly"

BILLING_CYCLES = [
    BILLING_CYCLE_MONTHLY,
    BILLING_CYCLE_QUARTERLY,
    BILLING_CYCLE_YEARLY,
]

# Mesi per ciclo, usati per normalizzare il costo mensile
BILLING_CYCLE_MONTHS = {
    BILLING_CYCLE_MONTHLY: 1,
    BILLING_CYCLE_QUARTERLY: 3,
    BILLING_CYCLE_YEARLY: 12,
}

CURRENCIES = ["EUR", "USD", "GBP"]

DEFAULT_EXPIRING_SOON_DAYS = 7

# --- Stati ----------------------------------------------------------------
STATUS_ACTIVE = "active"
STATUS_EXPIRING_SOON = "expiring_soon"
STATUS_EXPIRED = "expired"
STATUS_PAUSED = "paused"

# --- Categorie ------------------------------------------------------------
CATEGORY_VIDEO = "video"
CATEGORY_AUDIO = "audio"
CATEGORY_ALTRO = "altro"

CATEGORIES = [CATEGORY_VIDEO, CATEGORY_AUDIO, CATEGORY_ALTRO]

# --- Servizio custom ------------------------------------------------------
SERVICE_ADD_PRICE_HISTORY = "add_price_history"
ATTR_PRICE = "price"
ATTR_DATE = "date"

# --- Servizi noti pre-mappati --------------------------------------------
# nome visualizzato, icona mdi, colore identificativo, categoria di default.
KNOWN_SERVICES: dict[str, dict[str, str]] = {
    "netflix": {"name": "Netflix", "icon": "mdi:netflix", "color": "#A32D2D", "category": CATEGORY_VIDEO},
    "prime_video": {"name": "Prime Video", "icon": "mdi:amazon", "color": "#185FA5", "category": CATEGORY_VIDEO},
    "disney_plus": {"name": "Disney+", "icon": "mdi:castle", "color": "#185FA5", "category": CATEGORY_VIDEO},
    "paramount_plus": {"name": "Paramount+", "icon": "mdi:play-box-outline", "color": "#378ADD", "category": CATEGORY_VIDEO},
    "crunchyroll": {"name": "Crunchyroll", "icon": "mdi:animation-play", "color": "#BA7517", "category": CATEGORY_VIDEO},
    "hbo_max": {"name": "HBO Max", "icon": "mdi:play-network", "color": "#534AB7", "category": CATEGORY_VIDEO},
    "now_tv": {"name": "NOW TV", "icon": "mdi:television", "color": "#0F6E56", "category": CATEGORY_VIDEO},
    "chili": {"name": "Chili", "icon": "mdi:movie-open", "color": "#D85A30", "category": CATEGORY_VIDEO},
    "apple_tv_plus": {"name": "Apple TV+", "icon": "mdi:apple", "color": "#5F5E5A", "category": CATEGORY_VIDEO},
    "dazn": {"name": "DAZN", "icon": "mdi:soccer", "color": "#854F0B", "category": CATEGORY_VIDEO},
    "raiplay": {"name": "RaiPlay+", "icon": "mdi:television-classic", "color": "#185FA5", "category": CATEGORY_VIDEO},
    "mediaset_infinity": {"name": "Mediaset Infinity+", "icon": "mdi:television-play", "color": "#993C1D", "category": CATEGORY_VIDEO},
    "timvision": {"name": "TIMvision", "icon": "mdi:television", "color": "#993556", "category": CATEGORY_VIDEO},
    "sky_now": {"name": "Sky", "icon": "mdi:satellite-variant", "color": "#0C447C", "category": CATEGORY_VIDEO},
    "discovery_plus": {"name": "Discovery+", "icon": "mdi:compass-outline", "color": "#3B6D11", "category": CATEGORY_VIDEO},
    "spotify": {"name": "Spotify", "icon": "mdi:spotify", "color": "#0F6E56", "category": CATEGORY_AUDIO},
    "apple_music": {"name": "Apple Music", "icon": "mdi:apple", "color": "#993556", "category": CATEGORY_AUDIO},
    "amazon_music": {"name": "Amazon Music Unlimited", "icon": "mdi:amazon", "color": "#185FA5", "category": CATEGORY_AUDIO},
    "youtube_music": {"name": "YouTube Music/Premium", "icon": "mdi:youtube", "color": "#A32D2D", "category": CATEGORY_AUDIO},
    "tidal": {"name": "Tidal", "icon": "mdi:water-outline", "color": "#2C2C2A", "category": CATEGORY_AUDIO},
    "audible": {"name": "Audible", "icon": "mdi:book-music-outline", "color": "#854F0B", "category": CATEGORY_AUDIO},
    CUSTOM_SERVICE_KEY: {"name": "Altro (personalizzato)", "icon": "mdi:credit-card-outline", "color": "#5F5E5A", "category": CATEGORY_ALTRO},
}
