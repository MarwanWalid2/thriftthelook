"""Deterministic budget-constrained outfit assembly."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from itertools import product


def _cents(value: Decimal) -> int:
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True, slots=True)
class Candidate:
    """A reranked listing ready for a deterministic budget decision."""

    slot: str
    listing_id: str
    title: str
    price: Decimal
    shipping: Decimal | None
    match_score: int
    reason: str = ""
    image_url: str | None = None
    item_url: str | None = None

    @property
    def total(self) -> Decimal | None:
        """Return delivered total only when shipping is known."""

        if self.shipping is None:
            return None
        return self.price + self.shipping


@dataclass(frozen=True, slots=True)
class Look:
    """One auditable selection of candidates."""

    selections: tuple[Candidate, ...]
    total: Decimal
    match_score: int

    @property
    def slots_found(self) -> int:
        return len(self.selections)


@dataclass(frozen=True, slots=True)
class AssemblyResult:
    """Primary fit, alternatives, and an explicit outcome state."""

    primary: Look
    alternatives: tuple[Look, ...]
    state: str
    budget: Decimal
    missing_slots: tuple[str, ...]


def _look_key(look: Look) -> tuple[int, int, int, tuple[str, ...]]:
    """Prefer filled slots, visual match, then the less costly deterministic result."""

    return (
        look.slots_found,
        look.match_score,
        -_cents(look.total),
        tuple(candidate.listing_id for candidate in look.selections),
    )


def _make_look(selections: Iterable[Candidate]) -> Look:
    chosen = tuple(selections)
    total = sum((candidate.total or Decimal("0") for candidate in chosen), Decimal("0"))
    score = sum(candidate.match_score for candidate in chosen)
    return Look(selections=chosen, total=total, match_score=score)


def _enumerate_looks(
    slots: tuple[str, ...], candidates: Iterable[Candidate]
) -> tuple[Look, ...]:
    by_slot: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.slot in slots and candidate.total is not None:
            by_slot[candidate.slot].append(candidate)

    options = [tuple(by_slot[slot]) + (None,) for slot in slots]
    return tuple(
        _make_look(candidate for candidate in choice if candidate is not None)
        for choice in product(*options)
    )


def assemble(
    slots: Iterable[str],
    candidates: Iterable[Candidate],
    budget: Decimal,
    limit: int = 3,
) -> AssemblyResult:
    """Choose the highest-quality delivered-price look without using an LLM.

    Unknown-shipping listings are excluded because their delivered price is unknown.
    When a complete look does not fit, this deliberately returns the best partial look.
    """

    requested_slots = tuple(dict.fromkeys(slots))
    available = tuple(candidates)
    all_looks = _enumerate_looks(requested_slots, available)
    fitting = tuple(
        look for look in all_looks if look.selections and look.total <= budget
    )
    if fitting:
        ranked = sorted(fitting, key=_look_key, reverse=True)
        primary = ranked[0]
        alternatives = tuple(look for look in ranked[1:] if look != primary)[:limit]
        missing = tuple(
            slot
            for slot in requested_slots
            if slot not in {item.slot for item in primary.selections}
        )
        state = "complete" if not missing else "partial"
        return AssemblyResult(primary, alternatives, state, budget, missing)

    empty = Look((), Decimal("0"), 0)
    known_delivered = any(item.total is not None for item in available)
    state = "over_budget" if known_delivered else "partial"
    return AssemblyResult(empty, (), state, budget, requested_slots)
