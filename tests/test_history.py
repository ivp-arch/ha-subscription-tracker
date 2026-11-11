"""Monthly history of the summary: comparison with the previous month."""
from datetime import UTC, date, datetime

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.subscription_tracker.calc import (
    history_comparison,
    previous_month_key,
    update_monthly_history,
)
from custom_components.subscription_tracker.const import DOMAIN, HISTORY_STORE_KEY

SUMMARY = "sensor.subscriptions_total"


def _sub(service, name, cost, renewal="2027-01-15", currency="EUR"):
    return MockConfigEntry(
        domain=DOMAIN,
        title=name,
        unique_id=f"{service}_{name}",
        data={"service": service, "cost": cost, "currency": currency,
              "billing_cycle": "monthly", "renewal_date": renewal},
        options={},
    )


async def _setup(hass, *entries):
    for e in entries:
        e.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entries[0].entry_id)
    await hass.async_block_till_done()


def _attrs(hass):
    return hass.states.get(SUMMARY).attributes


# ---------- pure functions ----------


def test_previous_month_key_handles_january_and_month_ends():
    assert previous_month_key(date(2026, 1, 31)) == "2025-12"
    assert previous_month_key(date(2026, 3, 1)) == "2026-02"
    assert previous_month_key(date(2026, 11, 11)) == "2026-10"


def test_update_replaces_current_month_keeps_earlier_and_trims():
    h = [{"month": "2026-09", "total": 10.0, "currency": "EUR"}]
    h = update_monthly_history(h, date(2026, 10, 3), 12.0, "EUR", 24)
    h = update_monthly_history(h, date(2026, 10, 20), 15.5, "EUR", 24)
    assert h == [
        {"month": "2026-09", "total": 10.0, "currency": "EUR"},
        {"month": "2026-10", "total": 15.5, "currency": "EUR"},
    ]
    many = [{"month": f"2024-{m:02d}", "total": 1.0, "currency": "EUR"} for m in range(1, 13)]
    many += [{"month": f"2025-{m:02d}", "total": 1.0, "currency": "EUR"} for m in range(1, 13)]
    trimmed = update_monthly_history(many, date(2026, 1, 5), 2.0, "EUR", 24)
    assert len(trimmed) == 24 and trimmed[0]["month"] == "2024-02" and trimmed[-1]["month"] == "2026-01"


def test_comparison_values_and_missing_cases():
    h = [{"month": "2026-10", "total": 20.0, "currency": "EUR"}]
    up = history_comparison(h, date(2026, 11, 5), 25.0, "EUR")
    assert up == {"previous_month_cost": 20.0, "change_vs_previous": 5.0, "change_vs_previous_pct": 25.0}
    down = history_comparison(h, date(2026, 11, 5), 15.0, "EUR")
    assert down["change_vs_previous"] == -5.0 and down["change_vs_previous_pct"] == -25.0
    none = {"previous_month_cost": None, "change_vs_previous": None, "change_vs_previous_pct": None}
    assert history_comparison(h, date(2026, 12, 5), 25.0, "EUR") == none  # gap: October is not "previous"
    assert history_comparison(h, date(2026, 11, 5), 25.0, "USD") == none  # other currency
    zero = [{"month": "2026-10", "total": 0.0, "currency": "EUR"}]
    z = history_comparison(zero, date(2026, 11, 5), 5.0, "EUR")
    assert z["change_vs_previous"] == 5.0 and z["change_vs_previous_pct"] is None


# ---------- integration ----------


async def test_first_month_has_no_comparison(hass, freezer):
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to(datetime(2026, 11, 11, 10, 0, tzinfo=UTC))
    await _setup(hass, _sub("netflix", "Netflix", 10.0))
    a = _attrs(hass)
    assert a["previous_month_cost"] is None and a["change_vs_previous"] is None
    assert a["change_vs_previous_pct"] is None
    assert a["monthly_history"] == [{"month": "2026-11", "total": 10.0, "currency": "EUR"}]


