# ThriftTheLook — Build Spec v1 (post-audit, 2026-07-15)

> **One-liner:** Screenshot the fit. Thrift the look.
> Upload any outfit photo → GPT-5.6 breaks it into garment slots → the agent hunts real eBay
> listings for each piece → a deterministic solver assembles the complete look **under your total
> budget**, with visible reasoning and swap alternatives.
>
> **Pitch line (use verbatim in video/README):** "Refind, Beni and Phia find you *one* item.
> eBay and Vinted search one photo on one platform. Nobody rebuilds the complete look, entirely
> secondhand, under your total budget — until now."

Track: **Apps for Your Life**. Deadline: **July 21, 2026, 5:00 PM PT**. Solo build, Codex is the
builder of record (see `02-codex-playbook.md`).

---

## 1. Scope freeze

**IN (must ship):**
1. Image ingestion: drag-drop / clipboard-paste / file upload of a screenshot. Nothing else.
2. Outfit decomposition: one GPT-5.6 vision call → structured JSON garment slots.
3. Garment crops: YOLOv8n clothing detector (off-the-shelf), padded crops per slot.
4. Live search: eBay Browse `search_by_image` per crop (EBAY_US) + keyword fallback via Browse
   `/search` using GPT-5.6 attributes.
5. Rerank: one batched GPT-5.6 vision call per slot over top ~24 candidates → keep top 3 with
   one-line reasons; strict reject rule (wrong garment type / wrong dominant color → discard).
6. Budget assembly: deterministic greedy/knapsack over slots (≤ 20 candidates each), **prices
   include shipping** (`shippingOptions`), maximize match quality s.t. total ≤ budget.
7. The money-shot interaction: drag budget slider → agent re-solves the whole look live, printing
   trade-offs ("spend on the jacket, save on the tee").
8. Slot interactions: swap (top-3 alternatives) and thumbs-down → live re-search of that slot
   under the remaining budget.
