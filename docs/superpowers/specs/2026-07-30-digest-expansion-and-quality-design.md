# Digest Expansion and Quality — Design

**Date:** 2026-07-30
**Status:** Approved (design), pending implementation plan

## Problem

Three requests, plus an open-ended "what else":

1. Expand news sources.
2. Avoid duplicates.
3. Some titles are too long.

Investigation changed the shape of two of these.

## Evidence gathered

Measurements taken against the live `digest.db` (415 published items, 45 digests).

### Duplicates are not currently a problem — but expansion will create them

| Check | Result |
| --- | --- |
| Same-day, different-source pairs ≥ 0.75 | **0** across all 415 published items |
| Cross-day pairs ≥ 0.70 (07-29 vs 07-30) | **0** |
| Within-day pairs ≥ 0.78 | **1** (07-30) |
| Cross-date pairs ≥ 0.75 | 64 |

The single within-day pair is **not** a duplicate:

- `0.824` "Gemini Robotics 2 brings whole body intelligence to robots" (VLA motor-control model)
- `0.824` "Gemini Robotics ER 2: powering robotics with video understanding…" (embodied-reasoning model)

Both are official DeepMind posts announcing *different models* from one launch. Merging them is
the documented false-merge failure from 2026-07-29, when threshold 0.80 merged "Claude Opus 4.5"
with "Opus 4.6". **The main threshold must stay at 0.83.**

Zero same-source-story duplication is an artifact of non-overlapping sources: each enabled feed
covers a distinct beat, and only TechCrunch competes editorially with the labs' own blogs.
Adding outlets removes that property. **Dedup hardening is insurance for expansion, not a
response to a current defect.**

The 64 cross-date pairs are mostly narrative continuity, not duplication:

| Similarity | Earlier | Later |
| --- | --- | --- |
| 0.899 | "$20 million to Public First Action" (W07) | "Donating *another* $20 million" (W30) |
| 0.844 | "Introducing Claude Sonnet 4.5" (2025-W40) | "Introducing Sonnet 4.6" (W08) |
| 0.829 | "raises $30B Series G" (W07) | "raises $65B Series H" (W22) |
| 0.822 | "OpenAI models, Codex come to AWS" (W18) | "…now available on AWS" (W23) |

These are weeks or months apart, beyond the 14-day `seen` window. Suppressing them would lose
real news. **Decision: link them, do not suppress.**

### The cap binds unevenly

Modelled against 07-30's pool of 72 items at significance ≥ 0.25:

| cap | model_releases | policy_business | research | tools_products | total |
| --- | --- | --- | --- | --- | --- |
| 6 | 5 | 6 | 6 | 2 | 19 |
| 10 | 5 | 10 | 10 | 2 | 27 |
| none | 5 | 15 | 50 | 2 | 72 |

`model_releases` (5 available) and `tools_products` (2 available) are **supply-starved** — no cap
value changes them. `research` has 50 candidates behind the cap, nearly all arXiv, and ranks 7–12
are generic ("Flow Map Learning via Nongradient Vector Flow", 0.55). A uniform cap raise
therefore buys mostly low-value arXiv volume.

### Title lengths

Median 56 chars, but 42% exceed 60, 13% exceed 80, max 150. Worst offenders by median:
`gemini_grounding` 130, `arxiv_lg` 120, `arxiv_ai` 88. No template truncates — every one
interpolates `{{ it.title }}` raw, and `.lead-title` renders up to 62px.

A rule-based split on `:` / em-dash covers only **21%** of long titles, and some splits sever the
payload ("A Dream of Spring for Open-Weight LLMs**: 10 Architectures from Jan-Feb 2026**").

### `cluster_sources` is discarded

`dedup.dedup_batch` computes `cluster_sources` and `cluster_size`; `llm._payload` passes it as
`also_covered_by`; `render._annotate` displays it. But `store.save_items` never persists it
(`store.py:194` documents this; `store.py:206` resets it to `[]`). Corroboration is lost on save,
so re-renders and DB-sourced pool items show nothing. This is the strongest signal available once
outlets overlap.

## Goals

- A longer digest, driven by per-category headroom and new sources in starved beats.
- Duplicate protection that holds up when sources overlap, without merging distinct stories.
- Recurring stories linked to their earlier chapters.
- Long titles displayed short without losing key numbers.

## Non-goals

- Lowering the main dedup threshold below 0.83.
- Suppressing recurring stories.
- Re-backfilling the archive (separate, already-parked decision requiring `--purge-all`).
- Reddit / YouTube / Substack expansion (parked in memo §11 Phase 2b).

## Phases

Ordered for visible wins first. The one hard dependency: **Phase 4 must follow Phase 3**, because
source expansion is what creates the overlap condition Phase 3 defends against.

### Phase 1 — `headline` field

Long titles shortened by the LLM, at no extra API call.

- `llm.py`: add `headline` to the enrich JSON schema and `SYSTEM` prompt. Constraint: ≤ 60
  characters, no trailing period, no `" - Publisher"` suffix, and **numbers preserved verbatim**
  per the project rule. Parse via a `_clean_str` guard that word-boundary-truncates if the model
  overshoots.
