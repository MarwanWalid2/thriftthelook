"""FastAPI entry point for ThriftTheLook."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from api.config import get_settings
from api.demo import demo_outfit
from api.location import LocationLookupError, us_zip_from_coordinates
from api.pipeline.run import live_progress

logger = logging.getLogger(__name__)

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


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Return a non-sensitive readiness indication for the selected runtime mode."""

    return {"status": "ok", "mode": get_settings().demo_mode}


@app.get("/api/location/zip")
async def location_zip(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
) -> dict[str, str]:
    """Turn a browser-approved location into an editable US delivery ZIP."""

    try:
        return {"zip": await us_zip_from_coordinates(latitude, longitude)}
    except LocationLookupError as error:
        raise HTTPException(
            status_code=422,
            detail="We could not determine a US delivery ZIP from that location.",
        ) from error


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
    )


@app.post("/api/outfit")
async def create_outfit(
    photo: Annotated[UploadFile, File()],
    budget: Annotated[Decimal, Form(ge=20, le=500)] = Decimal("75"),
    exclude_ids: Annotated[str, Form()] = "",
    size: Annotated[str, Form()] = "unspecified",
    avoid_colors: Annotated[str, Form()] = "",
    condition_floor: Annotated[str, Form()] = "any",
    delivery_zip: Annotated[str, Form()] = "",
) -> StreamingResponse:
    """Accept an outfit photo and stream either the judge-safe or live pipeline."""

    image_bytes = await photo.read()
    mime_type = photo.content_type or "image/jpeg"
    settings = get_settings()
    excluded_listing_ids = parse_excluded_ids(exclude_ids)
    selected_zip = " ".join(delivery_zip.split())
    if settings.demo_mode == "offline":
        return StreamingResponse(
            offline_progress(
                budget, excluded_listing_ids, selected_zip or "94103"
            ),
            media_type="text/event-stream",
        )
    request_settings = settings.model_copy(
        update={"ebay_delivery_zip": selected_zip or settings.ebay_delivery_zip}
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
    )
