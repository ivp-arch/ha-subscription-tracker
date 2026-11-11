"""Robustness: hub lifecycle, config-entry unique_id, and the midnight rollover."""
from datetime import UTC, date, datetime, timedelta

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.subscription_tracker.const import DOMAIN

SUMMARY = "sensor.subscriptions_total"


def _today() -> date:
    return dt_util.now().date()


def _sub(service, name, cost=10.0, days=10, renewal=None, unique_id=None, **extra):
    renewal = renewal or (_today() + timedelta(days=days)).isoformat()
    return MockConfigEntry(
        domain=DOMAIN,
        title=name,
        unique_id=unique_id if unique_id is not None else f"{service}_{name}",
        data={"service": service, "cost": cost, "currency": "EUR", "billing_cycle": "monthly",
              "renewal_date": renewal, **extra},
        options={"price_history": [{"date": _today().isoformat(), "price": cost}]},
    )


async def _setup(hass, *entries):
    for e in entries:
        e.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entries[0].entry_id)
    await hass.async_block_till_done()


def _hubs(hass):
    return [e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("hub")]


def _form(service, cost=10.0, **extra):
    return {"service": service, "cost": cost, "currency": "EUR", "billing_cycle": "monthly",
            "renewal_date": _today().isoformat(), **extra}


# ---------- hub lifecycle ----------


async def test_deleted_hub_is_recreated_while_subscriptions_exist(hass):
    a, b = _sub("netflix", "Netflix"), _sub("spotify", "Spotify", cost=5.0)
    await _setup(hass, a, b)
    old_hub = _hubs(hass)[0]
    assert hass.states.get(SUMMARY).state == "15.0"

    await hass.config_entries.async_remove(old_hub.entry_id)
    await hass.async_block_till_done()

    hubs = _hubs(hass)
    assert len(hubs) == 1 and hubs[0].entry_id != old_hub.entry_id
    assert hass.states.get(SUMMARY).state == "15.0"


async def test_deleted_hub_stays_deleted_when_nothing_is_left(hass):
    a = _sub("netflix", "Netflix")
    await _setup(hass, a)
    await hass.config_entries.async_remove(a.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(_hubs(hass)[0].entry_id)
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_adding_a_subscription_brings_back_a_missing_hub(hass):
    a = _sub("netflix", "Netflix")
    await _setup(hass, a)
    await hass.config_entries.async_remove(a.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(_hubs(hass)[0].entry_id)
    await hass.async_block_till_done()
    assert _hubs(hass) == []

    b = _sub("spotify", "Spotify", cost=5.0)
    b.add_to_hass(hass)
    await hass.config_entries.async_setup(b.entry_id)
    await hass.async_block_till_done()
    assert len(_hubs(hass)) == 1
    assert hass.states.get(SUMMARY).state == "5.0"


# ---------- config-entry unique_id ----------


async def test_options_flow_keeps_unique_id_in_step_with_the_service(hass):
    a = _sub("dazn", "DAZN")
    await _setup(hass, a)

    r = await hass.config_entries.options.async_init(a.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], _form("netflix"))
    assert r["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert a.unique_id == "netflix_Netflix"

    # "DAZN" is free again: it can be added (before, it was refused as already configured)
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], _form("dazn"))
    assert r["type"] == FlowResultType.CREATE_ENTRY

    # ... and a second Netflix is now detected as a duplicate
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], _form("netflix"))
    assert r["type"] == FlowResultType.ABORT and r["reason"] == "already_configured"


async def test_options_flow_rejects_a_clash_with_another_subscription(hass):
    a, b = _sub("netflix", "Netflix"), _sub("dazn", "DAZN", cost=30.0)
    await _setup(hass, a, b)

    r = await hass.config_entries.options.async_init(b.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], _form("netflix", cost=30.0))
    assert r["type"] == FlowResultType.FORM
    assert r["errors"] == {"base": "duplicate_subscription"}
    assert b.data["service"] == "dazn" and b.unique_id == "dazn_DAZN"


