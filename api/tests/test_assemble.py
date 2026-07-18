"""Tests proving deterministic, shipping-aware budget assembly."""

from decimal import Decimal

from api.pipeline.assemble import Candidate, assemble


def candidate(
    slot: str, listing_id: str, price: str, shipping: str, score: int
) -> Candidate:
    return Candidate(
        slot, listing_id, listing_id, Decimal(price), Decimal(shipping), score
    )


def test_solver_replaces_an_expensive_low_value_slot_to_fit_budget() -> None:
    result = assemble(
        ("jacket", "top", "shoes"),
        (
            candidate("jacket", "premium-jacket", "70", "5", 84),
            candidate("jacket", "vintage-jacket", "18", "2", 76),
            candidate("top", "tee", "20", "0", 91),
            candidate("shoes", "boots", "35", "0", 96),
        ),
        Decimal("77"),
    )

    assert result.state == "complete"
    assert result.primary.total == Decimal("75")
    assert [item.listing_id for item in result.primary.selections] == [
        "vintage-jacket",
        "tee",
        "boots",
    ]


def test_solver_excludes_unknown_shipping_and_reports_partial_state() -> None:
    result = assemble(
        ("top", "bottom"),
        (
            candidate("top", "top", "14", "4", 95),
            Candidate("bottom", "unknown-ship", "bottom", Decimal("20"), None, 99),
        ),
        Decimal("30"),
    )

    assert result.state == "partial"
    assert result.missing_slots == ("bottom",)


def test_solver_never_exceeds_budget() -> None:
    result = assemble(
        ("top",),
        (candidate("top", "too-expensive", "20", "5", 100),),
        Decimal("10"),
    )

    assert result.state == "over_budget"
    assert result.primary.total == Decimal("0")
