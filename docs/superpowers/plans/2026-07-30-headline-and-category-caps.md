# Headline Field and Per-Category Caps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shorten long titles with an LLM-generated `headline` field, and replace the single global category cap with per-category ceilings and significance floors, so the digest can grow without filling up with generic arXiv papers.

**Architecture:** `llm.enrich` already returns one JSON object per item; `headline` is added to that same schema, so it costs output tokens but no extra API call. Storage gains one column, and render prefers `headline` over `title` via a single `display_title` computed in `_annotate`, so templates change mechanically. Caps move from one integer to a `CategoryRule` per category, resolved through `Settings.rule_for()` so any category not configured keeps today's global behaviour.

**Tech Stack:** Python 3.12, SQLite, Jinja2 (inline `DictLoader` templates), google-genai, pytest (new, dev-only).

## Global Constraints

- **Python 3.12 required.** 3.9 parses dates more strictly and silently drops items. Use `.venv/bin/python`.
- **Numbers verbatim.** Benchmark scores, parameter counts, dollar amounts and dates must survive into `summary` and now `headline` exactly as written in the source.
- **Secrets only in `.env`.** Never commit a key, never paste one into chat. `.env` is gitignored.
- **Comments in Korean**, matching the existing codebase style. Explain *why*, not *what*.
- **`--dry-run` must never write to the DB.** It skips `save_items`, `commit_seen`, `purge_old_seen` and `record_digest`.
- **`--dry-run` overwrites `output/`.** After running it, restore with `git checkout -- output/ && git clean -fd output/` and confirm `git status` is clean.
- **Commit after every task.**

---

### Task 1: Headline parsing helpers

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`
- Create: `tests/test_llm_headline.py`
- Modify: `llm.py` (add helpers after `_as_float`, around line 122)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `llm._clean_headline(value, fallback_title: str, limit: int = 70) -> str` and `llm._merge_row(it: dict, row: dict) -> None`. Task 2 relies on `_merge_row` being the single place a model row is applied to an item. Task 3 relies on items carrying a `headline` key.

- [x] **Step 1: Create the dev dependency file**

`requirements-dev.txt`:

```
-r requirements.txt
pytest>=8.0
```

- [x] **Step 2: Write the failing test**

`tests/__init__.py` is an empty file. `tests/test_llm_headline.py`:

```python
import llm


def test_clean_headline_uses_model_value():
    assert llm._clean_headline("Sonnet 4.6 ships", "Full original title") == "Sonnet 4.6 ships"


def test_clean_headline_falls_back_when_missing():
    assert llm._clean_headline(None, "Full original title") == "Full original title"
    assert llm._clean_headline("   ", "Full original title") == "Full original title"


def test_clean_headline_strips_trailing_period():
    assert llm._clean_headline("Anthropic raises $65B.", "t") == "Anthropic raises $65B"


def test_clean_headline_truncates_on_word_boundary():
    long = "Semalith v1.4 a calibrated safety classifier achieving state of the art detection results"
    out = llm._clean_headline(long, "t", limit=40)
    assert len(out) <= 41          # 40 + the ellipsis character
    assert out.endswith("\u2026")
    assert not out[:-1].endswith(" ")
    assert " ".join(out[:-1].split()) == out[:-1]   # no mid-word cut


def test_merge_row_applies_all_fields():
    it = {"id": "a", "category": "research", "summary_raw": "raw", "title": "Original title"}
    llm._merge_row(it, {
        "id": "a", "category": "model_releases", "summary": "A summary.",
        "significance": 0.9, "is_major": True, "headline": "Short one",
    })
    assert it["category"] == "model_releases"
    assert it["summary"] == "A summary."
    assert it["significance"] == 0.9
    assert it["is_major"] is True
    assert it["headline"] == "Short one"
    assert it["_enriched"] is True


def test_merge_row_ignores_unknown_category():
    it = {"id": "a", "category": "research", "summary_raw": "raw", "title": "T"}
    llm._merge_row(it, {"id": "a", "category": "not_a_category", "summary": "s"})
    assert it["category"] == "research"


def test_merge_row_headline_falls_back_to_title():
    it = {"id": "a", "category": "research", "summary_raw": "raw", "title": "Original title"}
    llm._merge_row(it, {"id": "a", "summary": "s"})
    assert it["headline"] == "Original title"
```

- [x] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_llm_headline.py -v`
Expected: FAIL with `AttributeError: module 'llm' has no attribute '_clean_headline'`

If pytest is missing, install first: `.venv/bin/pip install -r requirements-dev.txt`

- [x] **Step 4: Write the implementation**

In `llm.py`, insert after `_as_float` (which ends at line 122):

