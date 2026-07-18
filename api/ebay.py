"""Small, rate-conscious client for the official eBay Browse API."""

import asyncio
import base64
import hashlib
import logging
import random
import time
from collections.abc import Awaitable, Callable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from api.config import Settings, get_settings
from api.models import Listing

logger = logging.getLogger(__name__)

IDENTITY_URL = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary"
OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class EbayClientError(RuntimeError):
    """An eBay API request could not be completed safely."""


Sleep = Callable[[float], Awaitable[None]]


class EbayClient:
    """OAuth-authenticated Browse API client with short-lived in-process caches."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
        cache_enabled: bool = True,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self._http = http_client or httpx.AsyncClient(timeout=httpx.Timeout(20.0))
        self._owns_http_client = http_client is None
        self._max_retries = max_retries
        self._cache_enabled = cache_enabled
        self._sleep = sleep
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()
        self._query_cache: dict[str, tuple[Listing, ...]] = {}

    async def aclose(self) -> None:
        """Close the internally-created HTTP client."""

        if self._owns_http_client:
            await self._http.aclose()

    async def __aenter__(self) -> "EbayClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def search_by_image(
        self,
        crop: bytes,
        *,
        limit: int = 24,
        fallback_keywords: str | None = None,
    ) -> list[Listing]:
        """Search the selected eBay market with a crop, falling back to keywords."""

        if not crop:
            raise ValueError("A non-empty image crop is required.")
        encoded_crop = base64.b64encode(crop).decode("ascii")
        cache_key = f"image:{hashlib.sha256(crop).hexdigest()}:{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            payload = await self._request(
                "POST",
                f"{BROWSE_URL}/search_by_image",
                json={"image": encoded_crop},
                params={"limit": limit},
            )
            listings = self._normalize_search(payload)
        except EbayClientError:
            if fallback_keywords is None:
                raise
            logger.info("Image search unavailable; using keyword fallback")
            return await self.search_by_keywords(fallback_keywords, limit=limit)

        if not listings and fallback_keywords:
            return await self.search_by_keywords(fallback_keywords, limit=limit)
        if fallback_keywords and not any(item.total is not None for item in listings):
            logger.info(
                "Image search returned no delivery-priced listings; "
                "using keyword fallback"
            )
            return await self.search_by_keywords(fallback_keywords, limit=limit)
        self._cache(cache_key, listings)
        return listings

    async def search_by_keywords(
        self, keywords: str, *, limit: int = 24
    ) -> list[Listing]:
        """Search Browse ``/search`` using GPT-generated garment keywords."""

        normalized_keywords = " ".join(keywords.split())
        if not normalized_keywords:
            raise ValueError("Search keywords cannot be blank.")
        cache_key = f"keywords:{normalized_keywords.casefold()}:{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        payload = await self._request(
            "GET",
            f"{BROWSE_URL}/search",
            params={"q": normalized_keywords, "limit": limit},
        )
        listings = self._normalize_search(payload)
        self._cache(cache_key, listings)
        return listings

    async def _request(self, method: str, url: str, **kwargs: Any) -> Mapping[str, Any]:
        """Make a retrying Browse request without exposing credentials in logs."""

        token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self.settings.ebay_marketplace,
        }
        if self.settings.ebay_delivery_zip:
            headers["X-EBAY-C-ENDUSERCTX"] = (
                "contextualLocation="
                f"country={self.settings.ebay_delivery_country},"
                f"zip={self.settings.ebay_delivery_zip}"
            )
        response = await self._send_with_retries(method, url, headers=headers, **kwargs)
        try:
            payload = response.json()
        except ValueError as error:
            raise EbayClientError("eBay returned an invalid JSON response.") from error
        if not isinstance(payload, Mapping):
            raise EbayClientError("eBay returned an unexpected response shape.")
        return payload

    async def _get_access_token(self) -> str:
        if self._access_token and time.monotonic() < self._token_expires_at:
            return self._access_token
        if not self.settings.ebay_client_id or not self.settings.ebay_client_secret:
            raise EbayClientError("eBay credentials are required for live search.")

        async with self._token_lock:
            if self._access_token and time.monotonic() < self._token_expires_at:
                return self._access_token
            response = await self._send_with_retries(
                "POST",
                IDENTITY_URL,
                data={"grant_type": "client_credentials", "scope": OAUTH_SCOPE},
                auth=(self.settings.ebay_client_id, self.settings.ebay_client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            try:
                payload = response.json()
                token = payload["access_token"]
                expires_in = int(payload.get("expires_in", 7200))
            except (KeyError, TypeError, ValueError) as error:
                raise EbayClientError(
                    "eBay returned an invalid token response."
                ) from error
            if not isinstance(token, str) or not token:
                raise EbayClientError("eBay returned an invalid token response.")
            self._access_token = token
            self._token_expires_at = time.monotonic() + max(0, expires_in - 120)
            return token

    async def _send_with_retries(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._http.request(method, url, **kwargs)
            except httpx.RequestError as error:
                last_error = error
            else:
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    if response.is_error:
                        raise EbayClientError(
                            f"eBay request failed with status {response.status_code}."
                        )
                    return response
                last_error = EbayClientError(
                    f"eBay request failed with status {response.status_code}."
                )
            if attempt < self._max_retries:
                await self._sleep((2**attempt) * 0.25 + random.uniform(0, 0.1))
        raise EbayClientError("eBay request failed after retries.") from last_error

    def _get_cached(self, key: str) -> list[Listing] | None:
        if not self._cache_enabled or key not in self._query_cache:
            return None
        return list(self._query_cache[key])

    def _cache(self, key: str, listings: list[Listing]) -> None:
        if self._cache_enabled:
            self._query_cache[key] = tuple(listings)

    @staticmethod
    def _normalize_search(payload: Mapping[str, Any]) -> list[Listing]:
        raw_items = payload.get("itemSummaries", [])
        if not isinstance(raw_items, list):
            return []
        listings: list[Listing] = []
        for raw_item in raw_items:
            if isinstance(raw_item, Mapping):
                listing = normalize_listing(raw_item)
                if listing is not None:
                    listings.append(listing)
        return listings


def normalize_listing(payload: Mapping[str, Any]) -> Listing | None:
    """Convert an eBay item summary to a listing, discarding unusable prices."""

    item_id = payload.get("itemId")
    title = payload.get("title")
    price_data = payload.get("price")
    if (
        not isinstance(item_id, str)
        or not isinstance(title, str)
        or not isinstance(price_data, Mapping)
    ):
        return None
    price = _decimal_value(price_data.get("value"))
    if price is None:
        return None
    shipping, shipping_currency = _shipping_cost(payload.get("shippingOptions"))
    image_data = payload.get("image")
    image_url = image_data.get("imageUrl") if isinstance(image_data, Mapping) else None
    item_url = payload.get("itemWebUrl")
    currency = price_data.get("currency") or shipping_currency or "USD"
    return Listing(
        id=item_id,
        title=title,
        price=price,
        shipping=shipping,
        image_url=image_url if isinstance(image_url, str) else None,
        item_url=item_url if isinstance(item_url, str) else None,
        condition=payload.get("condition")
        if isinstance(payload.get("condition"), str)
        else None,
        currency=currency if isinstance(currency, str) else "USD",
    )


def _shipping_cost(value: object) -> tuple[Decimal | None, str | None]:
    if not isinstance(value, list):
        return None, None
    costs: list[tuple[Decimal, str | None]] = []
    for option in value:
        if not isinstance(option, Mapping):
            continue
        amount = option.get("shippingCost")
        if not isinstance(amount, Mapping):
            continue
        cost = _decimal_value(amount.get("value"))
        if cost is not None:
            currency = amount.get("currency")
            costs.append((cost, currency if isinstance(currency, str) else None))
    return min(costs, key=lambda item: item[0]) if costs else (None, None)


def _decimal_value(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
