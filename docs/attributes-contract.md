# Attribute contract — version 1

This document is the contract between the integration (data, calculations, entities) and the cards (presentation only). Every sensor exposes `contract_version: 1`.

**Versioning rules.** Adding an attribute does not change the version. Removing or renaming an existing attribute, or changing its type or meaning, requires incrementing `contract_version` and updating this file and the cards. Cards must ignore attributes they do not know.

**Data never exposed.** The payment method (`payment_note`) does not appear in any attribute of any entity. A test verifies it (`test_payment_method_never_in_attributes`). It does remain in the integration's configuration and therefore in Home Assistant backups.

## Single subscription sensor

State: days until the next renewal (integer, never negative if the date is valid), unit `days`.

| Attribute | Type | Notes |
|---|---|---|
| `contract_version` | int | Always `1` |
| `service` | str | Service key (`netflix`, `other`, ...) |
| `display_name` | str | Displayable name |
| `category` | str | `video`, `audio`, `other` |
| `color` | str \| null | Hex; `null` for custom services |
| `custom_icon` | str \| null | `mdi:` icon chosen by the user for this subscription; `null` if not set. Cards use their own generic icons unless this is set |
| `plan` | str \| null | Plan/tier |
| `cost` | float | Cost per cycle |
| `currency` | str | `EUR`, `USD`, `GBP` |
| `billing_cycle` | str | `monthly`, `quarterly`, `yearly` |
| `monthly_cost` / `yearly_cost` | float | Normalized cost |
| `next_renewal` | str (ISO) \| null | **Effective** next renewal (see below) |
| `renewal_advanced` | bool | `true` if `next_renewal` differs from the entered date |
| `shared_count` | int | People sharing (≥ 1) |
| `cost_per_person` | float | `cost / shared_count` |
| `status` | str | `active`, `expiring_soon`, `paused`. `expired` is reserved and is not produced |
| `paused` | bool | |
| `notes` | str \| null | Free text: do not enter personal data, it ends up in the recorder |
| `price_history` | list | `[{date, price}]` sorted by date |
| `subscribed_since`, `subscribed_days` | str (ISO), int | Only if "Customer since" is set |
| `price_change_total`, `price_change_pct`, `price_changes_count` | float, float, int | Only with at least 2 history points |

**Automatic renewal.** The date entered by the user is an anchor: `next_renewal` is the first date equal to or after today obtained by adding whole cycles to the anchor (it always starts from the anchor, so a monthly renewal on January 31 falls on February 28 and goes back to March 31). Nothing is written to the configuration. To stop the count use "paused".

## Summary sensor (`sensor.subscriptions_total`)

Owned by the "Subscription summary" entry (hub), created automatically. State: total monthly cost of the non-paused subscriptions, in the prevailing currency.

| Attribute | Type | Notes |
|---|---|---|
| `contract_version` | int | `1` |
| `currency` | str | Prevailing currency among active subscriptions (`EUR` if there are none) |
| `mixed_currency` | bool | `true` if there are subscriptions in other currencies |
| `other_currency_count` | int | How many active subscriptions are excluded from the totals because of a different currency. No exchange-rate conversion |
| `yearly_cost` | float | |
| `active_count`, `paused_count` | int | |
| `by_category` | dict str→float | Monthly cost per category |
| `expiring_count`, `expiring_soon_total` | int, float | Renewals within the notice threshold of each subscription |
| `expiring` | list | Items as below, sorted by days |
| `upcoming_days` | int | Timeline window, currently `30` |
| `upcoming` | list | Renewals within `upcoming_days`, sorted by days and name |
| `upcoming_total` | float | Sum of the costs in `upcoming` |
| `budget` | float \| null | Monthly threshold set in the hub; `null` if not set or 0 |
| `budget_used_pct` | float \| null | Monthly spend / budget × 100, one decimal; `null` without a budget |
| `budget_remaining` | float \| null | `budget - spend`; negative if exceeded |
| `budget_exceeded` | bool | `true` if the monthly spend exceeds the budget |
| `previous_month_cost` | float \| null | Monthly total recorded for the previous calendar month; `null` if that month was not recorded (first month after installation, gaps) or was in another currency |
| `change_vs_previous` | float \| null | Current total − `previous_month_cost`; negative if spending went down. `null` when there is no previous month |
| `change_vs_previous_pct` | float \| null | `change_vs_previous` / `previous_month_cost` × 100, one decimal; `null` when there is no previous month or it was 0 |
| `monthly_history` | list | `[{month, total, currency}]`, oldest first, at most the last 12 months **including the current one**. `month` is `YYYY-MM` in the Home Assistant time zone |

Item of `expiring` and `upcoming`: `{name, display_name, service, days, cost, renewal}`, with `days` ≥ 0, `renewal` ISO, `cost` per cycle. `name` is the entry title (service and plan, e.g. "Netflix (Premium)"); `display_name` is the service name, the same as the single-subscription sensor attribute ("Netflix"). Cards should show `display_name`.

The budget is set from Settings → Devices & services → Subscription Tracker → "Subscription summary" → Configure.

**Monthly history.** The "month" is the normalized monthly total (the state of the summary), not what was actually charged. The integration records the latest total of the current month in its own file (`.storage/subscription_tracker.monthly_history`, last 24 months kept, 12 exposed); when the month changes the value stops being updated, so each past month holds the total as it was on its last day. History starts at installation: until a full previous month has been recorded the comparison attributes are `null`, and cards must hide the comparison instead of showing 0. The file is not part of any subscription: it survives deleting and recreating the summary entry, and is removed together with the last Subscription Tracker entry.
