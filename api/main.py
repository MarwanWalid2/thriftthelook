"""FastAPI entry point for ThriftTheLook."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from api.config import get_settings
from api.demo import demo_outfit
from api.location import LocationLookupError, delivery_location_from_coordinates
from api.marketplaces import PHOTO_MARKETPLACES, marketplace_for_id
from api.pipeline.run import live_progress
from api.security import ALLOWED_IMAGE_TYPES, SlidingWindowLimiter, client_ip

logger = logging.getLogger(__name__)
live_request_limiter = SlidingWindowLimiter()

app = FastAPI(title="ThriftTheLook API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Return a non-sensitive readiness indication for the selected runtime mode."""

    return {"status": "ok", "mode": get_settings().demo_mode}


@app.get("/api/location")
async def delivery_location(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
) -> dict[str, str]:
    """Turn a browser-approved location into an editable delivery context."""

    try:
        location = await delivery_location_from_coordinates(latitude, longitude)
        return {
            "marketplace": location.marketplace,
            "country": location.country,
            "countryName": location.country_name,
            "postalCode": location.postal_code,
            "currency": location.currency,
        }
    except LocationLookupError as error:
        raise HTTPException(
            status_code=422,
            detail=(
                "We could not match your location to a supported "
                "photo-search market."
            ),
        ) from error


@app.get("/api/marketplaces")
async def supported_marketplaces() -> list[dict[str, str]]:
    """Expose the small, photo-search-ready market list without credentials."""

    return [
        {
            "marketplace": market.id,
            "country": market.country_code,
            "countryName": market.name,
            "currency": market.currency,
        }
        for market in PHOTO_MARKETPLACES
    ]


def parse_excluded_ids(value: str) -> frozenset[str]:
    """Parse the compact form/query representation used by the web client."""

    return frozenset(item for item in value.split(",") if item)


def format_style_profile(size: str, avoid_colors: str, condition_floor: str) -> str:
    """Keep user preferences explicit and safe to pass to the rerank prompt."""

    clean_size = " ".join(size.split())[:40] or "unspecified"
    clean_colors = " ".join(avoid_colors.split())[:120] or "none"
    clean_condition = " ".join(condition_floor.split())[:40] or "any"
    return (
        f"Size: {clean_size}; colors to avoid: {clean_colors}; "
        f"minimum condition: {clean_condition}."
    )


async def offline_progress(
    budget: Decimal,
    excluded_listing_ids: frozenset[str] = frozenset(),
    delivery_zip: str = "94103",
) -> AsyncIterator[str]:
    """Replay clearly labelled progress events for the zero-key demonstration path."""

    events = (
        ("intake", "Demo catalog ready — no live marketplace request."),
        ("decompose", "Reading the outfit into three garment slots."),
        (
            "re-search" if excluded_listing_ids else "search",
            "Finding a new synthetic option after your rejection."
            if excluded_listing_ids
            else "Matching the synthetic demo catalog.",
        ),
        ("assemble", "Solving a delivered-price budget."),
    )
    for stage, message in events:
        payload = json.dumps({"stage": stage, "message": message})
        yield f"event: progress\ndata: {payload}\n\n"
        await asyncio.sleep(0.15)
    complete_payload = json.dumps(
        demo_outfit(budget, excluded_listing_ids, delivery_zip)
    )
    yield f"event: complete\ndata: {complete_payload}\n\n"


@app.get("/api/outfit")
async def outfit_events(
    budget: Decimal = Query(default=Decimal("75"), ge=20, le=500),
    exclude_ids: str = Query(default=""),
    delivery_zip: str = Query(default="94103"),
) -> StreamingResponse:
    """Replay the offline SSE demo path for an immediately judgeable result."""

    settings = get_settings()
    if settings.demo_mode != "offline":
        logger.info("GET outfit endpoint is reserved for the offline replay path")
    return StreamingResponse(
        offline_progress(
            budget, parse_excluded_ids(exclude_ids), delivery_zip
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/api/outfit")
async def create_outfit(
    request: Request,
    photo: Annotated[UploadFile, File()],
    budget: Annotated[Decimal, Form(ge=20, le=500)] = Decimal("75"),
    exclude_ids: Annotated[str, Form()] = "",
    size: Annotated[str, Form()] = "unspecified",
    avoid_colors: Annotated[str, Form()] = "",
    condition_floor: Annotated[str, Form()] = "any",
    delivery_zip: Annotated[str, Form()] = "",
    delivery_marketplace: Annotated[str, Form()] = "EBAY_US",
) -> StreamingResponse:
    """Accept an outfit photo and stream either the judge-safe or live pipeline."""

    settings = get_settings()
    mime_type = photo.content_type or ""
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPG, PNG, or WebP outfit image.",
        )
    image_bytes = await photo.read(settings.max_upload_bytes + 1)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Upload a non-empty outfit image.")
    if len(image_bytes) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Image must be 8 MB or smaller.")
    if settings.demo_mode == "live" and not live_request_limiter.allow(
        client_ip(request),
        settings.live_requests_per_minute,
    ):
        raise HTTPException(
            status_code=429,
            detail="Too many live look requests. Please try again in a minute.",
        )
    excluded_listing_ids = parse_excluded_ids(exclude_ids)
    selected_zip = " ".join(delivery_zip.split())
    selected_marketplace = marketplace_for_id(delivery_marketplace)
    if selected_marketplace is None:
        raise HTTPException(
            status_code=422,
            detail="Choose a supported eBay photo-search country.",
        )
    if not selected_zip and settings.demo_mode == "offline":
        selected_zip = "94103"
    if not _valid_postal_code(selected_zip):
        raise HTTPException(
            status_code=422,
            detail="Add a valid delivery postcode for the selected country.",
        )
    if settings.demo_mode == "offline":
        return StreamingResponse(
            offline_progress(
                budget, excluded_listing_ids, selected_zip
            ),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )
    request_settings = settings.model_copy(
        update={
            "ebay_marketplace": selected_marketplace.id,
            "ebay_delivery_country": selected_marketplace.country_code,
            "ebay_delivery_zip": selected_zip,
        }
    )
    return StreamingResponse(
        live_progress(
            image_bytes,
            mime_type,
            budget,
            request_settings,
            excluded_listing_ids,
            format_style_profile(size, avoid_colors, condition_floor),
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


def _valid_postal_code(value: str) -> bool:
    """Keep the marketplace header bounded and free of control characters."""

    return 2 <= len(value) <= 16 and all(
        character.isalnum() or character in {" ", "-"} for character in value
    )
