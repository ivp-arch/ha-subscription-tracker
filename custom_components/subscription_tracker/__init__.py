"""Subscription Tracker integration: tracks streaming subscriptions."""
from __future__ import annotations

from datetime import date

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DATE,
    ATTR_PRICE,
    CONF_HUB,
    CONF_PRICE_HISTORY,
    DOMAIN,
    SERVICE_ADD_PRICE_HISTORY,
    SIGNAL_SUMMARY_UPDATE,
)

PLATFORMS = ["sensor"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ADD_PRICE_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required(ATTR_PRICE): vol.Coerce(float),
        vol.Required(ATTR_DATE): cv.date,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the service and make sure the hub entry exists."""
    _async_register_services(hass)

    # The hub entry owns the summary and the budget: it is created automatically
    # the first time (also for users upgrading from a version without a hub).
    if not any(e.data.get(CONF_HUB) for e in hass.config_entries.async_entries(DOMAIN)):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data={}
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """After a subscription is removed the summary must be recomputed."""
    async_dispatcher_send(hass, SIGNAL_SUMMARY_UPDATE)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its configuration is modified."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    async def _handle_add_price_history(call: ServiceCall) -> None:
        """Manually add a past price change."""
        entity_id = call.data["entity_id"]
        price = float(call.data[ATTR_PRICE])
        when: date = call.data[ATTR_DATE]

        registry = er.async_get(hass)
        rentry = registry.async_get(entity_id)
        if rentry is None or rentry.config_entry_id is None:
            raise ServiceValidationError(f"Entita' {entity_id} non trovata")

        entry = hass.config_entries.async_get_entry(rentry.config_entry_id)
        if entry is None or entry.domain != DOMAIN or entry.data.get(CONF_HUB):
            raise ServiceValidationError(f"{entity_id} is not a {DOMAIN} subscription")

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