- `store.py`: `items.headline TEXT DEFAULT ''`, added through the existing idempotent `_migrate()`.
  `save_items` writes it; read APIs return it.
- `render.py`: templates use `{{ it.headline or it.title }}` and set `title="{{ it.title }}"` on
  the anchor so the full text remains available on hover.

The 415 archived rows have no headline and fall back to `title`, unchanged.

**Verification:** run enrich against ~5 real items; assert every `headline` is non-empty and
≤ 70 chars, and that any number appearing in the headline matches the source title. The prompt asks
for ≤ 60; the check allows 70 so that a marginal overshoot is a warning rather than a hard failure,
since the `_clean_str` guard truncates anything longer before storage.

### Phase 2 — Hybrid per-category caps

Per-category ceiling plus per-category significance floor.

```yaml
settings:
  categories:
    model_releases:  { max_items: 10, min_significance: 0.30 }
    research:        { max_items: 6,  min_significance: 0.60 }
    tools_products:  { max_items: 10, min_significance: 0.30 }
    policy_business: { max_items: 10, min_significance: 0.40 }
```

- `config.py`: `Settings.category_rules: dict[str, CategoryRule]`, falling back to the existing
  global `max_items_per_category` and `min_significance` for any category not listed.
- `pipeline.py`: the global `min_significance` 0.25 stays as a hard pre-filter; the per-category
  floor applies inside grouping.
- `render.group_by_category` takes per-category caps and floors instead of one `cap`.
- `_drop_reasons` gains a `category_floor` reason, distinct from the global `min_significance`,
  so the accumulating tuning data stays interpretable.

**Verification:** replay 07-30's stored pool through the new grouping and confirm the counts match
the modelled table above (research 6, policy 10, model_releases 5, tools 2).

### Phase 3 — Dedup hardening and story threading

- **Persist corroboration:** `items.cluster_sources TEXT` (JSON array) and
  `items.cluster_size INTEGER DEFAULT 1`. Render shows "covered by N sources".
- **Persist embeddings:** new table `item_emb(id TEXT PRIMARY KEY, embedding BLOB, digest_date TEXT)`,
  retained 180 days. The 14-day `seen` window cannot reach the W07→W22 span that threading needs.
  Backfill the existing 415 items locally with `dedup.embed` (no API cost). Retention is enforced by
  a `purge_old_embeddings(180)` call alongside the existing `purge_old_seen` step in `pipeline.run`,
  so the two retention windows stay independent and neither silently truncates the other.
- **Threading:** for each published item, find the highest-similarity item from an *earlier*
  `digest_date` in the band **[0.75, 0.83)** — related but below the duplicate line — and store
  `items.thread_parent_id TEXT`. Render as "Earlier: {parent headline} ({parent date})", linking to
  the parent's archive page. Threading is cross-date only, so same-day distinct announcements like
  the Gemini Robotics pair are never linked.
- Main threshold stays 0.83; grounding stays 0.78 (shipped 2026-07-30).

**Verification:** assert the known pairs thread (Series G → Series H, Sonnet 4.5 → 4.6); assert the
two same-day Gemini Robotics items produce no thread link.

### Phase 4 — Targeted source expansion

Aimed at the starved beats rather than broad volume.

- **`tools_products`** (2 items today): enable `hn_show` — Show HN filtered to AI, already
  `status: verified` and sitting at `enabled: false`. It is a product-launch feed by construction.
- **`model_releases`** (5 items today): add non-US labs, the clearest structural blind spot —
  Mistral (currently `no_feed`), Qwen, DeepSeek, Cohere.
- **Grounding quality:** blocklist news-roundup/content-farm domains in `llm.catch_missed_news`
  (2026-07-30 surfaced `buildfastwithai.com` and `unrot.co`, which also produced that day's
  duplicate) and add a primary-source preference to the prompt.
- **gnews:** apply the two recorded fixes — `email.utils.parsedate_to_datetime` as a `_norm_date`
  fallback, and `fetch.resolve_url()` on article URLs — then re-enable narrowly as a gap-filler for
  organisations without their own feed, not as a broad keyword search.

**Verification:** dry-run shows each new source returning > 0 items; `tools_products` and
`model_releases` counts rise; re-run the same-day cross-source duplicate scan and confirm nothing
appears above 0.83.

## Cost

Significance is assigned *by* the LLM, so every fetched item is enriched before any floor can drop
it. Source expansion raises enrichment cost linearly with item count. The per-category floors save
reader attention, not tokens. `headline` adds a few output tokens per item and no extra request.

## Risks

| Risk | Mitigation |
| --- | --- |
| `headline` drops a key number | Explicit prompt rule; spot-check verification step |
| Threading links unrelated stories in the 0.75–0.83 band | Cross-date only; band is bounded below the duplicate line; links are additive, never suppress |
| Expansion raises cost without raising quality | Per-category floors; scope new sources to starved beats only |
| New overlapping outlets reintroduce duplicates | Phase 3 ships first; `cluster_size` makes overlap visible |

## Testing

The project has no automated test suite; verification is by targeted scripts against the live DB,
matching existing practice. Each phase lists its own verification step above. `pipeline.py --dry-run`
covers collection and rendering without LLM cost or DB writes, and `git status` must be clean
afterward since dry-run overwrites `output/`.