async def test_comparison_uses_stored_previous_month(hass, freezer, hass_storage):
    hass_storage[HISTORY_STORE_KEY] = {
        "version": 1,
        "key": HISTORY_STORE_KEY,
        "data": {"months": [{"month": "2026-10", "total": 8.0, "currency": "EUR"}]},
    }
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to(datetime(2026, 11, 11, 10, 0, tzinfo=UTC))
    await _setup(hass, _sub("netflix", "Netflix", 10.0))
    a = _attrs(hass)
    assert a["previous_month_cost"] == 8.0
    assert a["change_vs_previous"] == 2.0 and a["change_vs_previous_pct"] == 25.0
    assert [m["month"] for m in a["monthly_history"]] == ["2026-10", "2026-11"]


async def test_history_is_saved_and_month_rollover_freezes_the_total(hass, freezer, hass_storage):
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to(datetime(2026, 11, 30, 22, 59, 30, tzinfo=UTC))  # 23:59:30 on 30 Nov
    a, b = _sub("netflix", "Netflix", 10.0), _sub("spotify", "Spotify", 5.0)
    await _setup(hass, a, b)
    assert hass.states.get(SUMMARY).state == "15.0"

    # delayed save fires: the November total is persisted
    freezer.move_to(datetime(2026, 11, 30, 22, 59, 59, tzinfo=UTC))
    async_fire_time_changed(hass, datetime(2026, 11, 30, 23, 0, 40, tzinfo=UTC))
    await hass.async_block_till_done()
    assert hass_storage[HISTORY_STORE_KEY]["data"]["months"][-1] == {
        "month": "2026-11", "total": 15.0, "currency": "EUR"
    }

    # midnight in Rome: November is frozen, December starts with the same total
    freezer.move_to(datetime(2026, 11, 30, 23, 0, 5, tzinfo=UTC))
    async_fire_time_changed(hass, datetime(2026, 11, 30, 23, 0, 5, tzinfo=UTC))
    await hass.async_block_till_done()
    at = _attrs(hass)
    assert at["previous_month_cost"] == 15.0 and at["change_vs_previous"] == 0.0
    assert [m["month"] for m in at["monthly_history"]] == ["2026-11", "2026-12"]

    # a change in December is compared with the frozen November total
    await hass.config_entries.async_remove(b.entry_id)
    await hass.async_block_till_done()
    at = _attrs(hass)
    assert at["previous_month_cost"] == 15.0
    assert at["change_vs_previous"] == -5.0 and at["change_vs_previous_pct"] == -33.3
    assert at["monthly_history"][0] == {"month": "2026-11", "total": 15.0, "currency": "EUR"}


async def test_history_is_removed_with_the_last_entry(hass, freezer, hass_storage):
    hass_storage[HISTORY_STORE_KEY] = {
        "version": 1, "key": HISTORY_STORE_KEY,
        "data": {"months": [{"month": "2026-10", "total": 8.0, "currency": "EUR"}]},
    }
    freezer.move_to(datetime(2026, 11, 11, 10, 0, tzinfo=UTC))
    a = _sub("netflix", "Netflix", 10.0)
    await _setup(hass, a)
    hub = next(e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("hub"))

    # hub deleted while a subscription exists: history survives (hub is recreated)
    await hass.config_entries.async_remove(hub.entry_id)
    await hass.async_block_till_done()
    assert HISTORY_STORE_KEY in hass_storage
    assert _attrs(hass)["previous_month_cost"] == 8.0

    # nothing left: history is deleted too
    await hass.config_entries.async_remove(a.entry_id)
    await hass.async_block_till_done()
    hub = next(e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("hub"))
    await hass.config_entries.async_remove(hub.entry_id)
    await hass.async_block_till_done()
    assert HISTORY_STORE_KEY not in hass_storage
