"""Subscription Tracker integration: tracks streaming subscriptions."""
from __future__ import annotations

from datetime import date

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DATE,
    ATTR_PRICE,
    CONF_HUB,
    CONF_PRICE_HISTORY,
    CONF_SERVICE,
    DOMAIN,
    HISTORY_STORE_KEY,
    HISTORY_STORE_VERSION,
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


@callback
def _async_ensure_hub(hass: HomeAssistant) -> None:
    """Create the hub entry (summary + budget) if it does not exist.

    Creating it twice is harmless: the import flow aborts on the hub unique_id.
    """
    if any(e.data.get(CONF_HUB) for e in hass.config_entries.async_entries(DOMAIN)):
        return
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={}
        )
    )


@callback
def _async_sync_unique_ids(hass: HomeAssistant) -> None:
    """Align stale config-entry unique_ids with "{service}_{title}".

    Versions up to 0.2.x did not update the unique_id when a subscription was edited
    (e.g. service or plan changed), so duplicate detection compared against the old
    values. Runs before the entries are set up, so no update listener (reload) fires.
    An entry is left alone if its expected unique_id is already taken by another one.
    """
    entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if not e.data.get(CONF_HUB) and e.data.get(CONF_SERVICE)
    ]
    taken = {e.unique_id for e in entries}
    for entry in entries:
        expected = f"{entry.data[CONF_SERVICE]}_{entry.title}"
        if entry.unique_id == expected or expected in taken:
            continue
        taken.discard(entry.unique_id)
        taken.add(expected)
        hass.config_entries.async_update_entry(entry, unique_id=expected)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the service and make sure the hub entry exists."""
    _async_register_services(hass)
    _async_sync_unique_ids(hass)

    # The hub entry owns the summary and the budget: it is created automatically
    # the first time (also for users upgrading from a version without a hub).
    _async_ensure_hub(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not entry.data.get(CONF_HUB):
        # The hub may have been deleted while no subscription existed.
        _async_ensure_hub(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Keep the summary consistent after an entry is removed."""
    if entry.data.get(CONF_HUB):
        # The hub owns the summary sensor and the budget: without it the summary
        # would be missing until the next restart. While subscriptions remain, bring
        # it back (the budget is reset). With no subscription left, leave it deleted.
        if any(not e.data.get(CONF_HUB) for e in hass.config_entries.async_entries(DOMAIN)):
            _async_ensure_hub(hass)
        else:
            # Nothing left to track: the monthly history goes away with the last entry.
            await Store(hass, HISTORY_STORE_VERSION, HISTORY_STORE_KEY).async_remove()
        return
    # After a subscription is removed the summary must be recomputed.
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
