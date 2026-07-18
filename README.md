# ThriftTheLook

> **Screenshot the fit. Thrift the look.**

Turn one outfit photo into a secondhand look assembled under a total delivered-price budget. A configured vision model understands the look and rejects visual near-misses; a deterministic solver shows exactly what it traded to stay within budget.

## Run the judge-safe offline demo

Prerequisites: Python 3.12+, Node.js 22+, and pnpm. If pnpm is not already enabled, use `corepack pnpm` in place of `pnpm` below.

1. Copy `.env.example` to `.env`; leave `DEMO_MODE=offline`.
2. Run `uv sync` and `pnpm --dir web install --ignore-scripts`.
3. In separate terminals, run `uv run fastapi dev api/main.py` and `pnpm --dir web dev`.

Open `http://localhost:3000`. The demo has no keys and makes no marketplace or model requests. Its inventory is clearly marked synthetic—not live eBay content.

## What it does

1. Accepts an outfit image by file upload, drag/drop surface, or clipboard paste.
2. In live mode, the configured vision model decomposes the outfit into structured garment slots and searches official eBay Browse inventory by crop or keywords.
3. Reranks candidates per slot, rejects wrong garment types or dominant colors, and uses a deterministic solver to choose the best delivered-price combination under budget.
4. Shows the choices, delivered-total calculation, agent receipt, alternatives, and an honest partial/over-budget state.

The offline demo replays the same sequence using a synthetic, licence-safe catalogue. It is intentionally not presented as live eBay inventory.

## Architecture

```text
photo upload / clipboard
          |
          v
configured model decomposition (strict Pydantic schema)
          |
          +--> YOLOv8 clothing crops (optional live extra)
          |          |
          |          v
          +--> eBay Browse image search + keyword fallback
                         |
                         v
             configured model batched candidate rerank
                         |
                         v
             deterministic delivered-price solver
                         |
                         v
              configured model receipt narration
                         |
                         v
              FastAPI SSE -> Next.js outfit board
```

## Live setup

Set these in a local `.env`—never commit them:

```dotenv
DEMO_MODE=live
OPENAI_API_KEY=
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
EBAY_MARKETPLACE=EBAY_US
```

Run `uv sync --extra vision` to enable YOLOv8/Pillow clothing crops. Production eBay validation requires a permitted eBay Browse application. The client uses the official Browse API only; it does not scrape Depop, Vinted, Pinterest, TikTok, or any marketplace.

To compare the detector against saved model-produced boxes, run:

```text
uv run --extra vision python scripts/crop_compare.py path/to/outfit.jpg path/to/decomposition.json --gpt-boxes
```

For live eBay results, enter a destination ZIP before treating shipping as known. The UI should show listing price, shipping, and delivered total separately. Live listing content is short-lived and is not committed to the repository; [eBay's API license](https://developer.ebay.com/cms/files/api_license_2018-10-26.pdf) requires current display data.

### Record a live rehearsal

With the API already running in `DEMO_MODE=live`, capture a video-rehearsal run locally:

```text
uv run python scripts/record_run.py path/to/outfit.jpg --output recordings/look-01
```

This saves the SSE transcript, normalized displayed result, and displayed thumbnails outside version control. The committed offline demo deliberately uses original synthetic artwork instead of stale marketplace content.

## Verification

```text
uv run python -m pytest api/tests -q
uv run ruff check api
uv run python -m mypy api
pnpm --dir web lint
pnpm --dir web build
```

On this build, the API tests cover OAuth token reuse, eBay payload normalization, identical-query caching, shipping-aware assembly, a wrong-item (duvet cover) reject, synthetic demo budget re-solve, SSE output, and crop padding.

The checked-in [CI workflow](.github/workflows/ci.yml) reruns this offline API suite plus the web lint/build on every push or pull request.

## Configurable model roles

Every model call lives in [api/llm.py](api/llm.py). The provider and model IDs are set only through environment configuration; the source code contains no runtime model default.

- [Decomposition](api/llm.py) turns one outfit image into strict garment slots, including optional comparison boxes.
- [Batched rerank](api/llm.py) scores all candidate thumbnails for one slot and returns a strict score/reason/reject payload.
- [Narration](api/llm.py) writes the receipt after—not instead of—the deterministic budget decision.

Set `OPENAI_SOL_MODEL`, `OPENAI_LUNA_MODEL`, or `GEMINI_MODEL` in `.env` for the provider you choose. The checked-in [.env.example](.env.example) documents the contest configuration without making it an application dependency.

The solver in [api/pipeline/assemble.py](api/pipeline/assemble.py) never calls a model. It optimizes known delivered totals, excludes listings with unknown shipping, and returns a complete, partial, or over-budget state truthfully.

## Why this is different

Visual resale discovery already exists. Beni advertises screenshot/photo secondhand search across marketplaces, and Phia focuses on finding lower prices while people shop. ThriftTheLook's demo focuses on the distinct decision: *which combination of visible pieces can I buy under one delivered-price budget?* [Beni](https://www.joinbeni.com/faq), [Phia](https://phia.nyc/)

| Product | Primary moment | Budget decision shown |
| --- | --- | --- |
| Beni | Find secondhand matches from an item or image | Marketplace/item-level filters |
| Phia | Compare prices while shopping | Lower-price alternatives |
| ThriftTheLook | Rebuild a multi-piece inspiration outfit | One auditable, shipping-aware total with slot trade-offs |

## Roadmap

- eBay production validation, an explicit delivery-ZIP field, and size-aware Browse filters.
- Measure crop quality across YOLO and model-box paths on a licensed test set.
- Partner APIs for additional marketplaces only where official access permits them; Depop and Vinted remain disabled “coming soon” UI chips until then.
- Preference learning only after the core purchase-ready outfit loop proves reliable.

## License

[MIT](LICENSE)
