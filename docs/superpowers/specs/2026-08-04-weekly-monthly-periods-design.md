# Weekly and monthly digests — design (2026-08-04)

## Problem

The site publishes one page per day and nothing above it. A reader who missed a week has no way
to see what mattered that week except opening seven daily pages, and the masthead's period chip
is a dead label (`Daily`) with the Weekly and Monthly slots deliberately left out because no
implementation existed (`templates/macros.html`, 2026-08-03).

Weekly pages *appear* to exist — `archive/2026-W31.html` and 42 siblings — but they are not
rollups. They are the one-time backfill's own runs: each holds only what the seven blog/lab
sources published that week, bucketed by `digest_date = '2026-W31'`.

That produces a direct contradiction. `2026-W31` covers Jul 27 – Aug 2, and so do the live
dailies `2026-07-28` … `2026-08-02`. The weekly page shows **9 stories from 7 sources**; those
six dailies published **94 stories from 16 sources**. Same calendar week, two disjoint sets, two
different answers.

## Decision

Introduce a single concept — the **period** (day, week, month) — with one page per period.
Weekly pages are rebuilt as true rollups and **absorb** the backfill pages rather than sitting
beside them. Monthly pages are new. All three kinds share the daily page's layout, navigation,
categories, and topic filters, so weekly and monthly behave exactly like today's page.

Period ordering is a new, deterministic score computed from stored data. Per-story
`significance` and the fixed ranking rubric (`PROJECT_MEMO` §3) are **not touched**. One LLM
call per period adds an editorial layer on top: headline, `$` total, category one-liners, and
trending themes.

User decisions recorded (2026-08-04): absorb the backfill weeks · hybrid ranking (deterministic
order, LLM labels only) · scaled category caps · home-page layout for all period kinds ·
themes backfilled across all history · trending themes clickable as filter chips.

## Measurements that shaped this

Run against the live `digest.db` (496 published items, 8 dailies, 43 backfill weeks):

- `2026-W31`: backfill page has 9 items; the six dailies inside that week have 94.
- `item_emb` covers **480 of 496** published items, so grouping a period into story lines costs
  no API calls. The 16 without an embedding stay singletons.
- **All 496** published items have a usable `published` date, and only **5** land in a different
  ISO week than their digest label implies. Article date is therefore a safe grouping axis, and
  it is the truthful one for a retrospective.
- Monthly volume by `published`: 2026-08 → 36 (partial), 2026-07 → 143, 2026-06 → 74,
  2026-05 → 58, 2026-04 → 52, 2026-03 → 52, 2026-02 → 61. A month is large enough to need caps
  and small enough that no chunking is required for the single LLM call.
- Five further months hold **1–2 items each** (2026-01, 2025-12, 2025-11, 2025-10, 2025-09).
  These are the `lastmod`-versus-real-`published` stragglers the memo records at 2026-07-29 and
  deliberately kept. Their monthly pages will be nearly empty; they are still generated, because
  suppressing them would mean a story reachable in search with no period page containing it.
  Twelve monthly labels exist in total.
- Topic coverage is 397 of 496, so period topic pills have real counts to work with.

## Labels

Three kinds share the existing `digests.date` column, which already mixes daily and weekly:

| kind | label | sort key |
|---|---|---|
| daily | `2026-08-04` | itself |
| weekly | `2026-W31` | that week's Monday (existing behaviour) |
| monthly | `2026-M08` | that month's first day |

`M` is not decoration. A bare `2026-08` string-sorts as a prefix of `2026-08-04`, and label
comparison happens in `label_sort_key`, `links_to_check`, `list_digests`, `embeddings_before`,
and `_feed_pub_date` — the memo already records two separate bugs caused by naive label sorting
(`'W'` > `'0'`). An unambiguous pattern keeps that class of bug closed.

`store.py` gains:

- a month branch in `label_sort_key()`
- `is_month_label()` beside the existing `is_week_label()`
- `label_kind(label) -> "daily" | "weekly" | "monthly"`

Ordering becomes `(label_sort_key, kind_rank)` with monthly < weekly < daily, so `2026-M08`
sits above the weeks and days it contains instead of tying with `2026-08-01`. Label formats stay
known **only** to `store.py`, as `is_week_label` already establishes.

## Membership — derived, never materialized

A period page is a view over already-published items. There is no `period_items` table and no
duplicated item rows.

An item's period is a pure function of its article date: `published` → ISO week → month, with
`label_sort_key(digest_date)` as the fallback when a date is missing or unparsable.

This is the load-bearing choice, for three reasons:

1. Materializing membership recreates the drift the memo repeatedly documents — `save_items`
   uses `INSERT OR REPLACE`, so a re-collected story silently changes `digest_date` and moves
   between periods.