9. Agent activity feed: streamed narration of the plan ("decomposing → 4 slots → searching in
   parallel → solving for $75") — the machinery must be *visible*.
10. Partial success as default UI state: "4 of 5 pieces found — $61 of your $75."
11. One-time style profile (size, colors to avoid, condition floor) injected into rerank calls.
12. `DEMO_MODE=offline`: cached fixture listings + images checked into the repo; runs end-to-end
    with zero keys, zero network. This is the judge-safe path and the fallback if eBay breaks.
13. LICENSE (MIT), README per rules, <3-min video.

**OUT (cut by default — roadmap lines in README only):**
- Depop/Vinted anything (no API, ToS-banned scraping, DataDome/Cloudflare). Show as grayed-out
  "integration-ready" marketplace slots in the UI.
- Computer use in the critical path.
- Preference learning across sessions, accounts/auth, browser extension, native mobile,
  Pinterest/TikTok URL ingestion (optional 1–2h bonus: TikTok official oEmbed thumbnail fetch),
  checkout/affiliate links, self-hosted embedding index.
- Etsy as second marketplace: **stretch goal, day 5 only if core is demo-solid** (register the
  Etsy app today anyway — keys need approval lead time).

## 2. Runtime architecture (GPT-5.6 is the visible brain)

```
photo (upload/paste)
   │
   ▼
[1] DECOMPOSE  GPT-5.6 Sol, low reasoning, input_image + json_schema strict
   → slots[]: {garment_type, colors, style_desc, search_keywords, price_band_guess}
   │
   ▼
[2] CROP  YOLOv8n-clothing (kesimeg/yolov8n-clothing-detection), padded boxes
   (fallback flag: GPT-5.6 bounding boxes — test day 1, keep whichever crops better)
   │
   ▼  (all slots in parallel — asyncio)
[3] SEARCH  eBay Browse search_by_image (base64 crop, X-EBAY-C-MARKETPLACE-ID=EBAY_US)
   + Browse /search keyword fallback (category + coarse color + style)
   → merge/dedupe top ~24 per slot
   │
   ▼
[4] RERANK  GPT-5.6 Sol, ONE batched vision call per slot (crop + candidate thumbnails)
   → per-candidate {match_score 0-100, reason, reject_flag}; keep top 3
   │
   ▼
[5] ASSEMBLE  deterministic greedy/knapsack (plain Python, NOT an LLM)
   total = item price + shipping; maximize Σ match_score s.t. total ≤ budget
   → primary look + per-slot alternatives + over/under-budget states
   │
   ▼
[6] NARRATE  GPT-5.6 Luna → stylist note + trade-off lines for the feed
   ("kept the boots, swapped the jacket for a $19 vintage one — $8 under budget")
```

Why this shape (all verified in `00-adversarial-audit.md`): eBay's image matcher was built for
social-media photos; GPT-5.6 does the four *reasoning* jobs (decompose, query synthesis, rerank
with reasons, trade-off narration) so its usage is meaningful, not decorative; the solver is
deterministic so the budget feature is an *optimizer*, not a filter; per-outfit cost ≈ **$0.10–0.60**
→ ~200 full runs on the $100 API credit. Target end-to-end latency **< 60s** (parallel slots,
batched rerank, streamed progress).

## 3. Tech stack

Monorepo, two processes, judge-runnable in 3 commands:

- **`api/`** — Python 3.12 + FastAPI, managed with **uv**. OpenAI SDK (Responses API,
  `responses.parse` + Pydantic schemas), `httpx` eBay client (client-credentials OAuth, token
  cached 2h), `ultralytics` YOLOv8n, SSE endpoint streaming agent-feed events. Fixtures module for
  DEMO_MODE. Config via `.env` (never committed): `OPENAI_API_KEY`, `EBAY_CLIENT_ID`,
  `EBAY_CLIENT_SECRET`, `DEMO_MODE`.
- **`web/`** — Next.js 15 + Tailwind, static-friendly, talks to `api/` only.
- Run: `uv run fastapi dev` + `pnpm dev` (documented in README top; `DEMO_MODE=offline` needs no keys).

## 4. UI/UX — "Soft Scrapbook" design direction

Product framing: a *cute, friendly thrift companion*, not a SaaS dashboard. Grounded base
(rose/stone warmth + rounded type) with a scrapbook/collage character layer. Light theme only
(deliberate; note in README).

**Design tokens:**
```
--paper:   #FDF6EE   (app background — warm cream, subtle paper-grain texture ok)
--ink:     #3B2E2A   (primary text — 12.4:1 on paper)
--cocoa:   #6E5A52   (secondary text — 5.6:1 on paper)
--rose:    #D96A73   (primary buttons/fills, white text ≥18px bold only)
--rosedeep:#A83E48   (accent text, links, focus ring — 5.5:1 on paper)
--blush:   #F6D8D0   (card fills, hover)
--sage:    #9DBB94   (success / under-budget)
--butter:  #F4E3A8   (highlights, sticker badges)
--sky:     #BFD9E4   (info chips)
--kraft:   #E8D9C3   (price tags, receipt paper)
radius: 16px cards / 999px pills;  shadows: soft, warm-tinted, low
```
**Type:** Nunito (800 display, 600/400 body) + **Caveat** for handwritten annotations only
(sticker labels, arrows, "cut here!") — never for data or buttons. Self-host via `next/font`.

**Signature components:**
- **Drop zone** = corkboard card with washi-tape corners: "paste your inspo ✂ (screenshot any fit)".
- **Garment slot cards** = polaroids, each rotated ±2°, listing photo on top, kraft **price tag**
  (price incl. shipping), match-score as a small stitched badge, one-line GPT reason in Caveat.
- **Budget dial** = oversized price-tag slider; dragging it visibly re-solves the board.
- **Agent feed** = till-receipt strip that "prints" streamed lines (monospace on kraft).
- **Swap** = circular sticker button cycling top-3; **thumbs-down** triggers live re-search.
- **Total bar**: "Look complete — $67 of your $75" in sage, or partial-state copy in butter.
- Grayed-out marketplace chips: eBay (live) · Etsy (soon) · Depop (soon) · Vinted (soon).

**Rules:** WCAG 4.5:1 for all body text (tokens above comply); no emoji as icons (Lucide, rounded
stroke); respect `prefers-reduced-motion` (tape/rotation static, no confetti); rotation/tape on
decorative elements only — data stays straight and legible; mobile-first single column, desktop =
photo left / outfit board right.

## 5. Demo video script (< 3:00 — three mandated voiceover topics)

- **0:00–0:30 Problem** — "That jacket on TikTok is $340 new. Resale is headed to $350B by 2028,
  but rebuilding a whole look secondhand means hours across five apps." Show a real fit-check
  screenshot being pasted.
- **0:30–1:45 Wow demo** — decompose animation → slots fill with live eBay finds → **drag budget
  $150 → $75, watch the re-solve + trade-off lines** → thumbs-down one piece, agent re-hunts →
  final board: "the whole look, $67, all secondhand." Name incumbents in one line (single-item
  only) — this is the Quality-of-the-Idea proof.
- **1:45–2:20 How I used Codex** — screen-capture of the actual canonical Codex thread, AGENTS.md,
  one concrete before/after ("Codex built the eBay OAuth client + searchByImage integration from
  the spec in one shot"). Mention the session ID is submitted.
- **2:20–2:50 How I used GPT-5.6** — show the decompose structured-output call and the rerank call
  in code/logs with the model name visible; one sentence on Sol for vision reasoning, Luna for narration.

Record July 20 with the 3 best of ~20 pre-tested inspiration photos. Real-time run, no time-lapse.

## 6. Schedule (backwards from the video)

| Date | Deliverable |
|---|---|
| **Jul 15 (today)** | Codex credits form (**closes Jul 17 at 12:00 PM noon PT**) · eBay dev signup · Etsy app registration · repo init + AGENTS.md + this spec committed · canonical Codex thread opened |
| Jul 16 | eBay keys → deletion exemption → **first production searchByImage call before any app code**. Pipeline stages 1–2 against fixtures |
| Jul 17 | Stages 3–4 live (search + rerank) · fixture snapshots → DEMO_MODE |
| Jul 18 | Stage 5–6 (solver + narration) · budget re-solve + thumbs-down loop |
| Jul 19 | Cute UI complete · failure/partial states · test 20 photos · optional Etsy/oEmbed stretch |
| Jul 20 | Record video · README (setup + Codex narrative) · draft Devpost submission · `/feedback` in canonical thread |
| Jul 21 | Morning buffer · **submit hours before 5 PM PT** |

**Kill-switches:** `search_by_image` access is ambiguous in eBay's docs ("experimental / select
developers" on the live method page vs. open basic scope elsewhere) — **make one real production
call on Jul 16 before writing app code**; if still blocked end of Jul 17 → keyword-search
pipeline (same key, GPT-5.6 attributes → Browse `/search`) or Etsy; if decomposition isn't
demo-solid by Jul 18 EOD → do NOT regress to single-item search (that's a worse Refind) — narrow to
3 fixed slot types (top/bottom/shoes) which is still the unclaimed combination.
