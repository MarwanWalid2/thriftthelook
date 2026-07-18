# ThriftTheLook â€” Agent Instructions

## What this is
Hackathon entry (OpenAI Build Week, "Apps for Your Life", deadline 2026-07-21 17:00 PT).
One photo -> GPT-5.6 decomposes the outfit -> eBay Browse API finds each piece secondhand ->
deterministic solver assembles the look under a total budget. Full spec: docs/01-thriftthelook-spec.md
(read it before large tasks). Design tokens + UI rules: spec Â§4.

## Layout
- api/  â€” Python 3.12, FastAPI, managed with uv. Run: `uv run fastapi dev api/main.py`
- web/  â€” Next.js 15 + Tailwind. Run: `pnpm --dir web dev`
- docs/ â€” spec, audit, playbook (reference, do not edit)

## Commands
- API tests: `uv run pytest api/tests -q`   (write tests for the solver and eBay client)
- Lint: `uv run ruff check api` Â· `pnpm --dir web lint`
- Types: `uv run mypy api`
- Offline run (no keys): set DEMO_MODE=offline in .env â€” must always work end-to-end

## Hard constraints
- NEVER scrape or automate Depop/Vinted/Pinterest/TikTok. Official APIs only (eBay Browse now,
  Etsy stretch). Depop/Vinted appear in the UI as disabled "coming soon" chips only.
- Secrets only via .env (gitignored). Never hardcode keys, never log them.
- All GPT-5.6 calls go through api/llm.py helpers: Responses API, structured outputs
  (json_schema strict / responses.parse + Pydantic). Models: gpt-5.6-sol (decompose, rerank),
  gpt-5.6-luna (narration, queries). Model names must be greppable â€” judges verify GPT-5.6 usage.
- Every displayed price INCLUDES shipping (Browse shippingOptions).
- The budget solver is deterministic Python (greedy/knapsack), never an LLM call.
- Every pipeline stage emits an SSE progress event (the UI's agent feed depends on it).
- Failure states are product features: partial outfit, over-budget, empty slot â€” style them
  per spec Â§4, never show a raw error or infinite spinner.
- Keep files under ~400 lines; type hints everywhere; no bare except; logger not print.

## Style
- Python: PEP 8, ruff-clean, Pydantic models for all external payloads.
- Web: Tailwind with the spec Â§4 tokens defined in tailwind config; Nunito/Caveat via next/font;
  Lucide icons; WCAG 4.5:1 body text; respect prefers-reduced-motion; no emoji as icons.

## Done means
- `uv run pytest` green, ruff/mypy clean, DEMO_MODE=offline works with zero network,
  README run instructions verified from a clean clone.