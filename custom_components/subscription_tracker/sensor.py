"""Sensor platform for Subscription Tracker."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util

from .calc import (
    build_summary,
    history_comparison,
    monthly_cost,
    next_renewal,
    parse_date,
    subscription_status,
    update_monthly_history,
)
from .const import (
    CONF_BILLING_CYCLE,
    CONF_BUDGET,
    CONF_CATEGORY,
    CONF_COST,
    CONF_COST_IS_MY_SHARE,
    CONF_CURRENCY,
    CONF_CUSTOM_ICON,
    CONF_CUSTOM_NAME,
    CONF_EXPIRING_SOON_DAYS,
    CONF_HUB,
    CONF_NOTES,
    CONF_PAUSED,
    CONF_PLAN,
    CONF_PRICE_HISTORY,
    CONF_RENEWAL_DATE,
    CONF_SERVICE,
    CONF_SHARED_COUNT,
    CONF_SUBSCRIBED_SINCE,
    CONTRACT_VERSION,
    CUSTOM_SERVICE_KEY,
    DEFAULT_EXPIRING_SOON_DAYS,
    DOMAIN,
    HISTORY_EXPOSED_MONTHS,
    HISTORY_KEEP_MONTHS,
    HISTORY_STORE_KEY,
    HISTORY_STORE_VERSION,
    KNOWN_SERVICES,
    SIGNAL_SUMMARY_UPDATE,
    UPCOMING_DAYS,
)

SUMMARY_UNIQUE_ID = f"{DOMAIN}_summary"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Hub: summary sensor. Other entries: single-subscription sensor."""
    if entry.data.get(CONF_HUB):
        _async_adopt_legacy_summary(hass, entry)
        async_add_entities([SubscriptionSummarySensor(hass, entry)], update_before_add=True)
        return

    async_add_entities([SubscriptionSensor(entry)])


@callback
def _async_adopt_legacy_summary(hass: HomeAssistant, hub: ConfigEntry) -> None:
    """Move to the hub the summary created by versions without a hub.

    Previously the summary was tied to the first loaded subscription: if that
    entry was reloaded or removed, the summary disappeared.
    """
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, SUMMARY_UNIQUE_ID)
    if entity_id is None:
        return
    reg_entry = registry.async_get(entity_id)
    if reg_entry is not None and reg_entry.config_entry_id != hub.entry_id:
        registry.async_update_entity(entity_id, config_entry_id=hub.entry_id)


@callback
def _schedule_midnight(hass: HomeAssistant, action) -> Any:
    """Run `action` at the next local midnight; returns the unsubscribe callback."""
    target = dt_util.start_of_local_day(dt_util.now() + timedelta(days=1))

    @callback
    def _fire(_now: datetime) -> None:
        action()

    return async_track_point_in_time(hass, _fire, target)


