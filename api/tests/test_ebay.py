"""Tests for eBay authentication and listing normalization."""

import json
from base64 import b64encode
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from api.config import Settings
from api.ebay import IDENTITY_URL, EbayClient

FIXTURE = Path(__file__).parent / "fixtures" / "ebay_search.json"


def settings(
    zip_code: str | None = None,
    marketplace: str = "EBAY_US",
    country: str = "US",
) -> Settings:
    return Settings(
        ebay_client_id="test-id",
        ebay_client_secret="test-secret",
        ebay_delivery_zip=zip_code,
        ebay_marketplace=marketplace,
        ebay_delivery_country=country,
    )


@pytest.mark.asyncio
async def test_token_is_cached_and_search_payload_is_normalized() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if str(request.url) == IDENTITY_URL:
            return httpx.Response(
                200, json={"access_token": "test-token", "expires_in": 7200}
            )
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_US"
        return httpx.Response(200, json=fixture)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = EbayClient(settings(), http_client=http, cache_enabled=False)
        first = await client.search_by_keywords("brown  leather jacket")
        second = await client.search_by_keywords("black boots")

    assert len([call for call in calls if str(call.url) == IDENTITY_URL]) == 1
    assert first[0].price == Decimal("42.50")
    assert first[0].shipping == Decimal("7.99")
    assert first[0].total == Decimal("50.49")
    assert first[0].item_url == "https://www.ebay.com/itm/123"
    assert first[1].shipping is None
    assert first[1].total is None
    assert len(second) == 2


@pytest.mark.asyncio
async def test_identical_image_query_uses_dev_cache() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if str(request.url) == IDENTITY_URL:
            return httpx.Response(
                200, json={"access_token": "token", "expires_in": 7200}
            )
        return httpx.Response(200, json={"itemSummaries": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = EbayClient(settings(), http_client=http, max_retries=0)
        await client.search_by_image(b"image-bytes")
        await client.search_by_image(b"image-bytes")

    assert calls == 2


@pytest.mark.asyncio
async def test_image_search_falls_back_to_keyword_search() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == IDENTITY_URL:
            return httpx.Response(
                200, json={"access_token": "token", "expires_in": 7200}
            )
        if request.url.path.endswith("/search_by_image"):
            return httpx.Response(503, json={})
        assert request.url.path.endswith("/search")
        assert request.url.params["q"] == "blue denim jacket"
        return httpx.Response(200, json={"itemSummaries": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = EbayClient(settings(), http_client=http, max_retries=0)
        listings = await client.search_by_image(
            b"image-bytes", fallback_keywords="blue denim jacket"
        )

    assert listings == []
    browse_calls = [
        request for request in requests if request.url.path.startswith("/buy/browse")
    ]
    assert [request.url.path for request in browse_calls] == [
        "/buy/browse/v1/item_summary/search_by_image",
        "/buy/browse/v1/item_summary/search",
    ]


@pytest.mark.asyncio
async def test_image_search_falls_back_when_shipping_is_not_supplied() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == IDENTITY_URL:
            return httpx.Response(
                200, json={"access_token": "token", "expires_in": 7200}
            )
        if request.url.path.endswith("/search_by_image"):
            return httpx.Response(
                200,
                json={
                    "itemSummaries": [
                        {
                            "itemId": "v1|no-shipping|0",
                            "title": "Unknown delivered price",
                            "price": {"value": "20", "currency": "USD"},
                        }
                    ]
                },
            )
        return httpx.Response(200, json=fixture)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = EbayClient(settings(), http_client=http, max_retries=0)
        listings = await client.search_by_image(
            b"image-bytes", fallback_keywords="blue shirt"
        )

    assert listings[0].total == Decimal("50.49")
    browse_paths = [
        request.url.path for request in requests if request.url.path.startswith("/buy")
    ]
    assert browse_paths == [
        "/buy/browse/v1/item_summary/search_by_image",
        "/buy/browse/v1/item_summary/search",
    ]


@pytest.mark.asyncio
async def test_location_header_is_sent_when_a_delivery_zip_is_known() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == IDENTITY_URL:
            return httpx.Response(
                200, json={"access_token": "token", "expires_in": 7200}
            )
        assert (
            request.headers["X-EBAY-C-ENDUSERCTX"]
            == "contextualLocation=country=US,zip=94103"
        )
        return httpx.Response(200, json={"itemSummaries": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = EbayClient(settings("94103"), http_client=http)
        await client.search_by_keywords("vintage jacket")


@pytest.mark.asyncio
async def test_location_header_uses_selected_market_country() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == IDENTITY_URL:
            return httpx.Response(
                200, json={"access_token": "token", "expires_in": 7200}
            )
        assert request.headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_GB"
        assert (
            request.headers["X-EBAY-C-ENDUSERCTX"]
            == "contextualLocation=country=GB,zip=SW1A 1AA"
        )
        return httpx.Response(200, json={"itemSummaries": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = EbayClient(settings("SW1A 1AA", "EBAY_GB", "GB"), http_client=http)
        await client.search_by_keywords("vintage jacket")


@pytest.mark.asyncio
async def test_token_refreshes_after_expiry() -> None:
    token_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests
        if str(request.url) == IDENTITY_URL:
            token_requests += 1
            return httpx.Response(
                200,
                json={"access_token": f"token-{token_requests}", "expires_in": 120},
            )
        assert request.headers["Authorization"] == f"Bearer token-{token_requests}"
        return httpx.Response(200, json={"itemSummaries": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = EbayClient(settings(), http_client=http, cache_enabled=False)
        await client.search_by_keywords("first query")
        await client.search_by_keywords("second query")

    assert token_requests == 2


@pytest.mark.asyncio
async def test_image_search_posts_a_base64_crop() -> None:
    crop = b"small-jpeg-crop"

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == IDENTITY_URL:
            return httpx.Response(
                200, json={"access_token": "token", "expires_in": 7200}
            )
        assert request.method == "POST"
        assert request.url.path.endswith("/search_by_image")
        assert json.loads(request.content) == {"image": b64encode(crop).decode("ascii")}
        return httpx.Response(200, json={"itemSummaries": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = EbayClient(settings(), http_client=http)
        assert await client.search_by_image(crop) == []
