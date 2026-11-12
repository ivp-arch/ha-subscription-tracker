"""Config flow for Subscription Tracker."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.util import dt as dt_util
from homeassistant.helpers.selector import (
    BooleanSelector,
    DateSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    BILLING_CYCLE_MONTHLY,
    BILLING_CYCLES,
    CATEGORIES,
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
    CONF_PAYMENT_NOTE,
    CONF_PLAN,
    CONF_PRICE_HISTORY,
    CONF_RENEWAL_DATE,
    CONF_SERVICE,
    CONF_SHARED_COUNT,
    CONF_SUBSCRIBED_SINCE,
    CURRENCIES,
    CUSTOM_SERVICE_KEY,
    DEFAULT_EXPIRING_SOON_DAYS,
    DOMAIN,
    HUB_TITLE,
    HUB_UNIQUE_ID,
    KNOWN_SERVICES,
)


def _service_options() -> list[dict[str, str]]:
    return [{"value": key, "label": info["name"]} for key, info in KNOWN_SERVICES.items()]


def _build_schema(defaults: dict[str, Any] | None = None, *, is_options: bool = False) -> vol.Schema:
    """Form schema. The options flow also shows the 'paused' flag."""
    d = defaults or {}

    schema: dict[Any, Any] = {
        vol.Required(CONF_SERVICE, default=d.get(CONF_SERVICE)): SelectSelector(
            SelectSelectorConfig(options=_service_options(), mode=SelectSelectorMode.DROPDOWN)
        ),
        vol.Optional(CONF_CUSTOM_NAME, default=d.get(CONF_CUSTOM_NAME, "")): TextSelector(),
        vol.Optional(CONF_CUSTOM_ICON, default=d.get(CONF_CUSTOM_ICON, "")): TextSelector(),
        vol.Optional(CONF_CATEGORY, default=d.get(CONF_CATEGORY, "")): SelectSelector(
            SelectSelectorConfig(options=[""] + CATEGORIES, mode=SelectSelectorMode.DROPDOWN)
        ),
        vol.Optional(CONF_PLAN, default=d.get(CONF_PLAN, "")): TextSelector(),
        vol.Required(CONF_COST, default=d.get(CONF_COST, 0.0)): NumberSelector(
            NumberSelectorConfig(min=0, step=0.01, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(CONF_CURRENCY, default=d.get(CONF_CURRENCY, "EUR")): SelectSelector(
            SelectSelectorConfig(options=CURRENCIES, mode=SelectSelectorMode.DROPDOWN)
        ),
        vol.Required(
            CONF_BILLING_CYCLE, default=d.get(CONF_BILLING_CYCLE, BILLING_CYCLE_MONTHLY)
        ): SelectSelector(SelectSelectorConfig(options=BILLING_CYCLES, mode=SelectSelectorMode.DROPDOWN)),
        vol.Required(
            CONF_RENEWAL_DATE, default=d.get(CONF_RENEWAL_DATE, dt_util.now().date().isoformat())
        ): DateSelector(),
        # No "" default: DateSelector validates with cv.date and rejects the empty string.
        vol.Optional(
            CONF_SUBSCRIBED_SINCE,
            description={"suggested_value": d.get(CONF_SUBSCRIBED_SINCE) or None},
        ): DateSelector(),
        vol.Optional(CONF_SHARED_COUNT, default=d.get(CONF_SHARED_COUNT, 1)): NumberSelector(
            NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(
            CONF_COST_IS_MY_SHARE, default=d.get(CONF_COST_IS_MY_SHARE, False)
        ): BooleanSelector(),
        vol.Optional(CONF_PAYMENT_NOTE, default=d.get(CONF_PAYMENT_NOTE, "")): TextSelector(),
        vol.Optional(
            CONF_EXPIRING_SOON_DAYS, default=d.get(CONF_EXPIRING_SOON_DAYS, DEFAULT_EXPIRING_SOON_DAYS)
        ): NumberSelector(NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX)),
        vol.Optional(CONF_NOTES, default=d.get(CONF_NOTES, "")): TextSelector(),
    }

    if is_options:
        schema[vol.Optional(CONF_PAUSED, default=d.get(CONF_PAUSED, False))] = BooleanSelector()

    return vol.Schema(schema)


def _display_name(user_input: dict[str, Any]) -> str:
    key = user_input[CONF_SERVICE]
    if key == CUSTOM_SERVICE_KEY:
        return user_input.get(CONF_CUSTOM_NAME, "")
    return KNOWN_SERVICES[key]["name"]


def _title(user_input: dict[str, Any]) -> str:
    name = _display_name(user_input)
    plan = user_input.get(CONF_PLAN)
    return f"{name} ({plan})" if plan else name


class SubscriptionTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Add a new subscription."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input[CONF_SERVICE] == CUSTOM_SERVICE_KEY and not user_input.get(CONF_CUSTOM_NAME):
                errors[CONF_CUSTOM_NAME] = "custom_name_required"
            else:
                title = _title(user_input)
                await self.async_set_unique_id(f"{user_input[CONF_SERVICE]}_{title}")
                self._abort_if_unique_id_configured()

                # The initial price opens the history, dated to the creation day.
                options = {
                    CONF_PRICE_HISTORY: [
                        {"date": dt_util.now().date().isoformat(), "price": float(user_input[CONF_COST])}
                    ]
                }
                return self.async_create_entry(title=title, data=user_input, options=options)

        return self.async_show_form(step_id="user", data_schema=_build_schema(), errors=errors)

    async def async_step_import(self, import_data: dict[str, Any] | None = None):
        """Create the hub entry (summary + budget), only one."""
        await self.async_set_unique_id(HUB_UNIQUE_ID)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=HUB_TITLE, data={CONF_HUB: True})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        if config_entry.data.get(CONF_HUB):
            return HubOptionsFlow(config_entry)
        return SubscriptionTrackerOptionsFlow(config_entry)


class SubscriptionTrackerOptionsFlow(config_entries.OptionsFlow):
    """Edit an already configured subscription."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input[CONF_SERVICE] == CUSTOM_SERVICE_KEY and not user_input.get(CONF_CUSTOM_NAME):
                errors[CONF_CUSTOM_NAME] = "custom_name_required"
            else:
                history = list(self._config_entry.options.get(CONF_PRICE_HISTORY, []))
                old_cost = float(self._config_entry.data.get(CONF_COST, 0))
                new_cost = float(user_input[CONF_COST])

                # Automatic capture: if the cost changes, record the change with today's date.
                if abs(new_cost - old_cost) > 0.001:
                    today = dt_util.now().date().isoformat()
                    history = [h for h in history if h.get("date") != today]
                    history.append({"date": today, "price": new_cost})
                    history.sort(key=lambda h: h["date"])

                title = _title(user_input)
                unique_id = f"{user_input[CONF_SERVICE]}_{title}"
                # Keep the config entry unique_id in step with service and plan, so
                # duplicate detection stays correct; refuse a clash with another entry.
                if any(
                    e.unique_id == unique_id and e.entry_id != self._config_entry.entry_id
                    for e in self.hass.config_entries.async_entries(DOMAIN)
                ):
                    errors["base"] = "duplicate_subscription"
                else:
                    options = {**self._config_entry.options, CONF_PRICE_HISTORY: history}
                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        title=title,
                        unique_id=unique_id,
                        data=user_input,
                        options=options,
                    )
                    # Home Assistant stores the returned data as the entry options: it must
                    # be the full options, otherwise the price history would be wiped.
                    return self.async_create_entry(title="", data=options)

        current = dict(self._config_entry.data)
        current.setdefault(CONF_PAUSED, self._config_entry.options.get(CONF_PAUSED, False))
        return self.async_show_form(
            step_id="init", data_schema=_build_schema(current, is_options=True), errors=errors
        )


class HubOptionsFlow(config_entries.OptionsFlow):
    """Global settings: monthly budget threshold."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        return await self.async_step_hub(user_input)

    async def async_step_hub(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data={CONF_BUDGET: float(user_input[CONF_BUDGET])})

        current = float(self._config_entry.options.get(CONF_BUDGET) or 0)
        return self.async_show_form(
            step_id="hub",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BUDGET, default=current): NumberSelector(
                        NumberSelectorConfig(min=0, step=0.01, mode=NumberSelectorMode.BOX)
                    )
                }
            ),
        )
