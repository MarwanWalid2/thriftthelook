"""Tests for the zero-key, synthetic demo catalogue."""

from decimal import Decimal

from api.demo import demo_outfit


def test_demo_budget_resolve_returns_complete_look_within_budget() -> None:
    payload = demo_outfit(Decimal("75"))

    assert payload["mode"] == "offline"
    assert payload["result"]["state"] == "complete"
    assert Decimal(payload["result"]["total"]) <= Decimal("75")
    assert all(item["image_url"] for item in payload["result"]["selections"])


def test_demo_preserves_closer_match_when_budget_is_higher() -> None:
    low_budget = demo_outfit(Decimal("75"))
    high_budget = demo_outfit(Decimal("150"))

    low_ids = {item["id"] for item in low_budget["result"]["selections"]}
    high_ids = {item["id"] for item in high_budget["result"]["selections"]}
    assert "demo-jacket-1" not in low_ids
    assert "demo-jacket-1" in high_ids


def test_demo_research_excludes_a_rejected_listing() -> None:
    payload = demo_outfit(Decimal("150"), frozenset({"demo-jacket-1"}))

    ids = {item["id"] for item in payload["result"]["selections"]}
    assert "demo-jacket-1" not in ids