```python
def _clean_headline(value, fallback_title: str, limit: int = 70) -> str:
    """표시용 짧은 제목. 모델이 비우거나 이상한 걸 주면 원제목으로 폴백.

    limit 을 넘기면 단어 경계에서 자른다 — 제목의 42%가 60자를 넘고 최대 150자라
    (2026-07-30 측정) 그대로 두면 .lead-title(최대 62px)에서 레이아웃이 깨진다.
    프롬프트로 60자를 요구하지만 모델이 넘길 때가 있어 저장 전에 여기서 막는다."""
    text = _clean_str(value).rstrip(".")
    if not text:
        return fallback_title
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "\u2026"


def _merge_row(it: dict, row: dict) -> None:
    """모델 응답 한 줄을 아이템에 반영. enrich 의 배치 루프에서 분리해 둔 이유는
    이 병합 규칙이 테스트 가능한 유일한 지점이기 때문(배치 호출은 네트워크가 필요)."""
    cat = row.get("category")
    if cat in CATEGORY_LABELS:
        it["category"] = cat
    it["summary"] = (row.get("summary") or it.get("summary_raw") or "")[:600]
    it["significance"] = _as_float(row.get("significance"))
    it["is_major"] = bool(row.get("is_major", False))
    it["headline"] = _clean_headline(row.get("headline"), it["title"])
    it["_enriched"] = True
```

- [x] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_llm_headline.py -v`
Expected: PASS, 7 passed

- [x] **Step 6: Commit**

```bash
git add requirements-dev.txt tests/ llm.py
git commit -m "feat(llm): headline 정제 + 행 병합 헬퍼 분리 (+pytest 도입)"
```

---

### Task 2: Ask the model for a headline

**Files:**
- Modify: `llm.py` — `SYSTEM` prompt (lines 24-37) and the `enrich` batch loop (lines 172-189)

**Interfaces:**
- Consumes: `llm._merge_row` from Task 1.
- Produces: every item returned by `llm.enrich` carries a non-empty `headline`. Tasks 3 and 4 depend on that key always existing.

- [x] **Step 1: Add the headline instruction to the prompt**

In `llm.py`, replace the `SYSTEM` constant (lines 24-37) with:

```python
SYSTEM = """You curate a personal daily AI-news digest. Items are pre-deduplicated.
For EACH item, decide:
1. category — exactly one of: model_releases, research, tools_products, policy_business, community_takes
2. summary — 2-3 sentences, in your own words (do NOT copy the source). PRESERVE key
   numbers verbatim (benchmark scores, parameter counts, dollar amounts, dates).
3. significance — 0.0-1.0, using this rubric (high to low):
   frontier model release > major funding/acquisition > benchmark record or new capability
   > notable policy shift > incremental research > community reaction
4. is_major — true only for a genuine frontier-model release, major funding/acquisition,
   or notable policy shift. Be strict; most items are false.
5. headline — a display title, AT MOST 60 characters. Keep the specific subject (model name,
   company, dollar amount) and PRESERVE numbers verbatim. Drop subtitles after a colon,
   marketing adjectives, and any " - Publisher" suffix. No trailing period.
   Example: "Gemini Robotics ER 2: powering robotics with video understanding, task
   orchestration, and multi-robot collaboration" -> "Gemini Robotics ER 2"

Prioritize signal over volume: if an item is minor or purely promotional, give it a low
significance. Return ONLY a JSON array, no prose, no markdown fences. Each element:
{"id": "...", "category": "...", "summary": "...", "significance": 0.0, "is_major": false,
 "headline": "..."}"""
```

- [x] **Step 2: Use the shared merge helper in the batch loop**

In `llm.py` `enrich`, replace lines 172-189 (the `for row in rows:` block and the fallback loop) with:

```python
        for row in rows:
            it = by_id.get(row.get("id"))
            if not it:
                continue
            _merge_row(it, row)

    # LLM 이 빠뜨렸거나 배치가 죽은 아이템 폴백
    for it in items:
        it.setdefault("summary", it.get("summary_raw", ""))
        it.setdefault("significance", 0.0)
        it.setdefault("is_major", False)
        it.setdefault("headline", it["title"])
        it.setdefault("_enriched", False)
