"""Consent-based location lookup for the supported eBay delivery markets."""

import asyncio
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from api.marketplaces import Marketplace, marketplace_for_country

logger = logging.getLogger(__name__)

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
_last_request_at = 0.0
_request_lock = asyncio.Lock()


class LocationLookupError(RuntimeError):
    """A delivery market could not be safely resolved from approved coordinates."""


class DetectedDeliveryLocation(BaseModel):
    """A location result that is safe to return to the browser."""

    model_config = ConfigDict(frozen=True)

    marketplace: str
    country: str
    country_name: str
    postal_code: str
    currency: str


async def delivery_location_from_coordinates(
    latitude: float, longitude: float
) -> DetectedDeliveryLocation:
    """Resolve a consented browser location without retaining coordinates."""

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
    return _delivery_location_from_nominatim_payload(payload)


async def _respect_public_geocoder_rate_limit() -> None:
    """Keep the demo below the public reverse-geocoder request rate."""

    global _last_request_at
    async with _request_lock:
        delay = 1.1 - (time.monotonic() - _last_request_at)
        if delay > 0:
            await asyncio.sleep(delay)
        _last_request_at = time.monotonic()


def _delivery_location_from_nominatim_payload(payload: Any) -> DetectedDeliveryLocation:
    """Extract a supported country and its postal code from Nominatim's payload."""

    if not isinstance(payload, dict):
        raise LocationLookupError("Location lookup returned an unexpected response.")
    address = payload.get("address")
    if not isinstance(address, dict):
        raise LocationLookupError("A delivery location could not be determined.")
    country = address.get("country_code")
    market = marketplace_for_country(country) if isinstance(country, str) else None
    if market is None:
        raise LocationLookupError("That country is not in photo search yet.")
    postcode = address.get("postcode")
    if not isinstance(postcode, str) or not postcode.strip():
        raise LocationLookupError("A delivery postcode could not be determined.")
    return _detected_location(market, postcode)


def _detected_location(market: Marketplace, postcode: str) -> DetectedDeliveryLocation:
    """Build the browser-safe public location response."""

    return DetectedDeliveryLocation(
        marketplace=market.id,
        country=market.country_code,
        country_name=market.name,
        postal_code=postcode.strip(),
        currency=market.currency,
    )
