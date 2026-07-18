"""Capture one live SSE run and its displayed thumbnails for demo-video rehearsal.

The output directory is intentionally local-only: eBay listing data and images are
time-sensitive provider content and must not be committed as offline fixtures.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "listing"


def _sse_events(stream: str) -> list[tuple[str, dict[str, Any]]]:
    """Decode complete SSE blocks from a saved text stream."""

    events: list[tuple[str, dict[str, Any]]] = []
    for block in stream.split("\n\n"):
        name: str | None = None
        raw_data: str | None = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            if line.startswith("data: "):
                raw_data = line.removeprefix("data: ")
        if name and raw_data:
            payload = json.loads(raw_data)
            if isinstance(payload, dict):
                events.append((name, payload))
    return events


async def _download_thumbnails(
    client: httpx.AsyncClient, payload: dict[str, Any], output: Path
) -> None:
    """Download only images exposed by the displayed look and alternatives."""

    thumbnails = output / "thumbnails"
    thumbnails.mkdir(exist_ok=True)
    result = payload.get("result", {})
    if not isinstance(result, dict):
        return
    looks = [result.get("selections", [])]
    looks.extend(
        item.get("selections", [])
        for item in result.get("alternatives", [])
        if isinstance(item, dict)
    )
    seen: set[str] = set()
    for selections in looks:
        if not isinstance(selections, list):
            continue
        for item in selections:
            if not isinstance(item, dict):
                continue
            image_url = item.get("image_url")
            listing_id = item.get("id")
            if (
                not isinstance(image_url, str)
                or not image_url.startswith(("https://", "http://"))
                or not isinstance(listing_id, str)
                or listing_id in seen
            ):
                continue
            seen.add(listing_id)
            try:
                response = await client.get(image_url)
                response.raise_for_status()
            except httpx.HTTPError as error:
                logger.warning("Could not record thumbnail for %s: %s", listing_id, error)
                continue
            (thumbnails / f"{_safe_filename(listing_id)}.jpg").write_bytes(
                response.content
            )


async def record(args: argparse.Namespace) -> None:
    """POST a photo to the local app, then save the complete SSE transcript."""

    image_path = Path(args.image)
    output = Path(args.output)
    if not image_path.is_file():
        raise ValueError(f"Image does not exist: {image_path}")
    output.mkdir(parents=True, exist_ok=True)
    content_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.post(
            f"{args.api_url.rstrip('/')}/api/outfit",
            data={"budget": str(args.budget)},
            files={"photo": (image_path.name, image_path.read_bytes(), content_type)},
        )
        response.raise_for_status()
        transcript = response.text
        events = _sse_events(transcript)
        complete = next(
            (payload for name, payload in events if name == "complete"), None
        )
        if complete is None:
            raise RuntimeError("The API did not emit a complete event.")
        if complete.get("mode") != "live":
            raise RuntimeError("Recording requires DEMO_MODE=live; no demo data was saved.")
        (output / "events.sse").write_text(transcript, encoding="utf-8")
        (output / "run.json").write_text(
            json.dumps(complete, indent=2), encoding="utf-8"
        )
        await _download_thumbnails(client, complete, output)
    logger.info("Recorded live run at %s", output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Record one live ThriftTheLook run.")
    parser.add_argument("image", help="Outfit image sent to the running local API")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--budget", type=int, default=75)
    parser.add_argument("--output", required=True, help="Untracked output directory")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(record(args))


if __name__ == "__main__":
    main()