```

- [x] **Step 3: Verify against the live API**

Run:

```bash
.venv/bin/python -c "
import llm
items = [
  {'id':'a','source_name':'DeepMind','category':'model_releases','title':'Gemini Robotics ER 2: powering robotics with video understanding, task orchestration, and multi-robot collaboration','summary_raw':'Google DeepMind released Gemini Robotics ER 2, an embodied reasoning model acting as a high-level brain for robots.'},
  {'id':'b','source_name':'TechCrunch','category':'policy_business','title':'Fish Audio raises \$52M seed to build AI voice models for creators and enterprises','summary_raw':'Fish Audio announced a \$52M seed round to build AI voice models.'},
]
out = llm.enrich(items)
for it in out:
    print(f\"[{len(it['headline']):3d}] {it['headline']}\")
    print(f\"      from: {it['title'][:70]}\")
"
```

Expected: two lines, each headline non-empty and ≤ 70 characters. The second must still contain `$52M` — the numbers-verbatim rule. If a number is dropped, strengthen the prompt example and re-run before continuing.

- [x] **Step 4: Run the unit tests again**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS, 7 passed (Task 1 tests still green after the refactor)

- [x] **Step 5: Commit**

```bash
git add llm.py
git commit -m "feat(llm): 스키마에 headline 추가 — 긴 제목 표시용 짧은 제목"
```

---

### Task 3: Persist `headline`

**Files:**
- Modify: `store.py` — `SCHEMA` (line 24-38), `_MIGRATIONS` (line 73-76), `save_items` (line 151-170), `items_for_digest` (line 192-208), `all_items` (line 227-236), `dropped_items` (line 238-248)
- Create: `tests/test_store_headline.py`

**Interfaces:**
- Consumes: items carrying `headline` from Task 2.
- Produces: `items.headline` column; every read API returns a `headline` key (empty string for pre-existing rows). Task 4 depends on that key being present but possibly empty.

- [x] **Step 1: Write the failing test**

`tests/test_store_headline.py`:

```python
from store import Store


def test_headline_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([{
        "id": "x1", "source_id": "openai", "category": "model_releases",
        "title": "A very long original title that would break the layout",
        "url": "https://example.com/a", "summary": "s", "significance": 0.9,
        "is_major": True, "published": "2026-07-30T00:00:00+00:00",
        "headline": "Short display title",
    }], "2026-07-30")
    got = store.items_for_digest("2026-07-30")
    assert got[0]["headline"] == "Short display title"
    assert got[0]["title"].startswith("A very long original")
    assert store.all_items()[0]["headline"] == "Short display title"
    store.close()


def test_headline_defaults_to_empty_when_absent(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([{
        "id": "x2", "source_id": "openai", "category": "research",
        "title": "T", "url": "https://example.com/b", "summary": "s",
        "significance": 0.1, "is_major": False, "published": "",
    }], "2026-07-30", is_published=False, drop_reason="min_significance")
    assert store.dropped_items("2026-07-30")[0]["headline"] == ""
    store.close()
```

- [x] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_store_headline.py -v`
Expected: FAIL with `KeyError: 'headline'` or `sqlite3.OperationalError: no such column: headline`

- [x] **Step 3: Add the column to the schema and migrations**

In `store.py` `SCHEMA`, add a line to the `items` table after `title TEXT,`:

```sql
    headline     TEXT DEFAULT '',    -- 표시용 짧은 제목 (LLM 생성). 비면 title 로 폴백
```

And append to `_MIGRATIONS` (after the `drop_reason` entry):

```python
    ("headline", "ALTER TABLE items ADD COLUMN headline TEXT DEFAULT ''"),
```

- [x] **Step 4: Write and read the column**

In `save_items`, replace the `INSERT` statement and its parameter tuple with:

```python
            self.conn.execute(
                """INSERT OR REPLACE INTO items
                   (id, source_id, category, title, headline, url, summary, significance,
                    is_major, published, fetched_at, digest_date, is_published, drop_reason)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    it["id"], it["source_id"], it["category"], it["title"],
                    it.get("headline", ""), it["url"],
                    it.get("summary", ""), it.get("significance", 0.0),
                    int(it.get("is_major", False)), it.get("published", ""),
                    _now(), digest_date, int(is_published),
                    "" if is_published else drop_reason,
                ),
            )
```

Then add `headline` to the `SELECT` column list in all three read methods. In `items_for_digest`:

```python
            """SELECT id, source_id, category, title, headline, url, summary, significance,
                      is_major, published FROM items
               WHERE digest_date=? AND is_published=1""",
```

In `all_items`:

```python
            """SELECT id, source_id, category, title, headline, url, summary, significance,
                      is_major, published, digest_date FROM items
               WHERE is_published=1
               ORDER BY published DESC"""
```

In `dropped_items`:

```python
        sql = """SELECT id, source_id, category, title, headline, url, summary, significance,
                        is_major, published, digest_date, drop_reason FROM items
                 WHERE is_published=0"""
```

- [x] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS, 9 passed

- [x] **Step 6: Confirm the migration is safe on the real DB**

Run:

```bash
.venv/bin/python -c "
from store import Store
import config
s = Store(config.DB_PATH)
print('counts:', s.counts())
print('headline column present:', any(r['name']=='headline' for r in s.conn.execute('PRAGMA table_info(items)')))
print('rows with empty headline:', s.conn.execute(\"SELECT COUNT(*) FROM items WHERE headline=''\").fetchone()[0])
s.close()
"
```

Expected: counts unchanged from before (items 474), column present, all 474 rows empty — the migration adds the column without touching data.

- [x] **Step 7: Commit**

```bash
git add store.py tests/test_store_headline.py
git commit -m "feat(store): items.headline 컬럼 + 멱등 마이그레이션"
```

---

### Task 4: Render the headline, keep the full title on hover

**Files:**
- Modify: `render.py` — `_annotate` (line 815-820), `_HOME_TMPL` (lines 436, 455, 474, 486), `_CATEGORY_TMPL` (line 553), `_ARCHIVE_WEEK_TMPL` (lines 739, 745, 752)
- Create: `tests/test_render_headline.py`

**Interfaces:**
- Consumes: items with a `headline` key (possibly empty) from Task 3.
- Produces: `it["display_title"]` set by `_annotate`. No later task depends on it.

- [ ] **Step 1: Write the failing test**

`tests/test_render_headline.py`:

```python
import render


def _item(**over):
    it = {"id": "a", "title": "A very long original title", "headline": "Short one",
          "url": "https://example.com/x", "significance": 0.9, "is_major": False,
          "summary": "s", "published": "2026-07-30T00:00:00+00:00",
          "source_id": "openai", "source_name": "OpenAI", "category": "model_releases"}
    it.update(over)
    return it


def test_annotate_prefers_headline():
    it = _item()
    render._annotate(it)
    assert it["display_title"] == "Short one"


def test_annotate_falls_back_to_title_when_headline_empty():
    it = _item(headline="")
    render._annotate(it)
    assert it["display_title"] == "A very long original title"


def test_annotate_falls_back_when_headline_missing():
    it = _item()
    del it["headline"]
    render._annotate(it)
    assert it["display_title"] == "A very long original title"


def test_home_page_shows_headline_and_keeps_full_title(tmp_path):
    groups = [("model_releases", [_item()])]
    render.render_digest("2026-07-30", groups, [], tmp_path, total_records=1)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Short one" in html
    assert 'title="A very long original title"' in html
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_render_headline.py -v`
Expected: FAIL with `KeyError: 'display_title'`

- [ ] **Step 3: Compute `display_title` in `_annotate`**

In `render.py`, replace `_annotate` (lines 815-820) with:

```python
def _annotate(it: dict, rank: int | None = None) -> None:
    it["domain_path"] = _domain_path(it["url"])
    it["tier_label"] = _tier(it.get("significance", 0.0))
    it["source_name"] = _source_line_name(it)
    # 표시용 제목은 headline 우선, 없으면 원제목. 한 군데서만 정하고 템플릿은 이것만 쓴다
    # (아카이브 415건은 headline 이 비어 있어서 그대로 원제목으로 나간다).
    it["display_title"] = (it.get("headline") or "").strip() or it["title"]
    if rank is not None:
        it["rank"] = rank
```

- [ ] **Step 4: Point the templates at `display_title`**

Make these eight replacements. Each keeps the full title as a hover tooltip.

In `_HOME_TMPL`:

```
line 436: <a class="lead-title" href="{{ lead.url }}" title="{{ lead.title }}">{{ lead.display_title }}</a>
line 455: <a class="item-h3" href="{{ it.url }}" title="{{ it.title }}">{{ it.display_title }}</a>
line 474: <a class="wk-title" href="{{ it.url }}" title="{{ it.title }}">{{ it.display_title }}</a>
line 486: <div><span class="brief-title" title="{{ it.title }}">{{ it.display_title }}</span><span class="brief-link">{{ it.domain_path }} →</span></div>
```

In `_CATEGORY_TMPL`:

```
line 553: <div class="cat-row-title" style="font-size:{{ it.row_size }}px" title="{{ it.title }}">{{ it.display_title }}</div>
```

In `_ARCHIVE_WEEK_TMPL`:

```
line 739: <a class="week-lead-title" href="{{ lead.url }}" title="{{ lead.title }}">{{ lead.display_title }}</a>
line 745: <a class="week-sec-title" href="{{ second.url }}" title="{{ second.title }}">{{ second.display_title }}</a>
line 752: <a class="week-rest-row" href="{{ it.url }}" title="{{ it.title }}"><span class="week-rest-num">{{ '%02d'|format(it.rank) }}</span><span class="week-rest-title">{{ it.display_title }}</span></a>
```

Leave the search index (`"t": it["title"]`, line 1007) on the full title — search recall is better against the complete text — and leave `archive_index` `top_title`, which comes from SQL.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS, 13 passed

- [ ] **Step 6: Confirm the archive still renders unchanged**

Run: `.venv/bin/python rerender.py && git diff --stat output/ | tail -3`

Expected: `rerender.py` completes; the diff shows only the added `title="…"` attributes, since every archived row has an empty `headline` and falls back to its original title. Spot-check with:

```bash
git diff output/archive/2026-W31.html | head -20
```

Then restore: `git checkout -- output/`

- [ ] **Step 7: Commit**

```bash
git add render.py tests/test_render_headline.py
git commit -m "feat(render): headline 우선 표시 + 원제목은 title 툴팁으로 보존"
```

---

### Task 5: Per-category rules in config

**Files:**
- Modify: `sources.yaml` — `settings:` block (after `max_item_age_days`, around line 27)
- Modify: `config.py` — add `CategoryRule` (after the `Source` dataclass, line 44), extend `Settings` (line 46-57), extend `load()` (line 72-83)
- Create: `tests/test_config_rules.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `config.CategoryRule(max_items: int, min_significance: float)` and `config.Settings.rule_for(category: str) -> CategoryRule`. Tasks 6 and 7 call `rule_for`.

- [ ] **Step 1: Write the failing test**

`tests/test_config_rules.py`:

```python
import config


def test_rule_for_configured_category():
    cfg = config.load()
    rule = cfg.settings.rule_for("research")
    assert rule.max_items == 6
    assert rule.min_significance == 0.55


def test_rule_for_policy_has_headroom():
    cfg = config.load()
    assert cfg.settings.rule_for("policy_business").max_items == 10


def test_rule_for_unknown_category_falls_back_to_globals():
    cfg = config.load()
    rule = cfg.settings.rule_for("community_takes")
    assert rule.max_items == cfg.settings.max_items_per_category
    assert rule.min_significance == cfg.settings.min_significance
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config_rules.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'rule_for'`

- [ ] **Step 3: Add the YAML block**

In `sources.yaml`, inside `settings:` directly after the `max_item_age_days` comment block (before `dedup:`), add:

```yaml
  # 카테고리별 상한 + 하한. 전역 max_items_per_category/min_significance 는 여기 없는
  # 카테고리의 폴백으로 남는다. 2026-07-30 측정 근거:
  #   research 후보 51건 중 29건이 0.40 에 몰린 일반 arXiv -> 하한 0.55 로 그 덩어리를 걷어내면
  #     10건이 남고 캡 6 이 실제로 작동한다. 하한을 0.60 으로 올리면 통과가 딱 6건이라
  #     캡이 무의미해지고, 점수가 조금만 내려가도 카테고리가 통째로 비어버린다.
  #   policy_business 는 15건 전부 0.50 이상이라 하한은 형식적 -> 10 까지 열어 캡으로 자른다
  #   model_releases(5건)/tools_products(2건)는 공급 부족이라 캡이 안 걸린다 -> 소스가 늘 때를 대비해 10
  categories:
    model_releases:  { max_items: 10, min_significance: 0.30 }
    research:        { max_items: 6,  min_significance: 0.55 }
    tools_products:  { max_items: 10, min_significance: 0.30 }
    policy_business: { max_items: 10, min_significance: 0.40 }
```

- [ ] **Step 4: Add `CategoryRule` and `rule_for`**

In `config.py`, add after the `Source` dataclass (line 44):

```python
@dataclass
class CategoryRule:
    """카테고리별 게재 규칙. max_items 는 상한, min_significance 는 하한.

    전역 하나로는 안 되는 이유: research 는 arXiv 때문에 후보가 50건씩 쌓이는데 7위 아래는
    일반 논문이고, tools_products 는 애초에 2건이라 캡이 의미가 없다(2026-07-30 측정)."""
    max_items: int
    min_significance: float
```

Extend `Settings` — add the field after `seen_store_retention_days`:

```python
    category_rules: dict[str, CategoryRule] = field(default_factory=dict)
```

and add the method to `Settings`:

```python
    def rule_for(self, category: str) -> CategoryRule:
        """설정에 없는 카테고리는 전역값으로 폴백 — 새 카테고리를 추가해도 안 죽는다."""
        return self.category_rules.get(
            category,
            CategoryRule(self.max_items_per_category, self.min_significance),
        )
```

In `load()`, build the rules before constructing `Settings`:

```python
    rules = {
        cat: CategoryRule(
            max_items=int(row.get("max_items", s.get("max_items_per_category", 6))),
            min_significance=float(row.get("min_significance", s.get("min_significance", 0.25))),
        )
        for cat, row in (s.get("categories") or {}).items()
    }
```

and pass `category_rules=rules,` as the last argument to the `Settings(...)` call.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS, 16 passed

- [ ] **Step 6: Commit**

```bash
git add config.py sources.yaml tests/test_config_rules.py
git commit -m "feat(config): 카테고리별 상한/하한(CategoryRule) — 전역 캡은 폴백으로"
```

---

### Task 6: Apply the rules in grouping

**Files:**
- Modify: `render.py` — `group_by_category` (lines 21-38)
- Create: `tests/test_group_rules.py`

**Interfaces:**
- Consumes: `config.CategoryRule` and `Settings.rule_for` from Task 5.
- Produces: `render.group_by_category(items, settings=None)` — when `settings` is `None` it only sorts (used by `rerender.py`, whose DB rows are already capped); when given a `Settings` it applies each category's floor then ceiling. Task 7 calls it with settings.

- [ ] **Step 1: Write the failing test**

`tests/test_group_rules.py`:

```python
import config
import render


def _items(category, n, sig):
    return [{"id": f"{category}{i}", "category": category, "significance": sig,
             "published": "2026-07-30T00:00:00+00:00"} for i in range(n)]


def test_cap_applied_per_category():
    settings = config.load().settings
    items = _items("research", 50, 0.9) + _items("policy_business", 12, 0.9)
    groups = dict(render.group_by_category(items, settings=settings))
    assert len(groups["research"]) == 6
    assert len(groups["policy_business"]) == 10


def test_floor_drops_weak_items_even_when_slots_free():
    settings = config.load().settings
    # research 하한 0.55 — 0.50 짜리는 캡(6)에 자리가 남아도 안 실린다
    groups = dict(render.group_by_category(_items("research", 3, 0.50), settings=settings))
    assert groups["research"] == []


def test_floor_is_per_category():
    settings = config.load().settings
    # 같은 0.35 라도 tools_products(0.30)는 통과, policy_business(0.40)는 탈락
    items = _items("tools_products", 1, 0.35) + _items("policy_business", 1, 0.35)
    groups = dict(render.group_by_category(items, settings=settings))
    assert len(groups["tools_products"]) == 1
    assert groups["policy_business"] == []


def test_no_settings_means_sort_only():
    groups = dict(render.group_by_category(_items("research", 50, 0.1)))
    assert len(groups["research"]) == 50
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_group_rules.py -v`
Expected: FAIL with `TypeError: group_by_category() got an unexpected keyword argument 'settings'`

- [ ] **Step 3: Write the implementation**

In `render.py`, replace `group_by_category` (lines 21-38) with:

```python
def group_by_category(items: list[dict], settings=None) -> list[tuple[str, list[dict]]]:
    """카테고리별 유의성 내림차순 그룹. community_takes 는 v1 제외.

    settings 를 주면 카테고리별 하한(min_significance) -> 상한(max_items) 순으로 적용한다
    (pipeline: 아직 안 잘린 풀). None 이면 정렬만 — rerender 는 DB 의 게재분을 읽는데
    그건 저장 시점에 이미 잘려 있어서 다시 자르면 이중 적용이 된다.
    하한을 상한보다 먼저 거는 이유: 자리가 남는다고 약한 항목이 올라오면 안 되기 때문
    (tools_products 는 후보가 2건뿐이라 캡만으로는 아무것도 못 거른다)."""
    groups: list[tuple[str, list[dict]]] = []
    for cat in CATEGORY_ORDER:
        if cat == "community_takes":
            continue
        picked = [it for it in items if it["category"] == cat]
        rule = settings.rule_for(cat) if settings is not None else None
        if rule is not None:
            picked = [it for it in picked if it["significance"] >= rule.min_significance]
        picked.sort(key=lambda it: (it["significance"], it.get("published") or ""), reverse=True)
        if rule is not None:
            picked = picked[: rule.max_items]
        groups.append((cat, picked))
    return groups
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS, 20 passed

- [ ] **Step 5: Commit**

```bash
git add render.py tests/test_group_rules.py
git commit -m "feat(render): group_by_category 가 카테고리별 하한/상한 적용"
```

---

### Task 7: Wire the pipeline and record the new drop reason

**Files:**
- Modify: `pipeline.py` — `_drop_reasons` (line 51), the `group_by_category` call (line 165), the `render_category_page` call (lines 211-216)
- Modify: `rerender.py` — the `render_category_page` call (lines 61-65). Leave `group_by_category(items)` at line 45 alone.
- Modify: `backfill.py` — the `group_by_category` call (line 126) and the `render_category_page` call (lines 141-146)
- Create: `tests/test_drop_reasons.py`

**Note:** `backfill.py` is easy to miss. It passes `cap=` positionally-by-keyword to `group_by_category`, so Task 6's signature change breaks it with `TypeError` the next time it runs. It must be updated in this task even though backfill is a one-off tool that has already run.

**Interfaces:**
- Consumes: `group_by_category(items, settings=...)` from Task 6, `Settings.rule_for` from Task 5.
- Produces: `drop_reason` values now include `category_floor`. No later task depends on this.

- [ ] **Step 1: Write the failing test**

`tests/test_drop_reasons.py`:

```python
import config
import pipeline


def _it(id_, cat, sig, enriched=True):
    return {"id": id_, "category": cat, "significance": sig, "_enriched": enriched,
            "published": "2026-07-30T00:00:00+00:00"}


def test_category_floor_is_distinct_from_global_min():
    settings = config.load().settings
    # 0.30 은 전역 0.25 는 넘지만 research 하한 0.60 에는 못 미친다
    pool = [_it("a", "research", 0.30)]
    buckets = pipeline._drop_reasons(pool, [], settings)
    assert "category_floor" in buckets
    assert buckets["category_floor"][0]["id"] == "a"


def test_global_min_still_reported():
    settings = config.load().settings
    buckets = pipeline._drop_reasons([_it("b", "research", 0.10)], [], settings)
    assert buckets["min_significance"][0]["id"] == "b"


def test_cap_drop_when_above_floor():
    settings = config.load().settings
    buckets = pipeline._drop_reasons([_it("c", "research", 0.95)], [], settings)
    assert buckets["category_cap"][0]["id"] == "c"


def test_enrich_failure_wins():
    settings = config.load().settings
    buckets = pipeline._drop_reasons([_it("d", "research", 0.95, enriched=False)], [], settings)
    assert buckets["enrich_failed"][0]["id"] == "d"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_drop_reasons.py -v`
Expected: FAIL — `KeyError: 'category_floor'`, since the item currently lands in `category_cap`

- [ ] **Step 3: Add the reason**

In `pipeline.py` `_drop_reasons`, replace the classification chain (the `if/elif` block, lines 52-59) with:

```python
        if not it.get("_enriched", True):
            reason = "enrich_failed"
        elif it["significance"] < settings.min_significance:
            reason = "min_significance"          # 전역 하한 — 홍보성/저가치
        elif it["category"] == "community_takes":
            reason = "category_off"              # v1 에서 통째로 제외되는 카테고리
        elif it["significance"] < settings.rule_for(it["category"]).min_significance:
            reason = "category_floor"            # 카테고리 하한 — 자리는 있었지만 기준 미달
        else:
            reason = "category_cap"              # 기준은 넘겼는데 자리가 없었음
```

Update the docstring's reason order to `LLM 실패 > 전역 하한 > 카테고리 OFF > 카테고리 하한 > 카테고리 상한`.

- [ ] **Step 4: Pass settings through the pipeline**

In `pipeline.py`, replace the `groups = render.group_by_category(...)` line with:

```python
    groups = render.group_by_category(ranked_pool, settings=settings)
```

and in the category-page loop, replace the `cap=` and `min_sig=` arguments so each page reports its own rule:

```python
        rule = settings.rule_for(cat)
        render.render_category_page(
            today, cat, groups, config.OUTPUT_DIR, in_archive=False,
            one_liner=recap["category_one_liners"].get(cat, ""),
            cap=rule.max_items, min_sig=rule.min_significance,
            total_records=total_records,
        )
```

In `rerender.py`, leave `group_by_category(items)` without settings (DB rows are already capped) and update only the category-page call:

```python
        for cat, cat_items in groups:
            one_liner = recaps.get(cat, {}).get("one_liner", "")
            rule = settings.rule_for(cat)
            render.render_category_page(
                label, cat, groups, config.OUTPUT_DIR, in_archive=not is_today,
                one_liner=one_liner, cap=rule.max_items,
                min_sig=rule.min_significance, total_records=total_records,
            )
```

In `backfill.py`, replace line 126 with:

```python
        groups = render.group_by_category(ranked_pool, settings=settings)
```

and the category-page call at lines 141-146 with:

```python
            rule = settings.rule_for(cat)
            render.render_category_page(
                label, cat, groups, config.OUTPUT_DIR, in_archive=True,
                one_liner=recap["category_one_liners"].get(cat, ""),
                cap=rule.max_items, min_sig=rule.min_significance,
                total_records=approx_total_records,
            )
```

- [ ] **Step 4b: Confirm no caller still uses the old `cap=` argument**

Run: `rg -n 'group_by_category\(' --glob '*.py'`

Expected: four call sites — `render.py` (the definition), `pipeline.py` and `backfill.py` passing `settings=settings`, and `rerender.py` passing nothing. No occurrence of `cap=` on a `group_by_category` call.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS, 24 passed

- [ ] **Step 6: Commit**

```bash
git add pipeline.py rerender.py tests/test_drop_reasons.py
git commit -m "feat(pipeline): 카테고리별 규칙 적용 + category_floor 탈락 사유 신설"
```

---

### Task 8: End-to-end verification and documentation

**Files:**
- Modify: `PROJECT_MEMO.md` (changelog, before the `## 11.` heading)
- Modify: `README.md` (setup section, after the `pip install` line)

**Interfaces:**
- Consumes: everything above.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Replay today's stored pool against the new rules**

Run:

```bash
.venv/bin/python -c "
import sqlite3, config, render
cfg = config.load(); s = cfg.settings
db = sqlite3.connect('digest.db'); db.row_factory = sqlite3.Row
rows = [dict(r) for r in db.execute(\"SELECT category, significance, title, published FROM items WHERE digest_date='2026-07-30'\")]
pool = [r for r in rows if r['significance'] >= s.min_significance]
for cat, items in render.group_by_category(pool, settings=s):
    rule = s.rule_for(cat)
    print(f'  {cat:18s} {len(items):2d}  (cap {rule.max_items}, floor {rule.min_significance})')
print('TOTAL', sum(len(i) for _c, i in render.group_by_category(pool, settings=s)))
"
```

Expected, exactly (simulated against the stored 2026-07-30 pool before implementation):

```
  model_releases      5  (cap 10, floor 0.3)
  research            6  (cap 6, floor 0.55)
  tools_products      1  (cap 10, floor 0.3)
  policy_business    10  (cap 10, floor 0.4)
TOTAL 22
```

That is 22 against the 19 currently live. Two of the three added items come from `policy_business` opening from 6 to 10; `tools_products` *loses* one — "GPU Management: Why Idle GPUs Are the New Grounded Aircraft" scores 0.25 and falls below the 0.30 floor. That is the floor working as intended, not a regression.

If any number differs, the rules are not being applied correctly — revisit Task 6 before continuing.

- [ ] **Step 2: Run a dry-run and confirm nothing is written**

Run: `.venv/bin/python pipeline.py --dry-run`

Expected: completes in roughly 30 seconds; the `[4/5]` line lists drop reasons including `category_floor`. Dry-run assigns a flat significance of 0.5 to every item, so `research` (floor 0.60) will be empty — that is correct behaviour for dry-run, not a bug.

- [ ] **Step 3: Restore the working tree**

Run: `git checkout -- output/ && git clean -fd output/ && git status --porcelain`
Expected: only `PROJECT_MEMO.md` and `README.md` modified; `digest.db` untouched.

- [ ] **Step 4: Document in PROJECT_MEMO.md**

Insert this entry immediately before the `## 11. 소스 확장 및 AI 그라운딩 (2026-07-29)` heading:

```markdown
- 2026-07-30: **headline 필드 + 카테고리별 상한/하한** (스펙 Phase 1-2,
  `docs/superpowers/specs/2026-07-30-digest-expansion-and-quality-design.md`).
  - 제목: 게재 415건 중 42%가 60자 초과, 최대 150자인데 템플릿이 원제목을 그대로 찍어서
    `.lead-title`(최대 62px)이 깨졌다. `:` 분리 같은 규칙은 21%밖에 못 고쳐서
    (측정) `llm.enrich` 의 기존 JSON 스키마에 `headline` 을 추가 — 호출이 안 늘어서
    비용은 출력 토큰 몇 개뿐. 렌더는 `_annotate` 가 정하는 `display_title` 하나만 보고,
    원제목은 `title=` 툴팁으로 남는다. 아카이브 415건은 headline 이 비어 원제목으로 폴백.
  - 캡: 전역 6 하나로는 안 맞았음. 07-30 풀 기준 research 는 후보 51건 중 29건이 0.40 에
    몰린 일반 arXiv 였고, tools_products 는 후보가 2건뿐이라 캡이 아무 일도 안 한다.
    `CategoryRule(max_items, min_significance)` 로 카테고리마다 따로 두고, 하한을 상한보다
    먼저 적용(자리가 남는다고 약한 항목이 올라오면 안 됨). 설정에 없는 카테고리는 전역값 폴백.
    research 하한은 0.60 이 아니라 0.55 — 0.60 이면 통과가 딱 6건이라 캡이 무의미해지고
    점수가 조금만 내려가도 카테고리가 통째로 빈다. 0.55 면 10건이 남아 캡이 실제로 일한다.
    결과: 19건 -> 22건 (policy_business 6->10, tools_products 2->1 은 0.25 짜리가 하한에 걸린 것).
  - `category_floor` 탈락 사유 신설 — 전역 하한 미달(`min_significance`)과 구분해야
    캡 튜닝 데이터가 해석 가능해진다.
  - pytest 도입(`requirements-dev.txt`, `tests/`). CI 는 다이제스트 생성 전용이라 안 붙임.
```

- [ ] **Step 5: Document the dev setup in README.md**

After the `pip install -r requirements.txt` line in the setup block, add:

```bash
pip install -r requirements-dev.txt   # 테스트용 (pytest). 파이프라인 실행에는 불필요
pytest                                 # 단위 테스트
```

- [ ] **Step 6: Commit**

```bash
git add PROJECT_MEMO.md README.md
git commit -m "docs: headline + 카테고리별 캡 변경 기록"
```

---

## Notes for the implementer

- **`row_sizes` in `render_category_page`** (line 955) is `[34, 28, 22, 17, 15, 15]`, sized for the old cap of 6. It already falls back to the last value for further items, so a cap of 10 renders correctly at 15px — no change required, but the visual ramp flattens after the sixth row. Phase 6 (UI) revisits this.
- **Dry-run and floors interact.** `--dry-run` sets every significance to 0.5, so categories with a floor above 0.5 come out empty. Do not "fix" this; a real run assigns real scores.
- **Do not re-cap in `rerender.py`.** Items read from the DB were already capped when saved; applying rules again would silently shrink historical pages.
- **A floor can empty a category.** Nothing guarantees a minimum item count per category, by design — `min_items_fallback` in settings is unrelated legacy. If a category comes out empty on a live run, check the score distribution before lowering its floor; an empty `tools_products` on a slow news day is the correct outcome.
- **Floors are tuned against a single day (2026-07-30).** After a few live runs, re-check with `store.dropped_items()` filtered to `drop_reason='category_floor'` — if genuinely good stories keep landing there, the floor is too high.
