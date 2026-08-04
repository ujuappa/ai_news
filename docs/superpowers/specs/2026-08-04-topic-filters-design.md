# Topic filters — design (2026-08-04)

## Problem

The home page filter row duplicates the top navigation. Both show the same four categories
(`Model releases` · `Research` · `Tools & products` · `Policy & business`), so the pills cost a
row of screen space and add nothing a reader cannot already do from the nav.

Separately, the four categories describe **what kind of event** a story is, never **what domain
it is about**. "AI music startup raises $50M" is a `policy_business` event about music; "new
video generation model" is a `model_releases` event about video. The second axis is currently
invisible.

## Decision

Replace the home filter pills with **topic** pills. Leave the top navigation, the four category
pages, and the category labels on cards exactly as they are.

## Measurements that shaped this

Keyword scan over all 497 published items (crude, but it establishes the shape):

| topic | share of archive | | topic | share of archive |
|---|---|---|---|---|
| code | 26% | | health | 8% |
| money | 20% | | chips | 7% |
| security | 11% | | art | 5% |
| science | 11% | | education | 3% |
| government | 10% | | music · robotics | 2% |
| | | | video · cars | ≤1% |

Two findings drive the design:

1. **The tail is long and thin.** A 13-topic vocabulary produced **8–9 pills on a typical day,
   most holding 1–2 stories.** A filter that reveals one story is not a filter, and nine pills
   do not fit the row. → cap the row at the **top 6 by count**.
2. **Stories genuinely span topics.** 26% of the archive matched two or more. → topics are
   **multi-label**, unlike categories.

## Vocabulary

Thirteen fixed topics, in `config.TOPIC_ORDER` / `TOPIC_LABELS`:

`code` · `money` · `chips` · `government` · `security` · `science` · `health` · `art` ·
`music` · `video` · `robotics` · `cars` · `education`

Kept **separate from `CATEGORY_ORDER`** deliberately: that constant does double duty as the
top-level grouping of `sources.yaml`, so anything added to it becomes a source bucket. Topics
must never leak into source configuration.

## Components

### Storage (`store.py`)

`items.topics TEXT DEFAULT '[]'` — a JSON array, the same pattern already used by
`cluster_sources`, with a `_MIGRATIONS` entry and defensive parsing in `_row_to_item` (a
malformed value degrades to `[]` rather than raising). Added to the `save_items` insert and to
the `items_for_digest` / `all_items` selects.

### Assignment (`llm.py`)

The system prompt gains a rule: choose **0–3** topics from the fixed list, omit when none fit.
`_merge_row` then validates against the vocabulary — dropping invented values, de-duplicating,
and capping at 3 — following the existing `image_key` precedent of never trusting the model's
key directly.

The cap is load-bearing. Without it the model tags liberally, every story collects five topics,
and the pills stop discriminating.

### Backfill (`backfill_topics.py`)

One-off, resumable, modelled on `backfill_embeddings.py`. Selects only items still at `'[]'`, so
an interrupted run resumes naturally. Uses a classification-only prompt (no re-summarising) to
keep the 497-item pass cheap. Supports `--dry-run` and `--limit`.

### Rendering (`render.py`)

`_category_filters` → `_topic_filters(items, total, cap=6)`: tally topics across the day's
items, sort by count descending with `TOPIC_ORDER` as a stable tie-break, return the top 6 plus
the `All` pill. Empty topics are never emitted (a pill that filters to nothing is a dead button
— the existing category version already honours this).

`_annotate` attaches the validated `topics` list and a space-joined `topic_attr` for the DOM.

### Template and filter script (`home.html`)

Items carry `data-topics="code money"` in place of `data-cat`. The filter script changes from
string equality to a token match. The empty-section collapse (`[data-section]`) works unchanged
— it only counts non-filtered children.

CSS needs no change: it keys solely on `.is-filtered`, never on `data-cat`.

### Untagged stories

`data-topics=""` — hidden by every topic pill, visible only under `All`. No catch-all bucket.

## Out of scope

Top navigation, category pages, the category label in each card kicker, search, and the feed.

### Correction — where the pills actually appear

An earlier draft of this spec claimed archive day pages inherit the pills "because they share
`home.html`". **That is wrong.** Verified after implementation:

- `render_digest` writes `index.html` *and* `archive/<today>.html` from `home.html` → both get pills.
- Every **other** archive page — 251 of them, daily and weekly alike — is written by
  `render_archive_digest` from `archive_week.html`, which has no filter row and never had one
  (the category pills were equally absent there).

**Resolved the same day.** `archive_week.html` gained the same filter row, so all 51 archive
digest pages now carry pills and the backfill is visible. Two things this required:

- Lead and second story were loose sibling elements (kicker, title, dek, byline), so nothing
  could hide them as a unit. They are now wrapped in `.week-lead-item` / `.week-sec-item`,
  which are pure wrappers — `.week-lead-col` has no child selectors, so layout is unaffected.
- Hiding a whole grid column left an empty cell, which happens often (filter by a topic the
  lead does not carry). `.week-split:has(> .is-filtered)` collapses the grid to one column;
  browsers without `:has()` just show the gap rather than breaking.

The filter row and its script now live in `macros.html` and are shared by both templates. They
were duplicated at first, which is exactly how the archive came to be missing the feature.

## Testing

- `_merge_row` drops invented topics, de-duplicates, and enforces the cap of 3.
- Store round-trip, including a malformed JSON value degrading to `[]`.
- `_topic_filters` returns at most 6, ordered by count, tie-broken by `TOPIC_ORDER`, omitting
  empties.
- An untagged item renders `data-topics=""` and so appears only under `All`.
- The rendered page emits topic pills rather than category pills.
