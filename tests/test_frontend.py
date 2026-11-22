"""The bundled card: served by the integration and registered as a dashboard resource."""
import json
import re
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.subscription_tracker.const import DOMAIN

PKG = Path(__file__).parent.parent / "custom_components" / "subscription_tracker"
VERSION = json.loads((PKG / "manifest.json").read_text())["version"]
CARD_PATH = "/subscription_tracker/subscription-tracker-card.js"
CARD_URL = f"{CARD_PATH}?v={VERSION}"
LEGACY_URL = "/hacsfiles/ha-subscription-tracker-card/subscription-tracker-card.js?hacstag=1"


def _sub(service="netflix", name="Netflix"):
    return MockConfigEntry(
        domain=DOMAIN, title=name, unique_id=f"{service}_{name}",
        data={"service": service, "cost": 10.0, "currency": "EUR", "billing_cycle": "monthly",
              "renewal_date": (dt_util.now().date() + timedelta(days=10)).isoformat()},
        options={"price_history": []},
    )


async def _setup(hass, entry=None):
    entry = entry or _sub()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _hub(hass):
    return next(e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("hub"))


async def _lovelace(hass, config=None):
    assert await async_setup_component(hass, "lovelace", config or {})
    resources = hass.data[LOVELACE_DATA].resources
    await resources.async_get_info()
    return resources


def _items(resources):
    return [{"type": i["type"], "url": i["url"]} for i in resources.async_items()]


async def test_card_file_is_served(hass, hass_client):
    await _setup(hass)
    client = await hass_client()
    resp = await client.get(CARD_URL)
    assert resp.status == 200
    body = await resp.text()
    assert 'customElements.get("subscription-tracker-card")' in body


async def test_card_version_matches_manifest():
    js = (PKG / "www" / "subscription-tracker-card.js").read_text(encoding="utf-8")
    assert re.search(r'const CARD_VERSION = "([^"]+)";', js).group(1) == VERSION


async def test_card_registers_its_element_only_once():
    js = (PKG / "www" / "subscription-tracker-card.js").read_text(encoding="utf-8")
    define = js.index('customElements.define("subscription-tracker-card"')
    guard = js.index('if (!customElements.get("subscription-tracker-card"))')
    assert guard < define


async def test_resource_created_in_storage_mode(hass):
    resources = await _lovelace(hass)
    await _setup(hass)
    assert _items(resources) == [{"type": "module", "url": CARD_URL}]


async def test_resource_updated_on_new_version_and_never_duplicated(hass):
    resources = await _lovelace(hass)
    await resources.async_create_item({"res_type": "module", "url": f"{CARD_PATH}?v=0.4.9"})
    await resources.async_create_item({"res_type": "module", "url": "/local/other-card.js"})
    await _setup(hass)
    await hass.config_entries.async_reload(_hub(hass).entry_id)
    await hass.async_block_till_done()
    assert _items(resources) == [
        {"type": "module", "url": CARD_URL},
        {"type": "module", "url": "/local/other-card.js"},
    ]


async def test_yaml_resources_fall_back_to_extra_module_url(hass):
    await _lovelace(hass, {"lovelace": {"resource_mode": "yaml", "resources": []}})
    with patch(
        "custom_components.subscription_tracker.frontend.add_extra_js_url"
    ) as add_url:
        await _setup(hass)
    add_url.assert_called_with(hass, CARD_URL)


async def test_without_lovelace_setup_still_works(hass):
    await _setup(hass)
    assert hass.states.get("sensor.subscriptions_total") is not None


async def test_resource_removed_with_the_last_entry(hass):
    resources = await _lovelace(hass)
    sub = await _setup(hass)
    await hass.config_entries.async_remove(sub.entry_id)
    await hass.async_block_till_done()
    assert _items(resources) == [{"type": "module", "url": CARD_URL}]  # hub still there
    await hass.config_entries.async_remove(_hub(hass).entry_id)
    await hass.async_block_till_done()
    assert _items(resources) == []


async def test_separately_installed_card_raises_a_repair_issue(hass):
    resources = await _lovelace(hass)
    await resources.async_create_item({"res_type": "module", "url": LEGACY_URL})
    await _setup(hass)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "legacy_card_resource")
    assert issue is not None
    assert issue.translation_placeholders == {"url": LEGACY_URL}
    # The user's resource is left alone.
    assert {"type": "module", "url": LEGACY_URL} in _items(resources)


async def test_no_repair_issue_without_a_separate_card(hass):
    await _lovelace(hass)
    await _setup(hass)
    # Second pass (restart, hub reload): the card's own resource is not "legacy".
    await hass.config_entries.async_reload(_hub(hass).entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "legacy_card_resource") is None
