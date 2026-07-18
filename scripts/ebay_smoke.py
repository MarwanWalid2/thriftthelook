"""Run a live eBay Browse image search against a local crop image.

Usage: uv run python scripts/ebay_smoke.py path/to/crop.jpg
"""

import argparse
import asyncio
from pathlib import Path

from api.ebay import EbayClient, EbayClientError


async def run(image_path: Path, fallback_keywords: str | None) -> None:
    crop = image_path.read_bytes()
    async with EbayClient() as ebay:
        listings = await ebay.search_by_image(crop, fallback_keywords=fallback_keywords)
    if not listings:
        print("No listings returned.")
        return
    for listing in listings[:10]:
        delivery = (
            str(listing.total)
            if listing.total is not None
            else "shipping unavailable"
        )
        print(f"{listing.title} | ${delivery} | {listing.item_url or listing.id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test eBay image search.")
    parser.add_argument("image", type=Path, help="Path to a JPEG or PNG crop")
    parser.add_argument(
        "--fallback-keywords", help="Used only if image search has no results"
    )
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"Image does not exist: {args.image}")
    try:
        asyncio.run(run(args.image, args.fallback_keywords))
    except EbayClientError as error:
        raise SystemExit(f"eBay smoke test failed: {error}") from error


if __name__ == "__main__":
    main()