async def test_plan_change_updates_unique_id(hass):
    a = _sub("netflix", "Netflix")
    await _setup(hass, a)
    r = await hass.config_entries.options.async_init(a.entry_id)
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], _form("netflix", plan="Premium")
    )
    assert r["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert a.title == "Netflix (Premium)" and a.unique_id == "netflix_Netflix (Premium)"


async def test_stale_unique_id_is_migrated_at_startup(hass):
    # entry edited with an older version: service is now netflix, unique_id still dazn
    stale = _sub("netflix", "Netflix", unique_id="dazn_DAZN")
    ok = _sub("spotify", "Spotify", cost=5.0)
    await _setup(hass, stale, ok)
    assert stale.unique_id == "netflix_Netflix"
    assert ok.unique_id == "spotify_Spotify"


async def test_stale_unique_id_is_left_alone_when_the_expected_one_is_taken(hass):
    # two entries that would end up with the same unique_id: nothing is overwritten
    a = _sub("netflix", "Netflix")
    stale = _sub("netflix", "Netflix", unique_id="dazn_DAZN")
    await _setup(hass, a, stale)
    assert a.unique_id == "netflix_Netflix"
    assert stale.unique_id == "dazn_DAZN"


async def test_config_flow_dates_follow_the_ha_time_zone(hass, freezer):
    # 23:30 UTC on 11 Nov is already 12 Nov in Rome: the HA date, not the system one
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to(datetime(2026, 11, 11, 23, 30, tzinfo=UTC))
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {"service": "netflix", "cost": 12.99, "currency": "EUR", "billing_cycle": "monthly",
         "renewal_date": "2026-12-12"},
    )
    entry = next(e for e in hass.config_entries.async_entries(DOMAIN) if not e.data.get("hub"))
    assert entry.options["price_history"][0]["date"] == "2026-11-12"


# ---------- midnight rollover (frozen clock) ----------
# The single-subscription sensors also poll every 30 s, so a clock jump refreshes them
# anyway: only the summary sensor (no polling) proves that the midnight timer works.


async def _tick(hass, freezer, when_utc):
    freezer.move_to(when_utc)
    async_fire_time_changed(hass, when_utc)
    await hass.async_block_till_done()


async def test_midnight_updates_days_and_summary(hass, freezer):
    await hass.config.async_set_time_zone("Europe/Rome")
    # 23:59:30 local on 11 Nov (22:59:30 UTC); renewal tomorrow
    freezer.move_to(datetime(2026, 11, 11, 22, 59, 30, tzinfo=UTC))
    a = _sub("netflix", "Netflix", renewal="2026-11-12")
    await _setup(hass, a)
    assert hass.states.get("sensor.netflix").state == "1"
    assert hass.states.get(SUMMARY).attributes["upcoming"][0]["days"] == 1

    # just after local midnight
    await _tick(hass, freezer, datetime(2026, 11, 11, 23, 0, 5, tzinfo=UTC))
    assert hass.states.get("sensor.netflix").state == "0"
    assert hass.states.get(SUMMARY).attributes["upcoming"][0]["days"] == 0

    # and it keeps rescheduling: the next midnight rolls the renewal to next month
    await _tick(hass, freezer, datetime(2026, 11, 12, 23, 0, 5, tzinfo=UTC))
    st = hass.states.get("sensor.netflix")
    assert st.attributes["next_renewal"] == "2026-12-12"
    assert st.state == "29"


async def test_month_end_anchor_across_midnights(hass, freezer):
    await hass.config.async_set_time_zone("Europe/Rome")
    # monthly renewal anchored on 31 Jan: 28 Feb, then back to 31 Mar
    freezer.move_to(datetime(2026, 2, 27, 22, 59, 30, tzinfo=UTC))  # 23:59:30 on 27 Feb
    a = _sub("netflix", "Netflix", renewal="2026-01-31")
    await _setup(hass, a)
    st = hass.states.get("sensor.netflix")
    assert st.attributes["next_renewal"] == "2026-02-28" and st.state == "1"
    assert hass.states.get(SUMMARY).attributes["upcoming"][0]["days"] == 1

    await _tick(hass, freezer, datetime(2026, 2, 27, 23, 0, 5, tzinfo=UTC))  # 28 Feb 00:00
    assert hass.states.get("sensor.netflix").state == "0"
    assert hass.states.get(SUMMARY).attributes["upcoming"][0]["days"] == 0

    await _tick(hass, freezer, datetime(2026, 2, 28, 23, 0, 5, tzinfo=UTC))  # 1 Mar 00:00
    st = hass.states.get("sensor.netflix")
    assert st.attributes["next_renewal"] == "2026-03-31" and st.state == "30"
    assert hass.states.get(SUMMARY).attributes["upcoming"][0]["days"] == 30
