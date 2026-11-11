"""Pure calculations for Subscription Tracker.

No dependency on Home Assistant: inputs and outputs are basic types, so the
logic (renewals, totals, budget, timeline) can be tested without an HA instance.
"""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, timedelta
from typing import Any

from .const import (
    BILLING_CYCLE_MONTHS,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_EXPIRING_SOON,
    STATUS_PAUSED,
)


def parse_date(raw: Any) -> date | None:
    if not raw:
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def monthly_cost(cost: float, cycle: str | None) -> float:
    return round(float(cost) / BILLING_CYCLE_MONTHS.get(cycle, 1), 2)


def add_months(d: date, months: int) -> date:
    """Add months keeping the day; if it does not exist use the last day of the month."""
    year_offset, month_index = divmod(d.month - 1 + months, 12)
    year = d.year + year_offset
    month = month_index + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def next_renewal(anchor: date | None, cycle: str | None, today: date) -> date | None:
    """Next renewal >= today, advancing from the anchor date by whole cycles.

    It always starts from the anchor (not from the previous renewal), so a
    subscription renewing on January 31 goes back to March 31 after February 28.
    """
    if anchor is None:
        return None
    if anchor >= today:
        return anchor
    step = BILLING_CYCLE_MONTHS.get(cycle, 1)
    diff = (today.year - anchor.year) * 12 + (today.month - anchor.month)
    k = max(0, diff // step - 1)
    while add_months(anchor, k * step) < today:
        k += 1
    return add_months(anchor, k * step)


def subscription_status(paused: bool, days: int | None, threshold: int) -> str:
    if paused:
        return STATUS_PAUSED
    if days is None:
        return STATUS_ACTIVE
    if days < 0:
        return STATUS_EXPIRED
    if days <= threshold:
        return STATUS_EXPIRING_SOON
    return STATUS_ACTIVE


def build_summary(
    subs: list[dict[str, Any]],
    today: date,
    budget: float | None,
    upcoming_days: int,
) -> dict[str, Any]:
    """Summary of all subscriptions.

    Each item of `subs`: name, service, category, cost, currency, cycle,
    anchor (date|None), paused (bool), threshold (int).
    Returns {"monthly": float, "attributes": dict}.
    """
    active = [s for s in subs if not s["paused"]]
    paused_count = len(subs) - len(active)

    # No exchange-rate conversion: only the prevailing currency is summed.
    counts = Counter(s["currency"] for s in active)
    currency = counts.most_common(1)[0][0] if counts else "EUR"
    counted = [s for s in active if s["currency"] == currency]
    other_currency_count = len(active) - len(counted)

    monthly = 0.0
    by_category: dict[str, float] = {}
    expiring: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []

    for s in counted:
        m = monthly_cost(s["cost"], s["cycle"])
        monthly += m
        by_category[s["category"]] = round(by_category.get(s["category"], 0.0) + m, 2)

        renewal = next_renewal(s["anchor"], s["cycle"], today)
        if renewal is None:
            continue
        days = (renewal - today).days
        item = {
            "name": s["name"],
            "display_name": s.get("display_name", s["name"]),
            "service": s["service"],
            "days": days,
            "cost": s["cost"],
            "renewal": renewal.isoformat(),
        }
        if days <= s["threshold"]:
            expiring.append(item)
        if days <= upcoming_days:
            upcoming.append(item)

    expiring.sort(key=lambda e: (e["days"], e["name"]))
    upcoming.sort(key=lambda e: (e["days"], e["name"]))
    monthly = round(monthly, 2)

    if budget and budget > 0:
        budget_used_pct = round(monthly / budget * 100, 1)
        budget_remaining = round(budget - monthly, 2)
        budget_exceeded = monthly > budget
    else:
        budget = None
        budget_used_pct = None
        budget_remaining = None
        budget_exceeded = False

    return {
        "monthly": monthly,
        "attributes": {
            "currency": currency,
            "yearly_cost": round(monthly * 12, 2),
            "active_count": len(active),
            "paused_count": paused_count,
            "mixed_currency": other_currency_count > 0,
            "other_currency_count": other_currency_count,
            "by_category": by_category,
            "expiring_count": len(expiring),
            "expiring": expiring,
            "expiring_soon_total": round(sum(e["cost"] for e in expiring), 2),
            "upcoming_days": upcoming_days,
            "upcoming": upcoming,
            "upcoming_total": round(sum(e["cost"] for e in upcoming), 2),
            "budget": budget,
            "budget_used_pct": budget_used_pct,
            "budget_remaining": budget_remaining,
            "budget_exceeded": budget_exceeded,
        },
    }


def month_key(d: date) -> str:
    """`YYYY-MM` of a date."""
    return f"{d.year:04d}-{d.month:02d}"


def previous_month_key(d: date) -> str:
    """`YYYY-MM` of the calendar month before the one containing `d`."""
    return month_key(d.replace(day=1) - timedelta(days=1))


def update_monthly_history(
    history: list[dict[str, Any]],
    today: date,
    total: float,
    currency: str,
    keep: int,
) -> list[dict[str, Any]]:
    """Record the latest total for the current month; earlier months stay frozen.

    Returns a new list sorted by month, trimmed to the last `keep` months.
    """
    key = month_key(today)
    months = [h for h in history if h.get("month") != key]
    months.append({"month": key, "total": round(total, 2), "currency": currency})
    months.sort(key=lambda h: h["month"])
    return months[-keep:]


def history_comparison(
    history: list[dict[str, Any]], today: date, total: float, currency: str
) -> dict[str, Any]:
    """Compare the current total with the previous calendar month.

    All values are None when the previous month was not recorded (for example just
    after installation) or was recorded in another currency.
    """
    previous = next(
        (h for h in history if h.get("month") == previous_month_key(today)), None
    )
    if previous is None or previous.get("currency") != currency:
        return {"previous_month_cost": None, "change_vs_previous": None, "change_vs_previous_pct": None}
    prev_total = float(previous["total"])
    change = round(total - prev_total, 2)
    return {
        "previous_month_cost": round(prev_total, 2),
        "change_vs_previous": change,
        "change_vs_previous_pct": round(change / prev_total * 100, 1) if prev_total else None,
    }
