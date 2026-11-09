from datetime import date, timedelta

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.subscription_tracker.const import DOMAIN

SUMMARY = "sensor.abbonamenti_totale"


def _sub(service, name, cost=10.0, days=10, **extra):
    return MockConfigEntry(
        domain=DOMAIN, title=name, unique_id=f"{service}_{name}",
        data={"service": service, "cost": cost, "currency": "EUR", "billing_cycle": "monthly",
              "renewal_date": (date.today() + timedelta(days=days)).isoformat(),
              "payment_note": "Carta 4417", **extra},
        options={"price_history": [{"date": date.today().isoformat(), "price": cost}]},
    )


async def _setup(hass, *entries):
    for e in entries:
        e.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entries[0].entry_id)
    await hass.async_block_till_done()


def _hub(hass):
    return next(e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("hub"))


async def test_hub_created_automatically(hass):
    a = _sub("netflix", "Netflix")
    await _setup(hass, a)
    hubs = [e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("hub")]
    assert len(hubs) == 1
    assert hass.states.get(SUMMARY).state == "10.0"


async def test_summary_survives_reload_of_any_entry(hass):
    a, b = _sub("netflix", "Netflix"), _sub("spotify", "Spotify", cost=5.0)
    await _setup(hass, a, b)
    assert hass.states.get(SUMMARY).state == "15.0"
    for eid in (a.entry_id, b.entry_id, _hub(hass).entry_id):
        await hass.config_entries.async_reload(eid)
        await hass.async_block_till_done()
        st = hass.states.get(SUMMARY)
        assert st.state == "15.0", f"dopo reload di {eid}"


async def test_summary_updates_on_remove_and_add(hass):
    a, b = _sub("netflix", "Netflix"), _sub("spotify", "Spotify", cost=5.0)
    await _setup(hass, a, b)
    await hass.config_entries.async_remove(a.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SUMMARY).state == "5.0"
    c = _sub("dazn", "DAZN", cost=30.0)
    c.add_to_hass(hass)
    await hass.config_entries.async_setup(c.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SUMMARY).state == "35.0"


async def test_legacy_summary_is_adopted_by_hub(hass):
    """Registro dell'installazione precedente: riepilogo legato a un abbonamento."""
    a = _sub("netflix", "Netflix")
    a.add_to_hass(hass)
    reg = er.async_get(hass)
    reg.async_get_or_create("sensor", DOMAIN, f"{DOMAIN}_summary", config_entry=a,
                            suggested_object_id="abbonamenti_totale")
    assert await hass.config_entries.async_setup(a.entry_id)
    await hass.async_block_till_done()
    assert reg.async_get(SUMMARY).config_entry_id == _hub(hass).entry_id
    await hass.config_entries.async_reload(a.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SUMMARY).state == "10.0"


async def test_budget_option_flows_into_summary(hass):
    a = _sub("netflix", "Netflix", cost=40.0)
    await _setup(hass, a)
    hub = _hub(hass)
    r = await hass.config_entries.options.async_init(hub.entry_id)
    assert r["type"] == FlowResultType.FORM and r["step_id"] == "hub"
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"budget": 50})
    assert r["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    at = hass.states.get(SUMMARY).attributes
    assert at["budget"] == 50.0 and at["budget_used_pct"] == 80.0 and at["budget_exceeded"] is False
    assert at["contract_version"] == 1


async def test_timeline_and_renewal_advance(hass):
    a = _sub("netflix", "Netflix", days=-3)  # data inserita 3 giorni fa
    await _setup(hass, a)
    st = hass.states.get("sensor.netflix")
    assert int(st.state) >= 0 and st.attributes["status"] != "expired"
    assert st.attributes["renewal_advanced"] is True
    up = hass.states.get(SUMMARY).attributes["upcoming"]
    assert len(up) == 1 and up[0]["name"] == "Netflix"


async def test_payment_method_never_in_attributes(hass):
    a = _sub("netflix", "Netflix")
    await _setup(hass, a)
    for eid in ("sensor.netflix", SUMMARY):
        dumped = str(hass.states.get(eid).attributes)
        assert "4417" not in dumped and "payment" not in dumped


async def test_config_flow_without_subscribed_since(hass):
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {"service": "netflix", "cost": 12.99, "currency": "EUR", "billing_cycle": "monthly",
         "renewal_date": date.today().isoformat()},
    )
    assert r["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("sensor.netflix") is not None


async def test_options_flow_can_set_and_clear_subscribed_since(hass):
    a = _sub("netflix", "Netflix", subscribed_since="2021-03-01")
    await _setup(hass, a)
    base = {"service": "netflix", "cost": 10.0, "currency": "EUR", "billing_cycle": "monthly",
            "renewal_date": date.today().isoformat()}
    r = await hass.config_entries.options.async_init(a.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], base)  # senza data
    assert r["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert "subscribed_since" not in hass.states.get("sensor.netflix").attributes


async def test_add_price_history_service(hass):
    a = _sub("netflix", "Netflix", cost=12.99)
    await _setup(hass, a)
    await hass.services.async_call(DOMAIN, "add_price_history",
        {"entity_id": "sensor.netflix", "price": 9.99, "date": "2021-03-01"}, blocking=True)
    await hass.async_block_till_done()
    at = hass.states.get("sensor.netflix").attributes
    assert at["price_changes_count"] == 1 and at["price_history"][0]["price"] == 9.99


async def test_service_rejects_hub_entity(hass):
    from homeassistant.exceptions import ServiceValidationError
    await _setup(hass, _sub("netflix", "Netflix"))
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "add_price_history",
            {"entity_id": SUMMARY, "price": 1, "date": "2021-03-01"}, blocking=True)
