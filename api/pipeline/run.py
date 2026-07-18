"""Live pipeline orchestration with honest SSE-stage events."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from openai import APIError

from api.config import Settings
from api.demo import serialize_result
from api.ebay import EbayClient, EbayClientError
from api.llm import (
    CandidateAssessment,
    GarmentSlot,
    LlmConfigurationError,
    RerankCandidate,
    decompose_outfit,
    narrate_look,
    rerank_slot,
)
from api.models import Listing
from api.pipeline.assemble import Candidate, assemble
from api.pipeline.crop import (
    CropDependencyError,
    GarmentCrop,
    detect_yolo_crops,
    gpt_box_crops,
)
from api.pipeline.rerank import accepted_top_three

logger = logging.getLogger(__name__)


def _event(name: str, payload: dict[str, object]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload)}\n\n"


async def live_progress(
    image_bytes: bytes,
    mime_type: str,
    budget: Decimal,
    settings: Settings,
    excluded_listing_ids: frozenset[str] = frozenset(),
    style_profile: str = (
        "Size: unspecified; colors to avoid: none; minimum condition: any."
    ),
) -> AsyncIterator[str]:
    """Stream the live pipeline without leaking provider details."""

    try:
        yield _event(
            "progress",
            {"stage": "decompose", "message": "Reading the outfit into slots."},
        )
        decomposition = await decompose_outfit(image_bytes, mime_type, settings)
        slots = decomposition.slots[:3]
        if not slots:
            yield _event(
                "failure",
                {"message": "No garment slots were found. Try a clearer outfit photo."},
            )
            return

        yield _event(
            "progress",
            {
                "stage": "crop",
                "message": f"Preparing crops for {len(slots)} visible slots.",
            },
        )
        crop_bytes = await _make_crops(
            image_bytes, mime_type, slots, settings.use_gpt_boxes
        )
        yield _event(
            "progress",
            {
                "stage": "search",
                "message": "Searching official eBay inventory in parallel.",
            },
        )
        async with EbayClient(settings) as ebay:
            searched = await asyncio.gather(
                *[
                    _search_slot(
                        f"{index}:{slot.garment_type}",
                        slot.garment_type,
                        slot.colors,
                        slot.search_keywords,
                        crop_bytes[index],
                        mime_type,
                        ebay,
                        excluded_listing_ids,
                        style_profile,
                    )
                    for index, slot in enumerate(slots)
                ]
            )

        candidates = [
            candidate
            for candidates_for_slot in searched
            for candidate in candidates_for_slot
        ]
        slot_ids = tuple(
            f"{index}:{slot.garment_type}" for index, slot in enumerate(slots)
        )
        yield _event(
            "progress",
            {"stage": "assemble", "message": "Solving the delivered-price budget."},
        )
        outcome = assemble(slot_ids, candidates, budget)
        result = serialize_result(outcome)
        selected_names = ", ".join(item.title for item in outcome.primary.selections)
        yield _event(
            "progress",
            {"stage": "narrate", "message": "Writing the stylist receipt."},
        )
        narration = await narrate_look(
            str(budget), str(outcome.primary.total), selected_names, settings
        )
        yield _event(
            "complete",
            {
                "mode": "live",
                "notice": "Live eBay inventory; pricing estimated at request time.",
                "zip": settings.ebay_delivery_zip,
                "budget": str(budget),
                "result": result,
                "narration": narration.model_dump(),
            },
        )
    except (
        CropDependencyError,
        EbayClientError,
        LlmConfigurationError,
        RuntimeError,
        ValueError,
        APIError,
    ) as error:
        logger.warning("Live pipeline did not complete: %s", error)
        yield _event(
            "failure",
            {
                "message": (
                    "We could not complete this live look. Check your keys, "
                    "delivery ZIP, and crop setup, then try again."
                )
            },
        )


async def _make_crops(
    image_bytes: bytes,
    mime_type: str,
    slots: list[GarmentSlot],
    use_gpt_boxes: bool,
) -> list[bytes]:
    """Prefer YOLO crops; use the source image when the optional extra is absent."""

    suffix = ".png" if mime_type == "image/png" else ".jpg"
    with TemporaryDirectory() as directory:
        root = Path(directory)
        image_path = root / f"upload{suffix}"
        image_path.write_bytes(image_bytes)
        try:
            if use_gpt_boxes:
                crops = await asyncio.to_thread(
                    gpt_box_crops, image_path, slots, root / "gpt-crops"
                )
            else:
                crops = await asyncio.to_thread(
                    detect_yolo_crops, image_path, root / "yolo-crops"
                )
        except CropDependencyError:
            return [image_bytes for _ in slots]
        return [
            _closest_crop(slot, index, crops, image_bytes)
            for index, slot in enumerate(slots)
        ]


def _closest_crop(
    slot: GarmentSlot,
    index: int,
    crops: list[GarmentCrop],
    fallback: bytes,
) -> bytes:
    """Select a deterministic YOLO crop, falling back to the source image."""

    matching = [
        crop
        for crop in crops
        if slot.garment_type.casefold() in crop.box.label.casefold()
    ]
    if matching:
        return matching[0].path.read_bytes()
    if not crops:
        return fallback
    return crops[min(index, len(crops) - 1)].path.read_bytes()


async def _search_slot(
    slot_id: str,
    garment_type: str,
    colors: list[str],
    keywords: list[str],
    crop: bytes,
    mime_type: str,
    ebay: EbayClient,
    excluded_listing_ids: frozenset[str],
    style_profile: str,
) -> list[Candidate]:
    """Search and rerank one slot using exactly one batched model call."""

    query = _slot_query(colors, keywords)
    image_listings = await ebay.search_by_image(crop, fallback_keywords=query)
    keyword_listings = await ebay.search_by_keywords(query)
    listings = [
        item
        for item in _unique_listings([*keyword_listings, *image_listings])
        if item.id not in excluded_listing_ids
    ]
    visual_candidates = [
        RerankCandidate(id=item.id, title=item.title, image_url=item.image_url)
        for item in listings[:24]
        if item.image_url is not None
    ]
    assessments: dict[str, CandidateAssessment] = {}
    if visual_candidates:
        reranked = await rerank_slot(
            crop,
            mime_type,
            garment_type,
            colors,
            visual_candidates,
            style_profile,
        )
        assessments = {item.id: item for item in accepted_top_three(reranked)}
    return _to_candidates(slot_id, listings, assessments)


def _slot_query(colors: list[str], keywords: list[str]) -> str:
    """Use the most precise generated phrase, avoiding eBay's noisy long queries."""

    phrase = " ".join(keywords[0].split()) if keywords else ""
    color = " ".join(colors[0].split()) if colors else ""
    if color and color.casefold() not in phrase.casefold():
        phrase = f"{color} {phrase}".strip()
    return phrase or "secondhand clothing"


def _unique_listings(listings: list[Listing]) -> list[Listing]:
    """Preserve keyword relevance while retaining unique visual-search candidates."""

    seen: set[str] = set()
    unique: list[Listing] = []
    for item in listings:
        if item.id not in seen:
            unique.append(item)
            seen.add(item.id)
    return unique


def _to_candidates(
    slot: str,
    listings: list[Listing],
    assessments: dict[str, CandidateAssessment],
) -> list[Candidate]:
    return [
        Candidate(
            slot,
            item.id,
            item.title,
            item.price,
            item.shipping,
            assessments[item.id].match_score,
            assessments[item.id].reason,
            item.image_url,
            item.item_url,
        )
        for item in listings
        if item.id in assessments and item.total is not None
    ]
