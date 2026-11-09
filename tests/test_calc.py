from datetime import date

from custom_components.subscription_tracker.calc import (
    add_months, build_summary, monthly_cost, next_renewal, subscription_status,
)

T = date(2026, 11, 9)


def sub(name="A", cost=10.0, cur="EUR", cycle="monthly", anchor=date(2026, 11, 20),
        paused=False, cat="video", thr=7):
    return dict(name=name, service=name.lower(), category=cat, cost=cost, currency=cur,
                cycle=cycle, anchor=anchor, paused=paused, threshold=thr)


def test_add_months_clamps():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)


def test_next_renewal_future_and_today_unchanged():
    assert next_renewal(date(2026, 12, 1), "monthly", T) == date(2026, 12, 1)
    assert next_renewal(T, "monthly", T) == T


def test_next_renewal_monthly_advances_from_anchor():
    assert next_renewal(date(2026, 1, 31), "monthly", date(2026, 3, 1)) == date(2026, 3, 31)
    assert next_renewal(date(2026, 1, 31), "monthly", date(2026, 2, 1)) == date(2026, 2, 28)
    assert next_renewal(date(2026, 10, 9), "monthly", T) == T
    assert next_renewal(date(2026, 10, 8), "monthly", T) == date(2026, 12, 8)


def test_next_renewal_quarterly_yearly():
    assert next_renewal(date(2026, 1, 15), "quarterly", T) == date(2027, 1, 15)
    assert next_renewal(date(2020, 3, 1), "yearly", T) == date(2027, 3, 1)
    assert next_renewal(date(2025, 11, 9), "yearly", T) == T
    assert next_renewal(None, "monthly", T) is None


def test_status():
    assert subscription_status(True, 3, 7) == "paused"
    assert subscription_status(False, None, 7) == "active"
    assert subscription_status(False, 7, 7) == "expiring_soon"
    assert subscription_status(False, 8, 7) == "active"
    assert subscription_status(False, -1, 7) == "expired"


def test_summary_totals_budget_timeline():
    subs = [
        sub("Netflix", 19.99, anchor=date(2026, 11, 9)),            # today
        sub("Disney", 120.0, cycle="yearly", anchor=date(2027, 2, 1), cat="video"),
        sub("Spotify", 17.99, anchor=date(2026, 10, 25), cat="audio"),  # advances to 25/11
        sub("Paused", 50.0, paused=True),
    ]
    r = build_summary(subs, T, 100.0, 30)
    a = r["attributes"]
    assert r["monthly"] == round(19.99 + 10.0 + 17.99, 2)
    assert a["active_count"] == 3 and a["paused_count"] == 1
    assert a["by_category"] == {"video": 29.99, "audio": 17.99}
    assert [u["name"] for u in a["upcoming"]] == ["Netflix", "Spotify"]
    assert a["upcoming"][1]["renewal"] == "2026-11-25"
    assert a["upcoming_total"] == round(19.99 + 17.99, 2)
    assert a["expiring_count"] == 1 and a["expiring"][0]["name"] == "Netflix"
    assert a["budget"] == 100.0 and a["budget_used_pct"] == 48.0
    assert a["budget_remaining"] == 52.02 and not a["budget_exceeded"]


def test_summary_budget_exceeded_and_none():
    subs = [sub(cost=60.0), sub("B", 50.0)]
    a = build_summary(subs, T, 100.0, 30)["attributes"]
    assert a["budget_exceeded"] and a["budget_remaining"] == -10.0 and a["budget_used_pct"] == 110.0
    for b in (None, 0, 0.0):
        a = build_summary(subs, T, b, 30)["attributes"]
        assert a["budget"] is None and a["budget_used_pct"] is None and not a["budget_exceeded"]


def test_summary_mixed_currency_counts_prevalent_only():
    subs = [sub("A", 10.0), sub("B", 5.0), sub("C", 100.0, cur="USD")]
    r = build_summary(subs, T, None, 30)
    assert r["attributes"]["currency"] == "EUR"
    assert r["monthly"] == 15.0
    assert r["attributes"]["mixed_currency"] and r["attributes"]["other_currency_count"] == 1


def test_summary_empty():
    r = build_summary([], T, None, 30)
    assert r["monthly"] == 0.0 and r["attributes"]["currency"] == "EUR"
    assert r["attributes"]["upcoming"] == []


def test_monthly_cost():
    assert monthly_cost(120, "yearly") == 10.0 and monthly_cost(30, "quarterly") == 10.0