2. Derived membership leaves `all_items()`, the search index, and `total_records` untouched. A
   story appears once in search no matter how many period pages show it.
3. Backfill items keep working: their `published` dates are accurate, so they land in the right
   week without special-casing.

New reads on `Store`:

- `items_for_period(start_date, end_date)` — published items whose effective date falls in the
  inclusive range.
- `embeddings_for(ids)` — `{id: np.ndarray}` from `item_emb`, for grouping without loading the
  sentence-transformer model.

### `digests.item_count` for period rows

For weekly and monthly labels, `item_count` is written by the period builder (the number of
story groups shown). `recount_digest()` counts rows by `digest_date` and would report 9 for
`2026-W31` instead of the rollup's ~35, so it **refuses non-daily labels**. Its two callers
(`recheck_grounding_urls.py`, the unpublish flow) only ever pass daily labels today; the guard
keeps a future caller from silently corrupting the archive index bars and footer counts, which
read from this column.

## Assembly (`periods.py`, new)

A new module owns period math and nothing else — no rendering, no LLM calls. `render.py` stays
at data shaping (§13 T3.1) and `pipeline.py` stays thin.

### Grouping repeat coverage into story lines

Two passes, both reusing already-tuned thresholds rather than introducing a new one:

1. **`thread_parent_id` chains** are unioned. Those links already assert "same story line, later
   chapter" and were validated against real data (Series G → Series H at cosine 0.8286).
2. **Remaining groups merge at `settings.thread_min_similarity` (0.75)** on their representative
   embeddings.

0.75 is the correct floor rather than a new invention: daily cross-day dedup already removes
anything ≥ 0.83, so a same-story follow-up that survived into a different day necessarily sits
in `[0.75, 0.83)` — exactly the threading band. Nothing above 0.83 can reach this stage, so the
band's upper bound is irrelevant here.

Representative = highest `significance`, ties broken by newest `published` — the same key as
`group_by_category` and `_flatten_ranked`, so period order never contradicts daily order for
tied items. Remaining members become `updates` (title + date), and the group carries two derived
figures used by the score below:

- `days_covered` — count of distinct article dates among the group's members.
- `distinct_sources` — size of the union of every member's `cluster_sources` plus its own source
  name. Using the union rather than member count matters: the same outlet reporting twice is one
  source, and `cluster_sources` is already a set for exactly this reason (2026-07-31).

### Hotness

```
hotness = peak_significance
        + min(0.15, 0.05 * (days_covered - 1) + 0.03 * (distinct_sources - 1))
```

The cap is the point. An uncapped corroboration bonus lets a widely syndicated minor story
outrank a frontier model release, which inverts the rubric the whole pipeline is built on. With
the cap, sustained coverage can move a story up within its significance neighbourhood but never
across a tier boundary.

Weights and cap live under `settings.period` in `sources.yaml`. The values above are the starting
point, not the decision. Before they are committed, the scorer runs over `2026-W31`, `2026-W30`,
and `2026-M07` and prints the top 10 with and without the bonus, so the change in position is
visible per story. The values that ship, and the ordering they produced, are recorded in
`PROJECT_MEMO` — the same evidence-first procedure used for the dedup threshold (0.83), the
grounding threshold (0.78), and the threading band.

### Volume

Caps only, no floors. Every candidate is already a published item, so the daily global and
per-category floors have already been applied — re-applying them would be the double-cut
`group_by_category(settings=None)` already warns about.

`settings.period.weekly.max_items_per_category = 10`, `monthly = 12` → roughly 35 and 45
stories per page. Category balance is preserved, so a quiet category still appears.

## Editorial layer (`llm.py`)

`generate_recap(items, model=None, themes=False)` gains a themes mode instead of a second
near-identical prompt. One call per period returns:

- `headline` — existing behaviour (`RECAP_SYSTEM` already says "a day or a week")
- `dollar_committed` — existing behaviour, now period-wide
- `category_one_liners` — existing behaviour, consumed by the period's category pages
- `trending` — **new**: 3–5 themes, each `{label, why, item_ids}`

Validation follows the `clean_topics` / `image_key` precedent of never trusting model output:
unknown `item_ids` dropped, themes capped at 5, `label` and `why` length-capped, non-list
degrading to empty.

Failure returns an empty recap and the page renders without the band — the same contract as
today, which exists because one missing comma in a recap response once discarded 6m45s of
completed enrich work (2026-07-31).

Storage: `recaps.themes_json` on the whole-period row (`category = ''`), added via the existing
`_MIGRATIONS` list.

## Rendering

`home.html` becomes the single digest template for all three period kinds, and
`archive_week.html` is retired. No new visual design is introduced — every component already
exists:

- masthead, filter row, image slots, footer: `macros.html`
- the period band's four-figure strip: the `.stat-band` markup and CSS from the retired template
- `home.html` already renders correctly at `archive/` depth with `prefix="../"`, which is how
  today's `archive/<date>.html` copy works