class SubscriptionSensor(SensorEntity):
    """A single subscription. State = days left until renewal."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "days"
    _attr_name = None

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._data = dict(entry.data)
        self._options = dict(entry.options)

        key = self._data[CONF_SERVICE]
        known = KNOWN_SERVICES.get(key, KNOWN_SERVICES[CUSTOM_SERVICE_KEY])
        self._service_key = key
        self._known = known

        self._display_name = (
            self._data.get(CONF_CUSTOM_NAME) if key == CUSTOM_SERVICE_KEY else known["name"]
        )
        self._icon = self._data.get(CONF_CUSTOM_ICON) or known["icon"]
        self._category = self._data.get(CONF_CATEGORY) or known["category"]

        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Subscription Tracker",
            model=self._display_name,
        )
        self._unsub_midnight = None

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def available(self) -> bool:
        return True

    def _is_paused(self) -> bool:
        return bool(self._data.get(CONF_PAUSED) or self._options.get(CONF_PAUSED))

    def _anchor(self) -> date | None:
        return parse_date(self._data.get(CONF_RENEWAL_DATE))

    def _renewal(self) -> date | None:
        """Effective next renewal: the entered date advances by itself, one cycle at a time."""
        return next_renewal(
            self._anchor(), self._data.get(CONF_BILLING_CYCLE), dt_util.now().date()
        )

    def _days_remaining(self) -> int | None:
        renewal = self._renewal()
        if renewal is None:
            return None
        return (renewal - dt_util.now().date()).days

    def _status(self) -> str:
        threshold = int(self._data.get(CONF_EXPIRING_SOON_DAYS) or DEFAULT_EXPIRING_SOON_DAYS)
        return subscription_status(self._is_paused(), self._days_remaining(), threshold)

    def _price_history(self) -> list[dict]:
        return sorted(
            self._options.get(CONF_PRICE_HISTORY, []), key=lambda h: h.get("date", "")
        )

    @property
    def native_value(self) -> int | None:
        return self._days_remaining()

    @property
    def extra_state_attributes(self) -> dict:
        cost = float(self._data.get(CONF_COST, 0))
        cycle = self._data.get(CONF_BILLING_CYCLE)
        shared = int(self._data.get(CONF_SHARED_COUNT) or 1)
        my_share = bool(self._data.get(CONF_COST_IS_MY_SHARE))
        history = self._price_history()
        since = parse_date(self._data.get(CONF_SUBSCRIBED_SINCE))
        renewal = self._renewal()
        anchor = self._anchor()

        attrs = {
            "contract_version": CONTRACT_VERSION,
            "service": self._service_key,
            "display_name": self._display_name,
            "category": self._category,
            "color": self._known.get("color"),
            "custom_icon": self._data.get(CONF_CUSTOM_ICON) or None,
            "plan": self._data.get(CONF_PLAN) or None,
            "cost": cost,
            "currency": self._data.get(CONF_CURRENCY, "EUR"),
            "billing_cycle": cycle,
            "monthly_cost": monthly_cost(cost, cycle),
            "yearly_cost": round(monthly_cost(cost, cycle) * 12, 2),
            "next_renewal": renewal.isoformat() if renewal else None,
            "renewal_advanced": bool(renewal and anchor and renewal != anchor),
            "shared_count": shared,
            "cost_per_person": round(cost if my_share else cost / shared, 2),
            "cost_is_my_share": my_share,
            "status": self._status(),
            "paused": self._is_paused(),
            "notes": self._data.get(CONF_NOTES) or None,
            "price_history": history,
        }

        # Payment method deliberately NOT exposed as an attribute:
        # it stays in the configuration only, so it does not end up in the recorder.

        if since:
            attrs["subscribed_since"] = since.isoformat()
            attrs["subscribed_days"] = (dt_util.now().date() - since).days

        if len(history) >= 2:
            first = float(history[0].get("price", cost))
            attrs["price_change_total"] = round(cost - first, 2)
            if first:
                attrs["price_change_pct"] = round((cost - first) / first * 100, 1)
            attrs["price_changes_count"] = len(history) - 1

        return attrs

    async def async_added_to_hass(self) -> None:
        self._schedule_midnight_update()
        async_dispatcher_send(self.hass, SIGNAL_SUMMARY_UPDATE)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_midnight:
            self._unsub_midnight()

    def _schedule_midnight_update(self) -> None:
        @callback
        def _update() -> None:
            self.async_write_ha_state()
            self._schedule_midnight_update()

        self._unsub_midnight = _schedule_midnight(self.hass, _update)


class SubscriptionSummarySensor(SensorEntity):
    """Summary of all subscriptions. State = total monthly cost."""

    _attr_name = "Subscriptions total"
    _attr_unique_id = SUMMARY_UNIQUE_ID
    _attr_icon = "mdi:cash-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, hub: ConfigEntry) -> None:
        self._hass = hass
        self._hub = hub
        self._monthly = 0.0
        self._attrs: dict = {}
        self._unsub_midnight = None
        self._store: Store = Store(hass, HISTORY_STORE_VERSION, HISTORY_STORE_KEY)
        self._history: list[dict] | None = None

    @property
    def native_unit_of_measurement(self) -> str:
        return self._attrs.get("currency", "EUR")

    @property
    def native_value(self) -> float:
        return self._monthly

    @property
    def extra_state_attributes(self) -> dict:
        return self._attrs

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_SUMMARY_UPDATE, self._handle_signal)
        )
        self._schedule_midnight_update()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_midnight:
            self._unsub_midnight()

    @callback
    def _handle_signal(self) -> None:
        self.async_schedule_update_ha_state(True)

    def _schedule_midnight_update(self) -> None:
        @callback
        def _update() -> None:
            self.async_schedule_update_ha_state(True)
            self._schedule_midnight_update()

        self._unsub_midnight = _schedule_midnight(self.hass, _update)

    def _collect(self) -> list[dict[str, Any]]:
        subs: list[dict[str, Any]] = []
        for entry in self._hass.config_entries.async_entries(DOMAIN):
            data = entry.data
            if data.get(CONF_HUB) or not data.get(CONF_SERVICE):
                continue
            known = KNOWN_SERVICES.get(data[CONF_SERVICE], KNOWN_SERVICES[CUSTOM_SERVICE_KEY])
            subs.append(
                {
                    "name": entry.title,
                    "display_name": (
                        data.get(CONF_CUSTOM_NAME)
                        if data[CONF_SERVICE] == CUSTOM_SERVICE_KEY
                        else known["name"]
                    ),
                    "service": data[CONF_SERVICE],
                    "category": data.get(CONF_CATEGORY) or known["category"],
                    "cost": float(data.get(CONF_COST, 0)),
                    "currency": data.get(CONF_CURRENCY, "EUR"),
                    "cycle": data.get(CONF_BILLING_CYCLE),
                    "anchor": parse_date(data.get(CONF_RENEWAL_DATE)),
                    "paused": bool(data.get(CONF_PAUSED) or entry.options.get(CONF_PAUSED)),
                    "threshold": int(
                        data.get(CONF_EXPIRING_SOON_DAYS) or DEFAULT_EXPIRING_SOON_DAYS
                    ),
                }
            )
        return subs

    async def async_update(self) -> None:
        budget = self._hub.options.get(CONF_BUDGET)
        result = build_summary(
            self._collect(),
            dt_util.now().date(),
            float(budget) if budget else None,
            UPCOMING_DAYS,
        )
        self._monthly = result["monthly"]
        attrs = result["attributes"]
        today = dt_util.now().date()

        if self._history is None:
            stored = await self._store.async_load()
            self._history = list(stored.get("months", [])) if isinstance(stored, dict) else []
        updated = update_monthly_history(
            self._history, today, self._monthly, attrs["currency"], HISTORY_KEEP_MONTHS
        )
        if updated != self._history:
            self._history = updated
            self._store.async_delay_save(self._history_to_save, 30)

        self._attrs = {
            "contract_version": CONTRACT_VERSION,
            **attrs,
            **history_comparison(self._history, today, self._monthly, attrs["currency"]),
            "monthly_history": self._history[-HISTORY_EXPOSED_MONTHS:],
        }

    @callback
    def _history_to_save(self) -> dict:
        return {"months": self._history or []}
