"""Small, privacy-conscious location-to-ZIP helper for delivery estimates."""

import asyncio
import logging
import re
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
_ZIP_PATTERN = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
_last_request_at = 0.0
_request_lock = asyncio.Lock()


class LocationLookupError(RuntimeError):
    """A ZIP code could not be safely resolved from approved coordinates."""


async def us_zip_from_coordinates(latitude: float, longitude: float) -> str:
    """Resolve a consented browser location to a US ZIP without retaining it."""

    await _respect_public_geocoder_rate_limit()
    params = {
        "format": "jsonv2",
        "lat": str(latitude),
        "lon": str(longitude),
        "zoom": "18",
        "addressdetails": "1",
    }
    headers = {"User-Agent": "ThriftTheLook-hackathon/0.1 (delivery ZIP lookup)"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0)) as client:
            response = await client.get(
                NOMINATIM_REVERSE_URL, params=params, headers=headers
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        logger.info("Location ZIP lookup was unavailable: %s", error)
        raise LocationLookupError(
            "Location lookup is temporarily unavailable."
        ) from error
    return _zip_from_nominatim_payload(payload)


async def _respect_public_geocoder_rate_limit() -> None:
    """Keep the demo below the public reverse-geocoder request rate."""

    global _last_request_at
    async with _request_lock:
        delay = 1.1 - (time.monotonic() - _last_request_at)
        if delay > 0:
            await asyncio.sleep(delay)
        _last_request_at = time.monotonic()


def _zip_from_nominatim_payload(payload: Any) -> str:
    """Extract a five-digit ZIP only when the location is in the United States."""

    if not isinstance(payload, dict):
        raise LocationLookupError("Location lookup returned an unexpected response.")
    address = payload.get("address")
    if not isinstance(address, dict) or address.get("country_code") != "us":
        raise LocationLookupError("A US delivery ZIP could not be determined.")
    postcode = address.get("postcode")
    if not isinstance(postcode, str):
        raise LocationLookupError("A US delivery ZIP could not be determined.")
    match = _ZIP_PATTERN.search(postcode)
    if match is None:
        raise LocationLookupError("A US delivery ZIP could not be determined.")
    return match.group(1)