A period page reads: masthead (same category nav) → period band (headline, stories / peak
significance / model releases / `$` committed, trending chips) → topic filter pills → lead story
→ "Also this week/month" cards → worth-knowing and in-brief tail → sidebar.

Relative times use a period reference (the period's last day at 23:59 UTC, clamped to now),
extending `_digest_ref`'s existing rule so that re-rendering an old period does not age its
timestamps.

### Period toggle

`macros.masthead()` takes `period_links` and replaces the static `Daily` chip — precisely the
slot the template comment reserves. Links are self-consistent per page rather than global:

- from a daily page → Weekly and Monthly point at *that day's* week and month, so older pages
  never go stale as the current period advances
- from a period page → Daily points at `index.html`, the other period kind at its containing
  period

### Categories and topics

Category pages come nearly free: `render_category_page(label, cat, …, in_archive=True)` already
writes `archive/{label}-{cat}.html`, which is the scheme the backfill weeks use. Topic pills use
`_topic_filters` over the period's groups with the existing cap of 6.

### Trending chips as filters

The filter script in `macros.html` currently reads `data-topics`. It becomes parameterized on
the attribute name (about three lines), after which a `Trending` chip row filters via
`data-themes` exactly as topic pills filter via `data-topics`. Groups belonging to no theme are
visible only under `All`, matching the untagged-topic rule. The chip row appears only on period
pages and only when themes exist; CSS is unchanged because it keys solely on `.is-filtered`.

### Archive index

Gains All / Daily / Weekly / Monthly tabs using the same hide mechanism (`data-kind`), and the
count line extends to "N digests · 12 monthly · 44 weekly · 8 daily". The existing year grouping
and volume bars are unchanged and continue to sort by `label_sort_key`.

### RSS

`recent_digest_entries` narrows to daily labels. Without that filter every story ships three
times — once in its day, again in its week, again in its month — to every subscriber. This drops
the backfill weekly entries currently in the feed.

## Build paths

- **`pipeline.py`** (daily cron): after the daily render, rebuild the current week and the
  current month. Two extra LLM calls per day.
- **`rerender.py`**: rebuilds every period from the DB with zero API calls, reusing stored
  themes — the existing "design changed, no cost" path.
- **`backfill_periods.py`** (new, one-time, resumable): builds all historical periods and
  generates themes on `BACKFILL_MODEL`, skipping periods that already have `themes_json`. Same
  resume pattern as `backfill_topics.py`. Roughly 56 calls (44 weeks + 12 months). Existing
  weekly headlines are reused where present (45/45 have one), so most calls only add themes.
- **`backfill.py`**: stops rendering weekly pages itself and defers to the period builder, since
  weekly pages are now derived. Its weekly `digest_date` labels remain valid as a record of
  which run published an item.

## Testing

New `tests/test_periods.py`:

- **Label math** — `2026-M08` sort key and kind; monthly-before-weekly-before-daily ordering;
  the `2026-W01` → 2025 year trap already fixed once in the archive index; a week spanning two
  months resolving to one month.
- **Membership** — grouping by `published`; fallback to the digest label when a date is
  unparsable; a week's rollup containing both backfill and daily items.
- **Grouping** — thread chains union into one group; the 0.75 band merges follow-ups; items
  without embeddings stay singletons; representative selection and its tie-break.
- **Hotness** — the bonus cap prevents tier inversion; identical input yields identical order.
- **Caps** — per-category weekly/monthly limits; a quiet category still appears.
- **Themes** — unknown `item_ids` dropped, cap of 5, failure yields no band; chips filter via
  `data-themes` and unthemed groups appear only under `All`.
- **Guards** — `recount_digest` refuses period labels; the feed contains no period entries.
- **Render contracts** — period toggle hrefs resolve to real files at both root and `archive/`
  depth; archive tabs partition all rows.

Existing tests that reference `archive_week.html` — `test_render_assets`, `test_render_thread`,
`test_topics`, `test_render_archive_index` — are repointed at the period renderer with their
contracts unchanged (CSS link depth, thread line present on archive pages, filter row present,
no inline `<style>`, no `:root` in authored CSS).

## Out of scope

- Per-period link checking (`linkcheck.py` stays item-based).
- "Biggest movers vs last week" comparisons, and the parked yesterday-diff view (§5).
- Stable `weekly.html` / `monthly.html` bookmark URLs; navigation links straight at the period
  file, since a static site cannot redirect and duplicating the page would create two truths.
- Period-specific imagery; period pages use the existing `images.resolve()` fallback chain.
- Any change to `significance`, the ranking rubric (§3), the daily category caps and floors, or
  the source list (frozen at 16 sources).
