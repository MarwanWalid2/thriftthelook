# ThriftTheLook

> **Screenshot the fit. Thrift the look.**

Turn one outfit photo into a secondhand look assembled under one delivered-price budget. ThriftTheLook identifies visible pieces, finds secondhand candidates on eBay, and makes the budget trade-offs explicit.

[Open the hosted demo](https://devpost-gpt56codex.vercel.app) · [Source code](https://github.com/MarwanWalid2/thriftthelook)

## Run locally

The default offline mode needs no accounts, keys, or network calls.

```text
cp .env.example .env
uv sync
corepack pnpm --dir web install --ignore-scripts
```

Start the API and web app in separate terminals:

```text
uv run fastapi dev api/main.py
corepack pnpm --dir web dev
```

Open `http://localhost:3000`. Offline mode uses clearly labelled synthetic inventory, never live eBay content.

## What it does

1. Accepts an outfit image by upload, drag and drop, or clipboard paste.
2. Breaks the visible outfit into purchasable garment slots.
3. Searches official eBay Browse inventory by image and keyword fallback.
4. Rejects obvious visual mismatches, then solves for the strongest complete basket within the total budget.
5. Streams progress, alternatives, partial results, and the delivered-price receipt to the outfit board.

Every displayed total includes known shipping. Listings with unknown shipping are excluded from a guaranteed budget.

## Live mode

Live mode is optional. It uses a configurable model provider plus official eBay Browse credentials; no marketplace scraping is used. When configured, the hosted project stores credentials as encrypted platform environment variables, never as `NEXT_PUBLIC_*` values or committed files.

| Setting | Purpose |
| --- | --- |
| `DEMO_MODE` | `offline` for synthetic inventory, `live` for provider and eBay calls |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Configured Gemini provider and model |
| `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` | eBay client-credentials OAuth |
| `EBAY_MARKETPLACE` / `EBAY_DELIVERY_ZIP` | Marketplace and delivery context |

The model roles are configured through environment variables rather than fixed in request code. Offline mode remains available when no credentials are configured.

## Architecture

```text
photo upload / clipboard
          |
          v
configured model: strict garment-slot decomposition
          |
          +--> optional clothing crops
          |
          v
eBay Browse image search + keyword fallback
          |
          v
configured model: batched visual rerank
          |
          v
deterministic delivered-price solver
          |
          v
configured model: receipt narration
          |
          v
FastAPI SSE -> Next.js outfit board
```

The solver is deterministic Python: it uses known delivered totals, never an AI decision, and returns complete, partial, or over-budget states truthfully.

## OpenAI and Codex

The vision stages are implemented through the OpenAI Responses API with strict
Pydantic schemas in [`api/llm.py`](api/llm.py). The configured decomposition,
visual reranking, and receipt-narration roles support GPT-5.6 through deployment
environment variables; model identifiers are configuration rather than
hard-coded application defaults. If a primary provider request cannot proceed,
the same structured contract can use a configured compatible fallback. The
delivered-price solver always remains deterministic Python.

Codex was used in this workspace to scaffold the FastAPI and Next.js app,
implement the eBay OAuth/search client and tests, trace and fix serverless SSE
streaming, build the upload reliability flow, and refine the outfit-board UX.

## Quality checks

```text
uv run python -m pytest api/tests -q
uv run ruff check api
uv run python -m mypy api
corepack pnpm --dir web lint
corepack pnpm --dir web build
```

The GitHub Actions workflow runs the offline API suite plus web lint and build on every push and pull request.

## Why it is different

Visual resale tools can find a similar item. ThriftTheLook focuses on the next decision: which combination of visible pieces can be bought under one all-in budget? Its result is an auditable basket with delivery-aware slot trade-offs rather than a pile of loosely related matches.

## Roadmap

- Validate more licensed outfit photos and measure completion quality.
- Add official marketplace integrations only where partner access permits them.
- Learn preferences after the purchase-ready outfit loop is reliable.

## License

[MIT](LICENSE)
