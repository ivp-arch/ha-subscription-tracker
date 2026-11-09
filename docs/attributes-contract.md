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

Item of `expiring` and `upcoming`: `{name, service, days, cost, renewal}`, with `days` ≥ 0, `renewal` ISO, `cost` per cycle.

The budget is set from Settings → Devices & services → Subscription Tracker → "Subscription summary" → Configure.

## Not included in version 1

The change in spending compared to the previous month (used in the Orbit mockup) requires a monthly history of the total that does not exist today: it is not part of the contract.
