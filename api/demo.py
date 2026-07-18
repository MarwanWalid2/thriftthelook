"""Synthetic, license-safe data for the zero-key judge demo."""

from decimal import Decimal
from typing import Any

from api.pipeline.assemble import AssemblyResult, Candidate, assemble

DEMO_NOTICE = "Synthetic demo inventory — not live eBay listings."
DEMO_SLOTS = ("jacket", "top", "shoes")
DEMO_CANDIDATES = (
    Candidate(
        "jacket",
        "demo-jacket-1",
        "Vintage denim chore jacket",
        Decimal("42"),
        Decimal("8"),
        96,
        "Best washed-denim match for the reference layer.",
        "/demo/jacket.svg",
    ),
    Candidate(
        "jacket",
        "demo-jacket-2",
        "Faded indigo work jacket",
        Decimal("19"),
        Decimal("5"),
        83,
        "Keeps the indigo workwear mood for less.",
        "/demo/jacket.svg",
    ),
    Candidate(
        "jacket",
        "demo-jacket-3",
        "Soft cotton utility overshirt",
        Decimal("14"),
        Decimal("4"),
        74,
        "A lighter utility alternative.",
        "/demo/jacket.svg",
    ),
    Candidate(
        "top",
        "demo-top-1",
        "Cream ribbed tee",
        Decimal("18"),
        Decimal("3"),
        94,
        "Closest cream base layer.",
        "/demo/top.svg",
    ),
    Candidate(
        "top",
        "demo-top-2",
        "Ivory heavyweight pocket tee",
        Decimal("11"),
        Decimal("3"),
        83,
        "Same warm neutral palette at a lower total.",
        "/demo/top.svg",
    ),
    Candidate(
        "top",
        "demo-top-3",
        "Oatmeal cotton long-sleeve",
        Decimal("8"),
        Decimal("2"),
        76,
        "Budget-friendly long-sleeve option.",
        "/demo/top.svg",
    ),
    Candidate(
        "shoes",
        "demo-shoes-1",
        "Brown leather ankle boots",
        Decimal("49"),
        Decimal("9"),
        97,
        "Best leather-boot silhouette match.",
        "/demo/shoes.svg",
    ),
    Candidate(
        "shoes",
        "demo-shoes-2",
        "Cognac lace-up boots",
        Decimal("28"),
        Decimal("6"),
        86,
        "Preserves the warm leather shape for less.",
        "/demo/shoes.svg",
    ),
    Candidate(
        "shoes",
        "demo-shoes-3",
        "Chestnut leather work shoes",
        Decimal("19"),
        Decimal("5"),
        78,
        "Lowest-cost leather footwear alternative.",
        "/demo/shoes.svg",
    ),
)


def demo_outfit(
    budget: Decimal,
    excluded_listing_ids: frozenset[str] = frozenset(),
    delivery_zip: str = "94103",
) -> dict[str, Any]:
    """Solve the synthetic demo catalogue for the requested delivered-price budget."""

    candidates = tuple(
        candidate
        for candidate in DEMO_CANDIDATES
        if candidate.listing_id not in excluded_listing_ids
    )
    result = assemble(DEMO_SLOTS, candidates, budget)
    return {
        "mode": "offline",
        "notice": DEMO_NOTICE,
        "zip": delivery_zip,
        "budget": str(budget),
        "result": serialize_result(result),
    }


def serialize_result(result: AssemblyResult) -> dict[str, Any]:
    return {
        "state": result.state,
        "total": str(result.primary.total),
        "match_score": result.primary.match_score,
        "missing_slots": list(result.missing_slots),
        "selections": [
            _serialize_candidate(item) for item in result.primary.selections
        ],
        "alternatives": [
            {
                "total": str(look.total),
                "selections": [_serialize_candidate(item) for item in look.selections],
            }
            for look in result.alternatives
        ],
    }


def _serialize_candidate(candidate: Candidate) -> dict[str, Any]:
    total = candidate.total
    return {
        "slot": candidate.slot,
        "id": candidate.listing_id,
        "title": candidate.title,
        "price": str(candidate.price),
        "shipping": str(candidate.shipping) if candidate.shipping is not None else None,
        "total": str(total) if total is not None else None,
        "match_score": candidate.match_score,
        "reason": candidate.reason,
        "image_url": candidate.image_url,
        "item_url": candidate.item_url,
    }
