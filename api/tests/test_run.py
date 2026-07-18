"""Live orchestration tests with every provider boundary replaced by fakes."""

import json
from decimal import Decimal

import pytest

from api.config import Settings
from api.llm import GarmentSlot, OutfitDecomposition, StylistNarration
from api.pipeline import run
from api.pipeline.assemble import Candidate


@pytest.mark.asyncio
async def test_live_stream_emits_every_pipeline_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_decompose(*_: object) -> OutfitDecomposition:
        return OutfitDecomposition(
            slots=[
                GarmentSlot(
                    garment_type="jacket",
                    colors=["blue"],
                    style_desc="washed denim",
                    search_keywords=["denim jacket"],
                    price_band_guess="under $50",
                )
            ]
        )

    async def fake_crops(*_: object) -> list[bytes]:
        return [b"crop"]

    async def fake_search(*_: object) -> list[Candidate]:
        return [
            Candidate(
                "0:jacket",
                "listing-1",
                "Blue denim jacket",
                Decimal("20"),
                Decimal("5"),
                93,
                "Correct washed-denim silhouette.",
                "https://example.com/jacket.jpg",
            )
        ]

    async def fake_narrate(*_: object) -> StylistNarration:
        return StylistNarration(note="Great find.", tradeoffs=["Saved on the layer."])

    class FakeEbayClient:
        def __init__(self, *_: object) -> None:
            pass

        async def __aenter__(self) -> "FakeEbayClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(run, "decompose_outfit", fake_decompose)
    monkeypatch.setattr(run, "_make_crops", fake_crops)
    monkeypatch.setattr(run, "_search_slot", fake_search)
    monkeypatch.setattr(run, "narrate_look", fake_narrate)
    monkeypatch.setattr(run, "EbayClient", FakeEbayClient)

    events = [
        json.loads(event.removeprefix("event: progress\ndata: ").rstrip("\n"))
        async for event in run.live_progress(
            b"outfit", "image/jpeg", Decimal("75"), Settings(demo_mode="live")
        )
        if event.startswith("event: progress")
    ]

    assert [event["stage"] for event in events] == [
        "decompose",
        "crop",
        "search",
        "assemble",
        "narrate",
    ]
