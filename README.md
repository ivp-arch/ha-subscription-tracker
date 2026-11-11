# Subscription Tracker for Home Assistant

Custom integration to track streaming subscriptions: Netflix, Prime Video, Disney+, Paramount+, Crunchyroll, HBO Max, NOW TV, Chili, Apple TV+, DAZN, RaiPlay+, Mediaset Infinity+, TIMvision, Sky, Discovery+, Spotify, Apple Music, Amazon Music, YouTube Music, Tidal, Audible — plus any custom service ("Other").

The user interface of the integration is currently in Italian and English.

## Data entered by the user

Service name (with pre-mapped icon and color), plan/tier, cost per cycle, billing cycle, next renewal date, first subscription date, number of people sharing the account, category, payment method (text note), free notes, "paused" flag.

## Automatically derived data

Each subscription creates a sensor with **state = days until renewal** and these attributes:

| Attribute | Description |
|---|---|
| `monthly_cost` / `yearly_cost` | Normalized cost, so yearly plans are comparable with monthly ones |
| `cost_per_person` | Cost divided by the number of people sharing |
| `status` | `active` / `expiring_soon` / `paused` |
| `subscribed_days` | For how many days you have been a customer |
| `price_history` | List of `{date, price}` |
| `price_change_total` / `price_change_pct` / `price_changes_count` | Change compared to the first known price |
| `next_renewal` | Effective next renewal (advances by itself, one cycle at a time) |
| `color`, `category`, `display_name` | For rendering in the card |
| `custom_icon` | Icon chosen by the user in the options, or `null`; the card shows it instead of its generic icon |

The payment method is **never** exposed as an attribute: it only stays in the configuration, so it does not end up in the recorder database. Note that the configuration is part of Home Assistant backups, so write a generic note (e.g. "Personal card"), not card digits. Free notes are also visible in the attributes: no personal data.

### Summary sensor and the "Subscription summary" entry

`sensor.subscriptions_total` — state = total monthly cost. It belongs to a dedicated entry, "Subscription summary", created automatically, so it does not depend on any single subscription. Main attributes: `yearly_cost`, `active_count`, `paused_count`, `by_category`, `expiring` (renewals within the notice period), `upcoming` (timeline of renewals in the next 30 days) and `upcoming_total`, `budget`, `budget_used_pct`, `budget_remaining`, `budget_exceeded`. The full list, with types and versioning rules, is in [`docs/attributes-contract.md`](docs/attributes-contract.md).

**Monthly budget.** Set it from Devices & services → Subscription Tracker → "Subscription summary" → Configure. A value of 0 disables the threshold.

If you delete the "Subscription summary" entry while subscriptions still exist, it is created again right away (the budget is reset to none). Once no subscription is left, deleting it is final.

**Mixed currencies.** There is no exchange-rate conversion: totals only sum the subscriptions in the prevailing currency; `mixed_currency` and `other_currency_count` report the excluded ones.

**Automatic renewal.** The renewal date you enter is an anchor: the sensor computes the next renewal by itself by adding whole cycles, without writing anything to the configuration. To stop the count use "paused".

## Price history

It works in two combined ways:

- **Automatic** — when you change the cost from the integration's Options, the change is recorded with today's date.
- **Manual, retroactive** — the `subscription_tracker.add_price_history` service lets you enter prices from before the installation, so the chart is populated right away.

```yaml
service: subscription_tracker.add_price_history
data:
  entity_id: sensor.netflix_premium
  price: 12.99
  date: "2021-03-01"
```

## Installation

### Home Assistant Marketplace (2026.11 or later)
1. Settings → Marketplace → menu (⋮) → **Add from link** (requires connecting a GitHub account)
2. Enter `ivp-arch/ha-subscription-tracker`
3. Install "Subscription Tracker" and restart Home Assistant

### HACS (Home Assistant before 2026.11)
HACS → Integrations → menu (⋮) → Custom repositories → add this repo's URL, category "Integration".

### Manual
Copy `custom_components/subscription_tracker` into the `custom_components` folder of your instance, then restart.

## Configuration

Settings → Devices & services → Add integration → "Subscription Tracker". Repeat for each subscription. Data can be edited from the integration's Options, without removing and recreating it.

## Automations

The summary sensor makes the most useful automations simple:

```yaml
# Weekly notice about upcoming renewals
trigger:
  - platform: time
    at: "09:00:00"
condition:
  - condition: template
    value_template: "{{ state_attr('sensor.subscriptions_total','expiring_count') | int > 0 }}"
action:
  - service: notify.mobile_app
    data:
      title: Upcoming renewals
      message: >-
        {% for s in state_attr('sensor.subscriptions_total','expiring') %}
        {{ s.name }}: {{ s.cost }} € in {{ s.days }} days.
        {% endfor %}
```

```yaml
# Budget threshold exceeded (the budget is set in the "Subscription summary" entry)
trigger:
  - platform: state
    entity_id: sensor.subscriptions_total
    attribute: budget_exceeded
    to: true
action:
  - service: notify.mobile_app
    data:
      message: "Subscription spending is above the monthly budget."
```

```yaml
# Price increase detected on a service
trigger:
  - platform: state
    entity_id: sensor.netflix_premium
    attribute: price_changes_count
action:
  - service: notify.mobile_app
    data:
      message: >-
        Netflix changed its price: now {{ state_attr('sensor.netflix_premium','cost') }} €,
        {{ state_attr('sensor.netflix_premium','price_change_pct') }} % compared to the start.
```

## Development

Calculations live in `custom_components/subscription_tracker/calc.py`, with no dependency on Home Assistant. The tests (`tests/`) use `pytest-homeassistant-custom-component`:

```bash
pip install -r requirements_test.txt
pytest
```

## Roadmap

- Selector option labels translated in the configuration UI
- Ready-to-use automation blueprints

The companion Lovelace card (budget, timeline, "Orbit" theme) lives in the [card repository](https://github.com/ivp-arch/ha-subscription-tracker-card).

## Note

The integration does not connect to real service accounts: data is entered manually. It handles no credentials or payments.
