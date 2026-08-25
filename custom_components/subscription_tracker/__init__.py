"""Integrazione Subscription Tracker: monitora abbonamenti streaming."""
from __future__ import annotations

from datetime import date

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    ATTR_DATE,
    ATTR_PRICE,
    CONF_PRICE_HISTORY,
    DOMAIN,
    SERVICE_ADD_PRICE_HISTORY,
)

PLATFORMS = ["sensor"]

ADD_PRICE_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required(ATTR_PRICE): vol.Coerce(float),
        vol.Required(ATTR_DATE): cv.date,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and not hass.config_entries.async_entries(DOMAIN):
        hass.data[DOMAIN].pop("summary_created", None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ricarica l'entry quando la configurazione viene modificata."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_ADD_PRICE_HISTORY):
        return

    async def _handle_add_price_history(call: ServiceCall) -> None:
        """Inserisce a mano una variazione di prezzo passata."""
        entity_id = call.data["entity_id"]
        price = float(call.data[ATTR_PRICE])
        when: date = call.data[ATTR_DATE]

        registry = er.async_get(hass)
        rentry = registry.async_get(entity_id)
        if rentry is None or rentry.config_entry_id is None:
            raise ServiceValidationError(f"Entita' {entity_id} non trovata")

        entry = hass.config_entries.async_get_entry(rentry.config_entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(f"{entity_id} non appartiene a {DOMAIN}")

        iso = when.isoformat()
        history = [h for h in entry.options.get(CONF_PRICE_HISTORY, []) if h.get("date") != iso]
        history.append({"date": iso, "price": price})
        history.sort(key=lambda h: h["date"])

        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_PRICE_HISTORY: history}
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_PRICE_HISTORY,
        _handle_add_price_history,
        schema=ADD_PRICE_HISTORY_SCHEMA,
    )
