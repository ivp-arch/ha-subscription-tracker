"""Serve the bundled Lovelace card and register it as a dashboard resource."""
from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration

from .const import CARD_FILENAME, CARD_URL_PATH, DOMAIN, ISSUE_LEGACY_CARD

_LOGGER = logging.getLogger(__name__)


async def async_register_card_path(hass: HomeAssistant) -> None:
    """Serve www/<card> at CARD_URL_PATH (cached: the URL carries the version)."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PATH, str(Path(__file__).parent / "www" / CARD_FILENAME), True)]
    )


async def async_setup_card_resource(hass: HomeAssistant) -> None:
    """Add or update the card resource; warn about a separately installed card.

    Storage-mode resources get exactly one entry for the card, whose ?v= follows the
    integration version. Resources managed in YAML cannot be written, so the card is
    loaded as an extra frontend module instead.
    """
    data = hass.data.get(LOVELACE_DATA)
    if data is None:
        _LOGGER.debug("Lovelace is not loaded: card resource not registered")
        return
    url = f"{CARD_URL_PATH}?v={(await async_get_integration(hass, DOMAIN)).version}"
    resources = data.resources
    await resources.async_get_info()  # loads the stored resources
    items = resources.async_items() or []
    _async_check_legacy_card(hass, items)

    if not isinstance(resources, ResourceStorageCollection):
        _LOGGER.info("Dashboard resources are managed in YAML: loading %s as a frontend module", url)
        add_extra_js_url(hass, url)
        return

    ours = [item for item in items if _path(item["url"]) == CARD_URL_PATH]
    if not ours:
        await resources.async_create_item({"res_type": "module", "url": url})
    elif ours[0]["url"] != url:
        await resources.async_update_item(ours[0]["id"], {"res_type": "module", "url": url})


async def async_remove_card_resource(hass: HomeAssistant) -> None:
    """Remove the card resource (the integration has no entry left)."""
    ir.async_delete_issue(hass, DOMAIN, ISSUE_LEGACY_CARD)
    data = hass.data.get(LOVELACE_DATA)
    if data is None or not isinstance(data.resources, ResourceStorageCollection):
        return
    await data.resources.async_get_info()
    for item in list(data.resources.async_items()):
        if _path(item["url"]) == CARD_URL_PATH:
            await data.resources.async_delete_item(item["id"])


def _path(url: str) -> str:
    return urlsplit(url).path


def _async_check_legacy_card(hass: HomeAssistant, items: list[dict]) -> None:
    """Raise a repair issue if the card is also installed on its own (pre-0.5.0)."""
    legacy = [
        item["url"]
        for item in items
        if _path(item["url"]).endswith(f"/{CARD_FILENAME}") and _path(item["url"]) != CARD_URL_PATH
    ]
    if not legacy:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_LEGACY_CARD)
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_LEGACY_CARD,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_LEGACY_CARD,
        translation_placeholders={"url": legacy[0]},
    )
