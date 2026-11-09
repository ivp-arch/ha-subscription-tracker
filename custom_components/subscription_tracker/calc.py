"""Calcoli puri di Subscription Tracker.

Nessuna dipendenza da Home Assistant: input e output sono tipi base, cosi'
la logica (rinnovi, totali, budget, timeline) si prova senza istanza HA.
"""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date
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
    """Somma mesi mantenendo il giorno; se non esiste usa l'ultimo del mese."""
    year_offset, month_index = divmod(d.month - 1 + months, 12)
    year = d.year + year_offset
    month = month_index + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def next_renewal(anchor: date | None, cycle: str | None, today: date) -> date | None:
    """Prossimo rinnovo >= oggi, avanzando dalla data ancora per cicli interi.

    Si parte sempre dall'ancora (non dal rinnovo precedente), cosi' un
    abbonamento del 31 gennaio torna al 31 marzo dopo il 28 febbraio.
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
    """Riepilogo di tutti gli abbonamenti.

    Ogni elemento di `subs`: name, service, category, cost, currency, cycle,
    anchor (date|None), paused (bool), threshold (int).
    Restituisce {"monthly": float, "attributes": dict}.
    """
    active = [s for s in subs if not s["paused"]]
    paused_count = len(subs) - len(active)

    # Nessuna conversione di cambio: si somma solo la valuta prevalente.
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
