"""Piattaforma sensore per Subscription Tracker."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
import homeassistant.util.dt as dt_util

from .const import (
    BILLING_CYCLE_MONTHS,
    CONF_BILLING_CYCLE,
    CONF_CATEGORY,
    CONF_COST,
    CONF_CURRENCY,
    CONF_CUSTOM_ICON,
    CONF_CUSTOM_NAME,
    CONF_EXPIRING_SOON_DAYS,
    CONF_NOTES,
    CONF_PAUSED,
    CONF_PLAN,
    CONF_PRICE_HISTORY,
    CONF_RENEWAL_DATE,
    CONF_SERVICE,
    CONF_SHARED_COUNT,
    CONF_SUBSCRIBED_SINCE,
    CUSTOM_SERVICE_KEY,
    DEFAULT_EXPIRING_SOON_DAYS,
    DOMAIN,
    KNOWN_SERVICES,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_EXPIRING_SOON,
    STATUS_PAUSED,
)

SUMMARY_UNIQUE_ID = f"{DOMAIN}_summary"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Crea il sensore dell'abbonamento e, una sola volta, quello di riepilogo."""
    entities: list[SensorEntity] = [SubscriptionSensor(entry)]

    if not hass.data[DOMAIN].get("summary_created"):
        hass.data[DOMAIN]["summary_created"] = True
        entities.append(SubscriptionSummarySensor(hass))

    async_add_entities(entities)


def _parse_date(raw) -> date | None:
    if not raw:
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def _monthly_cost(cost: float, cycle: str) -> float:
    return round(float(cost) / BILLING_CYCLE_MONTHS.get(cycle, 1), 2)


class SubscriptionSensor(SensorEntity):
    """Un singolo abbonamento. Stato = giorni rimanenti al rinnovo."""

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

    def _renewal(self) -> date | None:
        return _parse_date(self._data.get(CONF_RENEWAL_DATE))

    def _days_remaining(self) -> int | None:
        renewal = self._renewal()
        if renewal is None:
            return None
        return (renewal - dt_util.now().date()).days

    def _status(self) -> str:
        if self._is_paused():
            return STATUS_PAUSED
        days = self._days_remaining()
        if days is None:
            return STATUS_ACTIVE
        threshold = int(self._data.get(CONF_EXPIRING_SOON_DAYS) or DEFAULT_EXPIRING_SOON_DAYS)
        if days < 0:
            return STATUS_EXPIRED
        if days <= threshold:
            return STATUS_EXPIRING_SOON
        return STATUS_ACTIVE

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
        history = self._price_history()
        since = _parse_date(self._data.get(CONF_SUBSCRIBED_SINCE))

        attrs = {
            "service": self._service_key,
            "display_name": self._display_name,
            "category": self._category,
            "color": self._known.get("color"),
            "plan": self._data.get(CONF_PLAN) or None,
            "cost": cost,
            "currency": self._data.get(CONF_CURRENCY, "EUR"),
            "billing_cycle": cycle,
            "monthly_cost": _monthly_cost(cost, cycle),
            "yearly_cost": round(_monthly_cost(cost, cycle) * 12, 2),
            "next_renewal": self._renewal().isoformat() if self._renewal() else None,
            "shared_count": shared,
            "cost_per_person": round(cost / shared, 2),
            "status": self._status(),
            "paused": self._is_paused(),
            "notes": self._data.get(CONF_NOTES) or None,
            "price_history": history,
        }

        # Metodo di pagamento volutamente NON esposto come attributo:
        # resta solo nella configurazione, per non finire nel recorder.

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

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_midnight:
            self._unsub_midnight()

    def _schedule_midnight_update(self) -> None:
        target = dt_util.start_of_local_day(dt_util.now() + timedelta(days=1))

        @callback
        def _update(_now: datetime) -> None:
            self.async_write_ha_state()
            self._schedule_midnight_update()

        self._unsub_midnight = async_track_point_in_time(self.hass, _update, target)


class SubscriptionSummarySensor(SensorEntity):
    """Riepilogo di tutti gli abbonamenti. Stato = costo mensile totale."""

    _attr_name = "Abbonamenti totale"
    _attr_unique_id = SUMMARY_UNIQUE_ID
    _attr_icon = "mdi:cash-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = True

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._monthly = 0.0
        self._attrs: dict = {}

    @property
    def native_unit_of_measurement(self) -> str:
        return self._attrs.get("currency", "EUR")

    @property
    def native_value(self) -> float:
        return self._monthly

    @property
    def extra_state_attributes(self) -> dict:
        return self._attrs

    async def async_update(self) -> None:
        entries = self._hass.config_entries.async_entries(DOMAIN)

        today = dt_util.now().date()
        monthly = 0.0
        active = 0
        paused = 0
        expiring: list[dict] = []
        by_category: dict[str, float] = {}
        currency = "EUR"

        for entry in entries:
            data = entry.data
            if not data.get(CONF_SERVICE):
                continue

            is_paused = bool(data.get(CONF_PAUSED) or entry.options.get(CONF_PAUSED))
            if is_paused:
                paused += 1
                continue

            active += 1
            cost = float(data.get(CONF_COST, 0))
            cycle = data.get(CONF_BILLING_CYCLE)
            m = _monthly_cost(cost, cycle)
            monthly += m
            currency = data.get(CONF_CURRENCY, currency)

            known = KNOWN_SERVICES.get(data[CONF_SERVICE], KNOWN_SERVICES[CUSTOM_SERVICE_KEY])
            category = data.get(CONF_CATEGORY) or known["category"]
            by_category[category] = round(by_category.get(category, 0.0) + m, 2)

            renewal = _parse_date(data.get(CONF_RENEWAL_DATE))
            if renewal:
                days = (renewal - today).days
                threshold = int(data.get(CONF_EXPIRING_SOON_DAYS) or DEFAULT_EXPIRING_SOON_DAYS)
                if 0 <= days <= threshold:
                    expiring.append(
                        {
                            "name": entry.title,
                            "days": days,
                            "cost": cost,
                            "renewal": renewal.isoformat(),
                        }
                    )

        expiring.sort(key=lambda e: e["days"])

        self._monthly = round(monthly, 2)
        self._attrs = {
            "currency": currency,
            "yearly_cost": round(monthly * 12, 2),
            "active_count": active,
            "paused_count": paused,
            "expiring_count": len(expiring),
            "expiring": expiring,
            "by_category": by_category,
            "expiring_soon_total": round(sum(e["cost"] for e in expiring), 2),
        }
