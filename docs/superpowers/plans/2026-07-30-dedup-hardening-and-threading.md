# Dedup Hardening and Story Threading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the corroboration and embedding data the pipeline already computes but throws away, then use the retained embeddings to link recurring stories to their earlier chapters ("Earlier: Anthropic raises $30 billion in Series G (2026-W07)").

**Architecture:** Three columns and one table. `items` gains `cluster_sources` / `cluster_size` (already computed by `dedup.dedup_batch`, currently discarded at `store.py:209`) and `thread_parent_id`. A new `item_emb` table keeps embeddings for 180 days on a retention clock independent of the 14-day `seen` window, because threading has to reach back months (Series G in W07 to Series H in W22). Threading itself is one pure function in `dedup.py` that picks the nearest earlier item in the similarity band `[0.75, 0.83)` — related, but strictly below the duplicate line. Restricting candidates to *earlier dates only* is what stops same-day sibling announcements from being linked.

**Tech Stack:** Python 3.12, SQLite, numpy, sentence-transformers (local, no API), Jinja2 (inline `DictLoader` templates), pytest.

## Global Constraints

- **Python 3.12 required.** 3.9 parses dates more strictly and silently drops items. Use `.venv/bin/python`.
- **The main dedup threshold stays 0.83.** Lowering it merged "Claude Opus 4.5" with "Opus 4.6" on 2026-07-29. Grounding stays 0.78. This plan changes neither.
- **Never suppress a recurring story.** The 64 cross-date pairs are narrative continuity; they get linked, not dropped.
- **Zero API cost.** Every embedding in this plan comes from local sentence-transformers via `dedup.embed`.
- **Comments in Korean**, matching the existing codebase style. Explain *why*, not *what*.
- **`--dry-run` must never write to the DB.** It skips `save_items`, `commit_seen`, `purge_old_seen`, `record_digest`, and now `save_embeddings` / `purge_old_embeddings` / threading.
- **`--dry-run` overwrites `output/`.** After running it, restore with `git checkout -- output/ && git clean -fd output/` and confirm `git status` is clean.
- **Back up the DB before the first migration run:** `cp digest.db digest.db.bak`.
- **Commit after every task.**

---

### Task 1: Persist cluster corroboration

`dedup.dedup_batch` computes `cluster_sources` and `cluster_size`, `llm._payload` passes them to the model as `also_covered_by`, and `render._source_line_name` already renders them as "TechCrunch (+2 more)". The only broken link is storage: `save_items` never writes them and `items_for_digest` resets the list to `[]`. Today this shows as nothing because no two enabled feeds overlap; Phase 4 deliberately breaks that.

**Files:**
- Modify: `store.py` (SCHEMA ~line 38, `_MIGRATIONS` ~line 74, `save_items` ~line 153, `items_for_digest` ~line 195, `all_items` ~line 230, `dropped_items` ~line 241)
- Create: `tests/test_store_cluster.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `items.cluster_sources` (JSON array text) and `items.cluster_size` (int) columns; a private `Store._row_to_item(row) -> dict` used by all three read methods. Task 5 adds a column to the same `SELECT` lists and reuses `_row_to_item`.

- [ ] **Step 1: Write the failing test**

`tests/test_store_cluster.py`:

```python
from store import Store


def _item(**over):
    it = {"id": "c1", "source_id": "techcrunch_ai", "category": "model_releases",
          "title": "T", "headline": "", "url": "https://example.com/a", "summary": "s",
          "significance": 0.9, "is_major": True, "published": "2026-07-30T00:00:00+00:00"}
    it.update(over)
    return it


def test_cluster_sources_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(cluster_sources=["OpenAI", "TechCrunch"], cluster_size=2)],
                     "2026-07-30")
    got = store.items_for_digest("2026-07-30")[0]
    assert got["cluster_sources"] == ["OpenAI", "TechCrunch"]
    assert got["cluster_size"] == 2
    store.close()


def test_cluster_defaults_when_absent(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(id="c2")], "2026-07-30")
    got = store.items_for_digest("2026-07-30")[0]
    assert got["cluster_sources"] == []
    assert got["cluster_size"] == 1
    store.close()


def test_cluster_survives_all_items_and_dropped_items(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(id="c3", cluster_sources=["A", "B", "C"], cluster_size=3)],
                     "2026-07-30")
    store.save_items([_item(id="c4", cluster_sources=["D"], cluster_size=1)],
                     "2026-07-30", is_published=False, drop_reason="category_cap")
    assert store.all_items()[0]["cluster_sources"] == ["A", "B", "C"]
    assert store.dropped_items("2026-07-30")[0]["cluster_sources"] == ["D"]
    store.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_store_cluster.py -v`
Expected: FAIL — `KeyError: 'cluster_size'` (the column does not exist, and `items_for_digest` hardcodes `cluster_sources = []`).

- [ ] **Step 3: Add the columns to the schema and migrations**

In `store.py`, add `import json` to the imports (after `import re`).

In `SCHEMA`, change the last two lines of the `items` table from:

```
    is_published INTEGER DEFAULT 1,  -- 1=다이제스트에 실림, 0=수집했지만 탈락
    drop_reason  TEXT DEFAULT ''     -- is_published=0 일 때의 사유 (min_significance 등)
);
```

to:

```
    is_published INTEGER DEFAULT 1,  -- 1=다이제스트에 실림, 0=수집했지만 탈락
    drop_reason  TEXT DEFAULT '',    -- is_published=0 일 때의 사유 (min_significance 등)
    cluster_sources TEXT DEFAULT '[]',  -- 같은 스토리를 함께 다룬 소스 이름 (JSON 배열)
    cluster_size    INTEGER DEFAULT 1   -- 클러스터 크기(대표 1 + 병합된 N)
);
```

In `_MIGRATIONS`, append two entries:

```python
_MIGRATIONS = [
    ("is_published", "ALTER TABLE items ADD COLUMN is_published INTEGER DEFAULT 1"),
    ("drop_reason", "ALTER TABLE items ADD COLUMN drop_reason TEXT DEFAULT ''"),
    ("headline", "ALTER TABLE items ADD COLUMN headline TEXT DEFAULT ''"),
    ("cluster_sources", "ALTER TABLE items ADD COLUMN cluster_sources TEXT DEFAULT '[]'"),
    ("cluster_size", "ALTER TABLE items ADD COLUMN cluster_size INTEGER DEFAULT 1"),
]
```

- [ ] **Step 4: Write the columns in `save_items`**

Replace the `INSERT` inside `save_items` with:

```python
        for it in items:
            self.conn.execute(
                """INSERT OR REPLACE INTO items
                   (id, source_id, category, title, headline, url, summary, significance,
                    is_major, published, fetched_at, digest_date, is_published, drop_reason,
                    cluster_sources, cluster_size)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    it["id"], it["source_id"], it["category"], it["title"],
                    it.get("headline", ""), it["url"],
                    it.get("summary", ""), it.get("significance", 0.0),
                    int(it.get("is_major", False)), it.get("published", ""),
                    _now(), digest_date, int(is_published),
                    "" if is_published else drop_reason,
                    json.dumps(it.get("cluster_sources") or [], ensure_ascii=False),
                    int(it.get("cluster_size", 1) or 1),
                ),
            )
```

- [ ] **Step 5: Add the shared row decoder and use it in all three read methods**

Add this method to `Store`, immediately above `items_for_digest`:

```python
    @staticmethod
    def _row_to_item(row) -> dict:
        """DB 행 -> 파이프라인/렌더가 기대하는 dict. 읽기 API 세 곳이 같은 변환을 해야 해서
        한 군데로 모음 — 예전엔 items_for_digest 만 cluster_sources 를 손봤고(그것도 []로
        덮어썼음) all_items/dropped_items 는 원시 문자열을 그대로 흘려보냈다."""
        it = dict(row)
        it["is_major"] = bool(it.get("is_major", 0))
        raw = it.get("cluster_sources")
        try:
            it["cluster_sources"] = json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            it["cluster_sources"] = []
        it["cluster_size"] = int(it.get("cluster_size") or 1)
        return it
```

Replace `items_for_digest` (docstring included — the old one documents the now-fixed behaviour):

```python
    def items_for_digest(self, digest_date: str) -> list[dict]:
        """저장된 게재 아이템 재조회 (템플릿 변경 후 재렌더용). 탈락분(is_published=0)은 제외 —
        재렌더가 원본 다이제스트와 달라지면 안 됨. source_name 은 저장하지 않으므로
        호출부에서 source_id -> 소스 이름 매핑을 채워줘야 함(config.py 참고)."""
        rows = self.conn.execute(
            """SELECT id, source_id, category, title, headline, url, summary, significance,
                      is_major, published, cluster_sources, cluster_size FROM items
               WHERE digest_date=? AND is_published=1""",
            (digest_date,),
        ).fetchall()
        return [self._row_to_item(r) for r in rows]
```

Replace the body of `all_items`:

```python
        rows = self.conn.execute(
            """SELECT id, source_id, category, title, headline, url, summary, significance,
                      is_major, published, digest_date, cluster_sources, cluster_size FROM items
               WHERE is_published=1
               ORDER BY published DESC"""
        ).fetchall()
        return [self._row_to_item(r) for r in rows]
```

Replace the body of `dropped_items`:

```python
        sql = """SELECT id, source_id, category, title, headline, url, summary, significance,
                        is_major, published, digest_date, drop_reason,
                        cluster_sources, cluster_size FROM items
                 WHERE is_published=0"""
        params: tuple = ()
        if digest_date is not None:
            sql += " AND digest_date=?"
            params = (digest_date,)
        return [self._row_to_item(r)
                for r in self.conn.execute(sql + " ORDER BY significance DESC", params)]
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 27 passed (24 existing + 3 new).

- [ ] **Step 7: Confirm the live DB migrates cleanly**

```bash
cp digest.db digest.db.bak
.venv/bin/python -c "
from store import Store
import config
s = Store(config.DB_PATH)
print('cols:', [r[1] for r in s.conn.execute('PRAGMA table_info(items)')])
print('sample:', s.items_for_digest('2026-07-30')[0]['cluster_sources'])
s.close()"
```

Expected: the column list ends with `cluster_sources, cluster_size`, and the sample prints `[]` (archive rows predate the column — correct, not a bug).

- [ ] **Step 8: Commit**

```bash
git add store.py tests/test_store_cluster.py
git commit -m "feat(store): cluster_sources/cluster_size 영속화 — 재렌더에서도 다중 소스 표기 유지"
```

---

### Task 2: Long-term embedding store

**Files:**
- Modify: `store.py` (`SCHEMA` after the `seen` table, `counts` ~line 126, new methods after `clear_seen`)
- Modify: `pipeline.py` (`purge_all` message ~line 263)
- Create: `tests/test_store_embeddings.py`

**Interfaces:**
- Consumes: `store.label_sort_key(label) -> str` (already exists at `store.py:14`; converts `2026-W31` to a comparable ISO date).
- Produces: `Store.save_embeddings(items: list[dict], digest_date: str) -> None` (reads `it["_emb"]`, skips items without one), `Store.embeddings_before(digest_date: str) -> list[dict]` with each dict shaped `{"id": str, "embedding": np.ndarray, "digest_date": str}`, and `Store.purge_old_embeddings(retention_days: int) -> int` returning the number of rows deleted. Task 3 calls `save_embeddings`; Task 6 calls all three.

- [ ] **Step 1: Write the failing test**

`tests/test_store_embeddings.py`:

```python
import numpy as np

from store import Store


def _emb(x: float) -> np.ndarray:
    return np.array([x, 1.0 - x], dtype=np.float32)


def test_save_and_read_back(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_embeddings([{"id": "a", "_emb": _emb(0.5)}], "2026-07-29")
    got = store.embeddings_before("2026-07-30")
    assert [g["id"] for g in got] == ["a"]
    assert np.allclose(got[0]["embedding"], _emb(0.5))
    store.close()


def test_excludes_same_and_later_dates(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_embeddings([{"id": "same", "_emb": _emb(0.1)}], "2026-07-30")
    store.save_embeddings([{"id": "later", "_emb": _emb(0.2)}], "2026-07-31")
    store.save_embeddings([{"id": "earlier", "_emb": _emb(0.3)}], "2026-07-29")
    assert [g["id"] for g in store.embeddings_before("2026-07-30")] == ["earlier"]
    store.close()


def test_weekly_labels_order_chronologically(tmp_path):
    """'2026-W07' 은 문자열 비교로는 모든 일간 날짜보다 커서, 순진하게 비교하면
    과거 주가 '미래'로 판정된다 — label_sort_key 를 타는지 확인."""
    store = Store(tmp_path / "t.db")
    store.save_embeddings([{"id": "w07", "_emb": _emb(0.4)}], "2026-W07")
    assert [g["id"] for g in store.embeddings_before("2026-07-30")] == ["w07"]
    store.close()


def test_skips_items_without_embedding(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_embeddings([{"id": "none"}, {"id": "ok", "_emb": _emb(0.6)}], "2026-07-29")
    assert [g["id"] for g in store.embeddings_before("2026-07-30")] == ["ok"]
    store.close()


def test_purge_drops_only_stale_rows(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_embeddings([{"id": "old", "_emb": _emb(0.1)}], "2020-01-01")
    store.save_embeddings([{"id": "new", "_emb": _emb(0.2)}], "2026-07-29")
    assert store.purge_old_embeddings(180) == 1
    assert [g["id"] for g in store.embeddings_before("2026-07-30")] == ["new"]
    store.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_store_embeddings.py -v`
Expected: FAIL with `AttributeError: 'Store' object has no attribute 'save_embeddings'`.

- [ ] **Step 3: Add the table**

In `store.py`, add this to `SCHEMA` immediately after the `seen` table definition:

```
CREATE TABLE IF NOT EXISTS item_emb (
    id          TEXT PRIMARY KEY,   -- items.id 와 동일
    embedding   BLOB,               -- float32 벡터
    digest_date TEXT                -- 일간 'YYYY-MM-DD' 또는 주간 'YYYY-Www'
);
```

No `_MIGRATIONS` entry is needed — that list only patches missing *columns* on `items`, and `CREATE TABLE IF NOT EXISTS` already handles a brand-new table on existing DBs.

- [ ] **Step 4: Add the three methods**

In `store.py`, insert after `clear_seen` and before the `# ---- items + digests ----` comment:

```python
    # ---- item_emb (장기 임베딩 — story threading 용) ----
    def save_embeddings(self, items: list[dict], digest_date: str):
        """게재분의 임베딩을 장기 보관. seen-store 와 따로 두는 이유는 보존 기간이 달라서다 —
        seen 은 14일이면 충분하지만(며칠 전 기사 재게재 방지), threading 은 몇 달 전과 이어야
        한다(Series G W07 -> Series H W22). 한 테이블에 합치면 둘 중 하나가 반드시 손해."""
        for it in items:
            emb = it.get("_emb")
            if emb is None:
                continue
            self.conn.execute(
                "INSERT OR REPLACE INTO item_emb (id, embedding, digest_date) VALUES (?,?,?)",
                (it["id"], np.asarray(emb, dtype=np.float32).tobytes(), digest_date),
            )
        self.conn.commit()

    def embeddings_before(self, digest_date: str) -> list[dict]:
        """주어진 라벨보다 **이전** 다이제스트의 임베딩만 반환.

        같은 날을 빼는 게 오연결 방지의 핵심 — 2026-07-30 의 Gemini Robotics 2 와
        Gemini Robotics ER 2 는 cos 0.824 로 threading 구간에 들어오지만 한 발표에서 나온
        서로 다른 모델이라 이어붙이면 안 된다.

        비교를 SQL 이 아니라 파이썬에서 하는 이유: digest_date 에 주간 라벨('2026-W07')이
        섞여 있어 문자열 비교로는 시간순이 안 나온다(label_sort_key 주석 참고)."""
        key = label_sort_key(digest_date)
        out = []
        for r in self.conn.execute("SELECT id, embedding, digest_date FROM item_emb"):
            if not r["embedding"] or label_sort_key(r["digest_date"]) >= key:
                continue
            out.append({
                "id": r["id"],
                "embedding": np.frombuffer(r["embedding"], dtype=np.float32),
                "digest_date": r["digest_date"],
            })
        return out

    def purge_old_embeddings(self, retention_days: int) -> int:
        """보존 기간 지난 임베딩 삭제 (지운 행 수 반환). purge_old_seen 과 분리된 함수인 건
        의도적 — 두 보존 창(180일 / 14일)이 서로를 자르지 않아야 한다."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).date().isoformat()
        stale = [r["id"] for r in self.conn.execute("SELECT id, digest_date FROM item_emb")
                 if label_sort_key(r["digest_date"]) < cutoff]
        for i in range(0, len(stale), 500):   # SQLite 변수 상한(999) 회피
            chunk = stale[i:i + 500]
            self.conn.execute(
                f"DELETE FROM item_emb WHERE id IN ({','.join('?' * len(chunk))})", chunk)
        self.conn.commit()
        return len(stale)
```

- [ ] **Step 5: Include the new table in `counts`**

Change `counts` so destructive operations report it:

```python
    def counts(self) -> dict[str, int]:
        """테이블별 행 수 — 파괴적 작업 전에 "뭘 잃는지" 보여주는 용도."""
        return {
            t: self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("seen", "items", "digests", "recaps", "item_emb")
        }
```

In `pipeline.py`, update the `purge_all` warning so the new table is listed. Replace:

```python
    print(f"⚠️ {config.DB_PATH} 전체 삭제 — seen {c['seen']} / items {c['items']} / "
          f"digests {c['digests']} / recaps {c['recaps']} 전부 사라짐 (복구 불가).")
```

with:

```python
    print(f"⚠️ {config.DB_PATH} 전체 삭제 — seen {c['seen']} / items {c['items']} / "
          f"digests {c['digests']} / recaps {c['recaps']} / item_emb {c['item_emb']} "
          f"전부 사라짐 (복구 불가).")
    print("   item_emb 는 backfill_embeddings.py 로 재생성 가능(API 비용 0).")
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 32 passed.

- [ ] **Step 7: Commit**

```bash
git add store.py pipeline.py tests/test_store_embeddings.py
git commit -m "feat(store): item_emb 테이블 — threading 용 180일 임베딩 보관"
```

---

### Task 3: Backfill embeddings for the existing archive

Threading needs history on day one. The archive holds 474 items whose embeddings were never kept, and regenerating them is free because `dedup.embed` runs locally.

**Files:**
- Create: `backfill_embeddings.py`

**Interfaces:**
- Consumes: `Store.save_embeddings`, `Store.counts` (Task 2); `dedup.embed(texts: list[str]) -> np.ndarray` (exists at `dedup.py:23`).
- Produces: a populated `item_emb` table. Task 8 depends on the four known pairs having embeddings.

- [ ] **Step 1: Write the script**

`backfill_embeddings.py`:

```python
"""기존 아카이브 아이템의 임베딩을 item_emb 에 채우는 1회성 스크립트.

threading 은 몇 달 전 기사와 비교해야 하는데 seen-store 는 14일치뿐이고, 그마저도
매일 purge 된다. 로컬 sentence-transformers 만 쓰므로 **API 비용 0**.
여러 번 돌려도 안전 — 이미 채워진 id 는 건너뛴다.

주의: 새 아이템은 `title. summary_raw`(원문 발췌)로 임베딩되는데 여기서는 원문이 남아 있지
않아 `title. summary`(LLM 요약)를 쓴다. 둘 다 제목이 지배적이라 실무상 차이는 작지만,
threading 구간을 튜닝할 땐 이 비대칭을 감안할 것(측정값은 PROJECT_MEMO 참고).

    python backfill_embeddings.py
"""
from __future__ import annotations

import config
import dedup
from store import Store


def run():
    store = Store(config.DB_PATH)
    have = {r["id"] for r in store.conn.execute("SELECT id FROM item_emb")}
    todo = [it for it in store.all_items() if it["id"] not in have]
    if not todo:
        print(f"이미 전부 채워짐 — item_emb {len(have)}건")
        store.close()
        return

    print(f"{len(todo)}건 임베딩 생성 (기존 {len(have)}건 건너뜀) — 로컬 모델, API 비용 없음")
    embs = dedup.embed([f"{it['title']}. {it.get('summary') or ''}" for it in todo])
    for it, e in zip(todo, embs):
        it["_emb"] = e

    by_date: dict[str, list[dict]] = {}
    for it in todo:
        by_date.setdefault(it["digest_date"], []).append(it)
    for digest_date, items in by_date.items():
        store.save_embeddings(items, digest_date)

    print(f"완료 — item_emb {store.counts()['item_emb']}건 "
          f"({len(by_date)}개 다이제스트)")
    store.close()


if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python backfill_embeddings.py`
Expected: `474건 임베딩 생성 (기존 0건 건너뜀) …` then `완료 — item_emb 474건 (46개 다이제스트)`. The exact counts depend on the DB at the time; what matters is that `item_emb` ends up equal to the number of published items.

- [ ] **Step 3: Verify idempotency**

Run: `.venv/bin/python backfill_embeddings.py`
Expected: `이미 전부 채워짐 — item_emb 474건`. No rows added.

- [ ] **Step 4: Spot-check that the known pairs are present and in band**

```bash
.venv/bin/python -c "
import numpy as np, config
from store import Store
s = Store(config.DB_PATH)
rows = {r['id']: np.frombuffer(r['embedding'], dtype=np.float32)
        for r in s.conn.execute('SELECT id, embedding FROM item_emb')}
pairs = [('Series G->H', 'd7d47956', 'a3d8c6fa'), ('Sonnet 4.5->4.6', '1ccc22f7', '45f898f6')]
ids = {r['id'][:8]: r['id'] for r in s.conn.execute('SELECT id FROM items')}
for name, a, b in pairs:
    va, vb = rows[ids[a]], rows[ids[b]]
    print(f'{name}: cos={float(np.dot(va, vb)):.4f}')
s.close()"
```

Expected: two similarity values printed. Record them — Task 8 checks whether they land inside `[0.75, 0.83)`. If either falls outside, do **not** silently widen the band here; Task 8 has the decision step.

- [ ] **Step 5: Commit**

```bash
git add backfill_embeddings.py
git commit -m "feat: backfill_embeddings.py — 기존 아카이브 임베딩 소급 생성 (API 비용 0)"
```

---

### Task 4: The thread-parent matcher

**Files:**
- Modify: `dedup.py` (add after `drop_similar_to`, ~line 90)
- Create: `tests/test_thread_parent.py`

**Interfaces:**
- Consumes: `dedup._cos(a, b) -> float` (exists at `dedup.py:30`; assumes normalized vectors).
- Produces: `dedup.find_thread_parent(emb: np.ndarray, candidates: list[dict], lo: float, hi: float) -> dict | None`. Each candidate is `{"id": str, "embedding": np.ndarray, "digest_date": str}` — exactly the shape `Store.embeddings_before` returns. Task 6 calls this.

- [ ] **Step 1: Write the failing test**

`tests/test_thread_parent.py`:

```python
import numpy as np

import dedup

X = np.array([1.0, 0.0], dtype=np.float32)


def _v(cos_to_x: float) -> np.ndarray:
    """X 와의 코사인이 정확히 cos_to_x 인 단위벡터."""
    return np.array([cos_to_x, float(np.sqrt(max(0.0, 1 - cos_to_x ** 2)))], dtype=np.float32)


def _c(cid: str, cos: float) -> dict:
    return {"id": cid, "embedding": _v(cos), "digest_date": "2026-W07"}


def test_picks_highest_similarity_in_band():
    cands = [_c("weak", 0.76), _c("strong", 0.82), _c("mid", 0.79)]
    assert dedup.find_thread_parent(X, cands, 0.75, 0.83)["id"] == "strong"


def test_ignores_duplicates_well_above_upper_bound():
    """0.83 이상은 '중복'이라 이어붙일 게 아니라 dedup 이 합쳤어야 하는 값."""
    assert dedup.find_thread_parent(X, [_c("dup", 0.90)], 0.75, 0.83) is None


def test_upper_bound_is_exclusive():
    """경계가 '미만'인지 확인. float32 는 0.83 을 정확히 표현하지 못해서
    (_v(0.83) 의 실측 코사인은 0.8299999833) 상수로는 경계를 짚을 수 없다 —
    실측치를 그대로 hi 로 넘겨 '< hi' 가 '<= hi' 로 새지 않는지 본다."""
    v = _v(0.80)
    exact = float(np.dot(X, v))
    cand = [{"id": "edge", "embedding": v, "digest_date": "2026-W07"}]
    assert dedup.find_thread_parent(X, cand, 0.75, exact) is None
    # 대조군: hi 를 아주 조금만 올리면 같은 후보가 잡혀야 한다(구간이 실제로 도는지 확인).
    assert dedup.find_thread_parent(X, cand, 0.75, exact + 1e-6)["id"] == "edge"


def test_ignores_unrelated_below_lower_bound():
    assert dedup.find_thread_parent(X, [_c("far", 0.40)], 0.75, 0.83) is None


def test_returns_none_without_candidates():
    assert dedup.find_thread_parent(X, [], 0.75, 0.83) is None


def test_skips_candidates_with_no_embedding():
    cands = [{"id": "null", "embedding": None, "digest_date": "2026-W07"}, _c("ok", 0.80)]
    assert dedup.find_thread_parent(X, cands, 0.75, 0.83)["id"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_thread_parent.py -v`
Expected: FAIL with `AttributeError: module 'dedup' has no attribute 'find_thread_parent'`.

- [ ] **Step 3: Implement it**

In `dedup.py`, add after `drop_similar_to`:

```python
def find_thread_parent(emb: np.ndarray, candidates: list[dict],
                       lo: float, hi: float) -> dict | None:
    """`emb` 와 [lo, hi) 유사도 구간에서 가장 가까운 후보 하나. 없으면 None.

    구간의 위를 여는(hi 미만) 게 설계의 핵심이다. hi 이상은 '같은 스토리'라 이어붙일 게
    아니라 dedup 이 합쳐야 하는 값이고, lo 미만은 그냥 남남. 그 사이 —
    "Series G 투자" -> "Series H 투자" 같은 후속편 — 만 링크 대상이다.

    후보를 **이전 날짜로만** 한정하는 책임은 호출부(store.embeddings_before)에 있다.
    여기서 날짜를 안 보는 이유는 이 함수가 순수 벡터 연산이라 테스트가 쉬워지기 때문."""
    best, best_sim = None, -float("inf")
    for c in candidates:
        ce = c.get("embedding")
        if ce is None:
            continue
        sim = _cos(emb, ce)
        if lo <= sim < hi and sim > best_sim:
            best, best_sim = c, sim
    return best
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 39 passed.

- [ ] **Step 5: Commit**

```bash
git add dedup.py tests/test_thread_parent.py
git commit -m "feat(dedup): find_thread_parent — [0.75,0.83) 구간의 앞 이야기 찾기"
```

---

### Task 5: Persist `thread_parent_id` and look up parent display data

**Files:**
- Modify: `store.py` (`SCHEMA`, `_MIGRATIONS`, `save_items`, `items_for_digest`, `all_items`, new `thread_parent_info`)
- Create: `tests/test_store_thread.py`

**Interfaces:**
- Consumes: `Store._row_to_item` (Task 1).
- Produces: `items.thread_parent_id` column, and `Store.thread_parent_info(ids: list[str]) -> dict[str, dict]` where each value is `{"display": str, "date": str}`. Task 6 writes the column; Task 7 renders `thread_parent_info`'s output.

- [ ] **Step 1: Write the failing test**

`tests/test_store_thread.py`:

```python
from store import Store


def _item(**over):
    it = {"id": "t1", "source_id": "anthropic", "category": "policy_business",
          "title": "Anthropic raises $30 billion in Series G funding", "headline": "",
          "url": "https://example.com/g", "summary": "s", "significance": 0.9,
          "is_major": True, "published": "2026-02-10T00:00:00+00:00"}
    it.update(over)
    return it


def test_thread_parent_id_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(id="parent")], "2026-W07")
    store.save_items([_item(id="child", thread_parent_id="parent")], "2026-W22")
    assert store.items_for_digest("2026-W22")[0]["thread_parent_id"] == "parent"
    assert store.items_for_digest("2026-W07")[0]["thread_parent_id"] == ""
    store.close()


def test_thread_parent_info_prefers_headline(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(id="p1", headline="Anthropic raises $30B Series G")], "2026-W07")
    info = store.thread_parent_info(["p1"])
    assert info["p1"]["display"] == "Anthropic raises $30B Series G"
    assert info["p1"]["date"] == "2026-W07"
    store.close()


def test_thread_parent_info_falls_back_to_title(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(id="p2", headline="")], "2026-W07")
    assert store.thread_parent_info(["p2"])["p2"]["display"].startswith("Anthropic raises $30")
    store.close()


def test_thread_parent_info_ignores_blanks_and_unknowns(tmp_path):
    store = Store(tmp_path / "t.db")
    assert store.thread_parent_info([]) == {}
    assert store.thread_parent_info(["", None]) == {}
    assert store.thread_parent_info(["nope"]) == {}
    store.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_store_thread.py -v`
Expected: FAIL — `KeyError: 'thread_parent_id'`.

- [ ] **Step 3: Add the column**

In `SCHEMA`, change the tail of the `items` table to:

```
    cluster_sources TEXT DEFAULT '[]',  -- 같은 스토리를 함께 다룬 소스 이름 (JSON 배열)
    cluster_size    INTEGER DEFAULT 1,  -- 클러스터 크기(대표 1 + 병합된 N)
    thread_parent_id TEXT DEFAULT ''    -- 같은 스토리의 '앞 이야기' items.id (없으면 '')
);
```

Append to `_MIGRATIONS`:

```python
    ("thread_parent_id", "ALTER TABLE items ADD COLUMN thread_parent_id TEXT DEFAULT ''"),
```

- [ ] **Step 4: Write and read the column**

In `save_items`, add `thread_parent_id` to the column list and one more `?`, and append the value:

```python
                """INSERT OR REPLACE INTO items
                   (id, source_id, category, title, headline, url, summary, significance,
                    is_major, published, fetched_at, digest_date, is_published, drop_reason,
                    cluster_sources, cluster_size, thread_parent_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
```

and, as the final tuple entry after `int(it.get("cluster_size", 1) or 1),`:

```python
                    it.get("thread_parent_id") or "",
```

Add `thread_parent_id` to the `SELECT` list in both `items_for_digest` and `all_items` (leave `dropped_items` alone — dropped items are never rendered, so they have no thread line).

`items_for_digest`:

```python
            """SELECT id, source_id, category, title, headline, url, summary, significance,
                      is_major, published, cluster_sources, cluster_size, thread_parent_id
               FROM items WHERE digest_date=? AND is_published=1""",
```

`all_items`:

```python
            """SELECT id, source_id, category, title, headline, url, summary, significance,
                      is_major, published, digest_date, cluster_sources, cluster_size,
                      thread_parent_id FROM items
               WHERE is_published=1
               ORDER BY published DESC"""
```

- [ ] **Step 5: Add the parent lookup**

Add to `Store`, after `dropped_items`:

```python
    def thread_parent_info(self, ids: list[str]) -> dict[str, dict]:
        """thread_parent_id -> {"display", "date"} 매핑.

        렌더가 'Earlier: {제목} ({날짜})' 를 그리려면 부모의 표시 제목과 실린 날짜가 필요한데,
        부모는 보통 몇 달 전 다이제스트라 현재 렌더 중인 groups 안에 없다. 그래서 DB 조회."""
        ids = [i for i in dict.fromkeys(ids) if i]
        if not ids:
            return {}
        rows = self.conn.execute(
            f"""SELECT id, headline, title, digest_date FROM items
                WHERE id IN ({','.join('?' * len(ids))})""",
            ids,
        ).fetchall()
        return {
            r["id"]: {"display": (r["headline"] or "").strip() or r["title"],
                      "date": r["digest_date"]}
            for r in rows
        }
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 43 passed.

- [ ] **Step 7: Commit**

```bash
git add store.py tests/test_store_thread.py
git commit -m "feat(store): thread_parent_id 컬럼 + 부모 표시정보 조회"
```

---

### Task 6: Wire threading into the pipeline

**Files:**
- Modify: `sources.yaml` (`settings.dedup` block, lines 47-57)
- Modify: `config.py` (`Settings` ~line 67, `load` ~line 106)
- Modify: `pipeline.py` (new `_thread_parents` helper, `run` save block ~line 173)
- Create: `tests/test_thread_settings.py`

**Interfaces:**
- Consumes: `dedup.find_thread_parent` (Task 4), `Store.embeddings_before` / `save_embeddings` / `purge_old_embeddings` (Task 2), `items.thread_parent_id` (Task 5).
- Produces: `Settings.thread_min_similarity`, `Settings.thread_max_similarity`, `Settings.embedding_retention_days`; `pipeline._thread_parents(flat, store, today, settings) -> int`. Task 7 renders what this writes.

- [ ] **Step 1: Write the failing test**

`tests/test_thread_settings.py`:

```python
import config


def test_thread_settings_load_from_yaml():
    s = config.load().settings
    assert s.thread_min_similarity == 0.75
    assert s.thread_max_similarity == 0.83
    assert s.embedding_retention_days == 180


def test_thread_band_sits_below_the_dedup_line():
    """상한이 dedup 임계값을 넘으면 '중복'을 '앞 이야기'로 링크하게 된다."""
    s = config.load().settings
    assert s.thread_max_similarity <= s.dedup_threshold
    assert s.thread_min_similarity < s.thread_max_similarity


def test_embeddings_outlive_the_seen_window():
    s = config.load().settings
    assert s.embedding_retention_days > s.seen_store_retention_days
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_thread_settings.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'thread_min_similarity'`.

- [ ] **Step 3: Add the settings to `sources.yaml`**

In the `settings.dedup` block, after the `seen_store_retention_days: 14` line, add:

```yaml
    thread_min: 0.75                 # [thread_min, thread_max) = "관련 있지만 중복은 아님".
    thread_max: 0.83                 # 상한을 threshold 와 같게 두는 게 핵심 — 그 위는 중복이라
                                     # 이어붙일 게 아니라 합쳐야 한다. 2026-07-30 측정에서
                                     # 이 구간에 든 64쌍은 대부분 후속편이었다
                                     # (Sonnet 4.5->4.6 0.844 는 구간 위, Series G->H 0.829 는 안).
    embedding_retention_days: 180    # seen(14일)과 별개 창. Series G(W07) -> Series H(W22) 처럼
                                     # 몇 달 걸쳐 이어지는 스토리를 잡으려면 이만큼 필요.
```

- [ ] **Step 4: Read them in `config.py`**

Add three fields to `Settings`, after `seen_store_retention_days`:

```python
    thread_min_similarity: float = 0.75       # 이 아래는 남남
    thread_max_similarity: float = 0.83       # 이 위는 중복(=dedup 이 합칠 것)
    embedding_retention_days: int = 180
```

Add three lines to the `Settings(...)` construction in `load`, after `seen_store_retention_days=...`:

```python
        thread_min_similarity=dedup.get("thread_min", 0.75),
        thread_max_similarity=dedup.get("thread_max", 0.83),
        embedding_retention_days=dedup.get("embedding_retention_days", 180),
```

- [ ] **Step 5: Run the config tests**

Run: `.venv/bin/python -m pytest tests/test_thread_settings.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 6: Add the pipeline helper**

In `pipeline.py`, add after `_grounding_items` and before `_health_warnings`:

```python
def _thread_parents(flat: list[dict], store: Store, today: str, settings) -> int:
    """게재분에 '앞 이야기'를 연결하고 연결 건수를 반환.

    후보를 이전 날짜로만 좁히는 게 오연결 방지의 핵심이다. 2026-07-30 의 Gemini Robotics 2 와
    Gemini Robotics ER 2 는 cos 0.824 로 구간 안이지만 한 발표에서 나온 다른 모델이라 이어지면
    안 되는데, 같은 날이라 애초에 후보에 안 들어온다.

    이번 실행분(_emb 가 있는 것)만 대상. DB 에서 읽어온 항목은 저장된 thread_parent_id 를
    그대로 들고 와 다시 저장되므로 덮어써지지 않는다 — 같은 날 두 번 돌려도 안전."""
    earlier = store.embeddings_before(today)
    if not earlier:
        return 0
    linked = 0
    for it in flat:
        emb = it.get("_emb")
        if emb is None or it.get("thread_parent_id"):
            continue
        parent = dedup.find_thread_parent(
            emb, earlier, settings.thread_min_similarity, settings.thread_max_similarity)
        if parent:
            it["thread_parent_id"] = parent["id"]
            linked += 1
    return linked
```

- [ ] **Step 7: Call it in `run`**

In `run`, inside the `if not dry_run:` block, replace:

```python
    if not dry_run:
        store.save_items(flat, today)
```

with:

```python
    if not dry_run:
        linked = _thread_parents(flat, store, today, settings)
        if linked:
            print(f"      앞 이야기 연결 {linked}건")
        store.save_items(flat, today)
```

Then, immediately after the existing `store.purge_old_seen(settings.seen_store_retention_days)` line, add:

```python
        # 임베딩은 seen 과 다른 창(180일)으로 따로 관리 — threading 이 몇 달 전까지 닿아야 함.
        # `_emb` 가 있는 것만 저장되므로 DB 풀에서 올라온 항목(오전에 캡 드롭됐다가 오후에
        # 게재된 경우 등)은 빠질 수 있다. 치명적이지 않고 backfill_embeddings.py 를 다시
        # 돌리면 메워지므로, 여기서 임베딩을 새로 계산하지는 않는다(모델 로드 비용).
        store.save_embeddings(flat, today)
        store.purge_old_embeddings(settings.embedding_retention_days)
```

- [ ] **Step 8: Verify the dry-run still writes nothing**

```bash
.venv/bin/python -c "
from store import Store
import config
s = Store(config.DB_PATH)
print('before:', s.counts())
s.close()"
.venv/bin/python pipeline.py --dry-run
.venv/bin/python -c "
from store import Store
import config
s = Store(config.DB_PATH)
print('after :', s.counts())
s.close()"
git checkout -- output/ && git clean -fd output/ && git status --porcelain
```

Expected: the `before` and `after` count dicts are identical (including `item_emb`), and `git status --porcelain` prints nothing.

- [ ] **Step 9: Run the full suite and commit**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 46 passed.

```bash
git add sources.yaml config.py pipeline.py tests/test_thread_settings.py
git commit -m "feat(pipeline): threading 배선 + 임베딩 180일 보관/정리"
```

---

### Task 7: Render the "Earlier" line

Corroboration needs no render work — `render._source_line_name` already turns `cluster_sources` into "TechCrunch (+2 more)", and Task 1 made that survive a re-render. This task is only the thread line.

The line goes in the three home-page blocks built from `<div>`s (lead, grid3, worth) as a real link, and on the category page as a `<span>`, because `.cat-row` is itself an `<a>` and nesting anchors is invalid HTML. The single-line `brief` rows and the weekly archive template are deliberately skipped — no room, and weekly pages are re-rendered from already-capped DB rows.

**Files:**
- Modify: `render.py` (`_BASE_CSS` ~line 96, `_annotate` ~line 818, `_HOME_TMPL` lead/grid3/worth blocks, `_CATEGORY_TMPL` row block, `render_digest` ~line 915, `render_category_page` ~line 998)
- Modify: `pipeline.py` (`run`, before the render step ~line 204)
- Modify: `rerender.py` (`run`, inside the per-digest loop ~line 41)
- Create: `tests/test_render_thread.py`

**Interfaces:**
- Consumes: `Store.thread_parent_info` (Task 5), `items.thread_parent_id` (Task 5).
- Produces: `it["thread_parent"]` set by callers as `{"display": str, "date": str}` or `None`; `it["thread"]` computed by `render._annotate`; a `prefix` template variable (`""` at the site root, `"../"` inside `output/archive/`).

- [ ] **Step 1: Write the failing test**

`tests/test_render_thread.py`:

```python
import render


def _item(**over):
    it = {"id": "a", "title": "Anthropic raises $65B in Series H", "headline": "",
          "url": "https://example.com/h", "significance": 0.9, "is_major": False,
          "summary": "s", "published": "2026-07-30T00:00:00+00:00", "source_id": "anthropic",
          "source_name": "Anthropic", "category": "policy_business"}
    it.update(over)
    return it


_PARENT = {"display": "Anthropic raises $30B Series G", "date": "2026-W07"}


def test_annotate_exposes_thread_when_parent_present():
    it = _item(thread_parent=_PARENT)
    render._annotate(it)
    assert it["thread"]["display"] == "Anthropic raises $30B Series G"
    assert it["thread"]["date"] == "2026-W07"


def test_annotate_thread_is_none_without_parent():
    it = _item()
    render._annotate(it)
    assert it["thread"] is None
    it2 = _item(thread_parent=None)
    render._annotate(it2)
    assert it2["thread"] is None


def test_home_lead_links_to_parent_archive_page(tmp_path):
    groups = [("policy_business", [_item(thread_parent=_PARENT)])]
    render.render_digest("2026-07-30", groups, [], tmp_path, total_records=1)

    root = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Earlier: Anthropic raises $30B Series G (2026-W07)" in root
    assert 'href="archive/2026-W07.html"' in root

    # 아카이브 사본은 output/archive/ 안에 있으므로 상대경로에 ../ 가 붙어야 한다.
    arch = (tmp_path / "archive" / "2026-07-30.html").read_text(encoding="utf-8")
    assert 'href="../archive/2026-W07.html"' in arch


def test_category_row_shows_thread_without_nesting_an_anchor(tmp_path):
    groups = [("policy_business", [_item(thread_parent=_PARENT)])]
    render.render_category_page("2026-07-30", "policy_business", groups, tmp_path,
                                in_archive=False, total_records=1)
    html = (tmp_path / "policy_business.html").read_text(encoding="utf-8")
    assert "Earlier: Anthropic raises $30B Series G (2026-W07)" in html
    assert '<span class="thread-line">' in html


def test_no_thread_line_when_absent(tmp_path):
    groups = [("policy_business", [_item()])]
    render.render_digest("2026-07-30", groups, [], tmp_path, total_records=1)
    assert "Earlier:" not in (tmp_path / "index.html").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_render_thread.py -v`
Expected: FAIL with `KeyError: 'thread'` on the first test.

- [ ] **Step 3: Add the CSS**

`_BASE_CSS` is concatenated into every template (`render.py` lines 421, 531, 583, 672, 715), so one rule covers all pages. Add at the end of `_BASE_CSS`, just before its closing `"""`:

```css
.thread-line { display:block; margin:0 0 8px; padding-left:9px; text-decoration:none;
               border-left:2px solid rgba(var(--inkrgb),.25);
               font:600 11px/1.45 Archivo,sans-serif; letter-spacing:.03em;
               color:rgba(var(--inkrgb),.5); }
a.thread-line:hover { color:var(--accd); border-left-color:var(--accd); }
```

- [ ] **Step 4: Compute `thread` in `_annotate`**

Replace `_annotate` with:

```python
def _annotate(it: dict, rank: int | None = None) -> None:
    it["domain_path"] = _domain_path(it["url"])
    it["tier_label"] = _tier(it.get("significance", 0.0))
    it["source_name"] = _source_line_name(it)
    # 표시용 제목은 headline 우선, 없으면 원제목. 한 군데서만 정하고 템플릿은 이것만 쓴다
    # (아카이브 415건은 headline 이 비어 있어서 그대로 원제목으로 나간다).
    it["display_title"] = (it.get("headline") or "").strip() or it["title"]
    # 앞 이야기. 호출부(pipeline/rerender)가 store.thread_parent_info 로 채워준 것만 쓴다 —
    # 부모는 보통 몇 달 전 다이제스트라 지금 렌더 중인 groups 안에 없다.
    parent = it.get("thread_parent")
    it["thread"] = parent if parent and parent.get("display") else None
    if rank is not None:
        it["rank"] = rank
```

- [ ] **Step 5: Add the line to the three home-page blocks**

In `_HOME_TMPL`, after the lead dek (`<p class="lead-dek">{{ lead.summary }}</p>`), insert:

```html
    {% if lead.thread %}<a class="thread-line" href="{{ prefix }}archive/{{ lead.thread.date }}.html">Earlier: {{ lead.thread.display }} ({{ lead.thread.date }})</a>{% endif %}
```

After the grid3 dek (`<p class="item-dek">{{ it.summary }}</p>`), insert:

```html
    {% if it.thread %}<a class="thread-line" href="{{ prefix }}archive/{{ it.thread.date }}.html">Earlier: {{ it.thread.display }} ({{ it.thread.date }})</a>{% endif %}
```

After the worth dek (`<div class="wk-dek">{{ it.summary }}</div>`), insert:

```html
        {% if it.thread %}<a class="thread-line" href="{{ prefix }}archive/{{ it.thread.date }}.html">Earlier: {{ it.thread.display }} ({{ it.thread.date }})</a>{% endif %}
```

- [ ] **Step 6: Add the line to the category rows**

In `_CATEGORY_TMPL`, after the dek line (`{% if it.show_dek %}<div class="cat-row-dek">{{ it.summary }}</div>{% endif %}`), insert a **span**, not an anchor — the enclosing `.cat-row` is already an `<a>`:

```html
    {% if it.thread %}<span class="thread-line">Earlier: {{ it.thread.display }} ({{ it.thread.date }})</span>{% endif %}
```

- [ ] **Step 7: Pass `prefix` to the templates**

In `render_digest`, add `prefix=prefix,` to the `tmpl.render(...)` call (the loop already computes `prefix` on the line above `home_href`).

In `render_category_page`, add `prefix=("../" if in_archive else ""),` to its `tmpl.render(...)` call. The category template only renders a span, but passing it keeps the two templates consistent if the row layout is ever un-nested.

- [ ] **Step 8: Attach parent info before rendering**

In `pipeline.py`, in `run`, immediately after the `print("[5/5] 렌더")` line, add:

```python
    parent_info = store.thread_parent_info([it.get("thread_parent_id", "") for it in flat])
    for it in flat:
        it["thread_parent"] = parent_info.get(it.get("thread_parent_id") or "")
```

In `rerender.py`, inside the `for d in digests:` loop, after the `it["source_name"] = ...` loop, add:

```python
        parent_info = store.thread_parent_info([it.get("thread_parent_id", "") for it in items])
        for it in items:
            it["thread_parent"] = parent_info.get(it.get("thread_parent_id") or "")
```

- [ ] **Step 9: Run the tests**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 51 passed.

- [ ] **Step 10: Eyeball a real page**

```bash
.venv/bin/python rerender.py && open output/index.html
```

Expected: pages render unchanged (no archive item has a `thread_parent_id` yet, so no "Earlier" lines appear). Confirm nothing regressed, then restore:

```bash
git checkout -- output/ && git clean -fd output/ && git status --porcelain
```

Expected: no output.

- [ ] **Step 11: Commit**

```bash
git add render.py pipeline.py rerender.py tests/test_render_thread.py
git commit -m "feat(render): 'Earlier: …' 앞 이야기 링크"
```

---

### Task 8: End-to-end verification against the known pairs

The spec names four real story pairs and one negative control that must **not** link. All five exist in the live DB — verified 2026-07-30.

| Role | id prefix | digest_date | title |
| --- | --- | --- | --- |
| parent | `d7d47956` | 2026-W07 | Anthropic raises $30 billion in Series G funding |
| child | `a3d8c6fa` | 2026-W22 | Anthropic raises $65B in Series H funding |
| parent (above band, must NOT thread) | `1ccc22f7` | 2025-W40 | Introducing Claude Sonnet 4.5 |
| child (above band, must NOT thread) | `45f898f6` | 2026-W08 | Introducing Sonnet 4.6 |
| negative (same day) | `7909c613` / `06b8d0ad` | both 2026-07-30 | Gemini Robotics 2 / Gemini Robotics ER 2 |

**Files:**
- Create: `tests/test_threading_live.py`
- Modify: `PROJECT_MEMO.md`, `README.md`

**Interfaces:**
- Consumes: everything from Tasks 1-7.
- Produces: no new code interfaces.

- [ ] **Step 1: Write the live-data test**

This one reads the real `digest.db` and skips cleanly if it is absent or not yet backfilled, so CI without a DB stays green.

`tests/test_threading_live.py`:

```python
"""실제 digest.db 로 threading 을 검증. DB 나 임베딩이 없으면 skip (CI 는 DB 없이 돈다)."""
import numpy as np
import pytest

import config
import dedup
from store import Store

# 2026-07-30 실측(backfill_embeddings.py 로 생성한 임베딩 기준).
# 두 쌍 다 '후속편'이지만 유사도가 갈린다 — 구간 안/밖을 각각 고정해 둔다.
PAIRS_IN_BAND = [("Series G -> Series H", "d7d47956", "a3d8c6fa", 0.8286)]
# Sonnet 4.5 -> 4.6 은 cos 0.8445 로 dedup 임계값(0.83) 위. 사람이 보면 후속편이지만
# 임베딩상으로는 '같은 스토리'에 가깝다. 여기서 구간을 넓히면 진짜 중복까지 '앞 이야기'로
# 붙게 되므로(2026-07-29 Opus 4.5/4.6 오병합 사고와 같은 계열) 넓히지 않기로 결정.
# 이 테스트는 그 결정을 고정하는 회귀 가드다 — 나중에 누가 thread_max 를 올리면 여기서 깨진다.
PAIRS_ABOVE_BAND = [("Sonnet 4.5 -> Sonnet 4.6", "1ccc22f7", "45f898f6", 0.8445)]
SAME_DAY = ("7909c613", "06b8d0ad")


@pytest.fixture(scope="module")
def live():
    if not config.DB_PATH.exists():
        pytest.skip("digest.db 없음")
    store = Store(config.DB_PATH)
    embs = {r["id"]: np.frombuffer(r["embedding"], dtype=np.float32)
            for r in store.conn.execute("SELECT id, embedding FROM item_emb")
            if r["embedding"]}
    if not embs:
        pytest.skip("item_emb 비어 있음 — backfill_embeddings.py 를 먼저 실행할 것")
    meta = {r["id"]: r["digest_date"]
            for r in store.conn.execute("SELECT id, digest_date FROM items")}
    yield {"embs": embs, "meta": meta,
           "full": {i[:8]: i for i in meta},
           "settings": config.load().settings}
    store.close()


def _pair(live, a, b):
    ids = live["full"]
    for short in (a, b):
        if short not in ids:
            pytest.skip(f"{short} 아이템이 DB 에 없음")
    va, vb = live["embs"].get(ids[a]), live["embs"].get(ids[b])
    if va is None or vb is None:
        pytest.skip("임베딩 없음")
    return float(np.dot(va, vb)), ids[a], ids[b]


@pytest.mark.parametrize("name,a,b,measured", PAIRS_IN_BAND)
def test_in_band_pairs_land_in_the_threading_band(live, name, a, b, measured):
    s = live["settings"]
    sim, _ia, _ib = _pair(live, a, b)
    assert s.thread_min_similarity <= sim < s.thread_max_similarity, (
        f"{name}: cos={sim:.4f} 가 [{s.thread_min_similarity}, "
        f"{s.thread_max_similarity}) 밖 (2026-07-30 실측 {measured})")


@pytest.mark.parametrize("name,a,b,measured", PAIRS_IN_BAND)
def test_child_selects_the_parent(live, name, a, b, measured):
    """자식이 '이전 날짜 후보' 전체 중에서 실제로 그 부모를 고르는지.
    구간 안에 있다는 것만으로는 부족하다 — 더 가까운 다른 후보가 있으면 그쪽이 뽑힌다."""
    s = live["settings"]
    _sim, ida, idb = _pair(live, a, b)
    store = Store(config.DB_PATH)
    cands = store.embeddings_before(live["meta"][idb])
    got = dedup.find_thread_parent(live["embs"][idb], cands,
                                   s.thread_min_similarity, s.thread_max_similarity)
    store.close()
    assert got is not None and got["id"] == ida, (
        f"{name}: 부모로 {got and got['id']} 를 골랐음 (기대: {ida})")


@pytest.mark.parametrize("name,a,b,measured", PAIRS_ABOVE_BAND)
def test_above_band_pairs_are_not_threaded(live, name, a, b, measured):
    """상한 위 쌍은 '중복'으로 취급되어 연결되지 않는다는 결정을 고정한다.

    사람 눈엔 후속편이라 연결되길 기대하게 되는데, 그러려면 thread_max 를 dedup 임계값
    위로 올려야 하고 그 순간 진짜 중복까지 앞 이야기로 붙는다. 그래서 '연결 안 됨'이
    의도된 동작 — 누가 구간을 넓히면 이 테스트가 깨지면서 결정을 다시 보게 만든다."""
    s = live["settings"]
    sim, ida, idb = _pair(live, a, b)
    assert sim >= s.thread_max_similarity, (
        f"{name}: cos={sim:.4f} 가 상한 {s.thread_max_similarity} 아래로 내려옴 "
        f"(2026-07-30 실측 {measured}) — 이제 연결 가능하니 결정을 재검토할 것")
    store = Store(config.DB_PATH)
    cands = store.embeddings_before(live["meta"][idb])
    got = dedup.find_thread_parent(live["embs"][idb], cands,
                                   s.thread_min_similarity, s.thread_max_similarity)
    store.close()
    assert got is None or got["id"] != ida, f"{name}: 상한 위인데 부모로 연결됨"


def test_same_day_siblings_are_never_linked(live):
    """Gemini Robotics 2 / ER 2 는 cos 0.824 로 구간 안이지만 같은 날 다른 모델이다.
    embeddings_before 가 같은 날짜를 빼주므로 후보에조차 안 들어와야 한다."""
    a, b = SAME_DAY
    sim, ida, idb = _pair(live, a, b)
    assert live["meta"][ida] == live["meta"][idb], "같은 날 항목이어야 이 테스트가 의미 있음"
    store = Store(config.DB_PATH)
    cand_ids = {c["id"] for c in store.embeddings_before(live["meta"][idb])}
    store.close()
    assert ida not in cand_ids, f"같은 날 항목이 후보에 들어옴 (cos={sim:.4f})"
```

- [ ] **Step 2: Run it and read the numbers**

Run: `.venv/bin/python -m pytest tests/test_threading_live.py -v`

Expected: 4 passed.

The two cosines were already measured on 2026-07-30 during the embedding backfill: **Series G → Series H = 0.8286** (inside the band, with only 0.0014 of margin) and **Sonnet 4.5 → Sonnet 4.6 = 0.8445** (above the 0.83 ceiling). The tests above encode exactly that split, so a green run means reality still matches the recorded decision.

If a test fails, the assertion message prints the measured value. **Do not widen the band past `dedup_threshold` (0.83)** — that is the whole point of `test_above_band_pairs_are_not_threaded`, and crossing it would link genuine duplicates as story history. If the Series G pair drifts below 0.75, lower `thread_min` in `sources.yaml` to just under the measured value, re-run, and record the measurement and reason in `PROJECT_MEMO.md`.

- [ ] **Step 3: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 55 passed.

- [ ] **Step 4: Confirm a dry-run is still clean**

```bash
.venv/bin/python pipeline.py --dry-run
git checkout -- output/ && git clean -fd output/ && git status --porcelain
```

Expected: the run completes without traceback and `git status --porcelain` prints nothing.

- [ ] **Step 5: Update `PROJECT_MEMO.md`**

Append a changelog entry at the **bottom** of the `## 변경 로그` section — the log runs oldest-first, so the newest entry goes last, immediately after the existing `2026-07-30: headline 필드 + 카테고리별 상한/하한` entry. The entry describes: the two new `items` columns plus `thread_parent_id`; the `item_emb` table and its 180-day window (independent of the 14-day `seen` window, purged by `purge_old_embeddings`); `backfill_embeddings.py` and the `title. summary` vs `title. summary_raw` asymmetry; the `[thread_min, thread_max)` band with the **measured** cosines from Step 2; and the fact that cross-date-only candidacy is what protects same-day sibling announcements. Note that the main threshold stayed 0.83 and grounding stayed 0.78.

- [ ] **Step 6: Update `README.md`**

Add `backfill_embeddings.py` to the script list with a one-line description ("아카이브 임베딩 소급 생성 — threading 용, API 비용 0, 재실행 안전"), and mention the two retention windows (seen 14일 / item_emb 180일) wherever the dedup behaviour is described.

- [ ] **Step 7: Commit**

```bash
git add tests/test_threading_live.py PROJECT_MEMO.md README.md
git commit -m "test: 실데이터 threading 검증 + 문서 갱신"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement (Phase 3) | Task |
| --- | --- |
| `items.cluster_sources` (JSON) + `cluster_size`, render shows corroboration | Task 1 (render side already existed via `_source_line_name`) |
| `item_emb(id, embedding, digest_date)` table | Task 2 |
| 180-day retention via `purge_old_embeddings`, independent of `purge_old_seen` | Task 2 (method), Task 6 (call site) |
| Backfill existing items locally with `dedup.embed`, no API cost | Task 3 |
| Threading in band `[0.75, 0.83)`, earlier dates only, store `thread_parent_id` | Tasks 4, 5, 6 |
| Render "Earlier: {parent headline} ({parent date})" linking to the archive page | Task 7 |
| Main threshold stays 0.83, grounding stays 0.78 | Global Constraints; asserted in `test_thread_band_sits_below_the_dedup_line` |
| Verify Series G→H and Sonnet 4.5→4.6 thread | Task 8 |
| Verify same-day Gemini Robotics pair produces no link | Task 8 |

**Deliberate deviations, all recorded above:** the thread line is skipped in the single-line `brief` rows and the weekly archive template (no room; weekly pages re-render from already-capped rows), and it renders as a `<span>` on category pages because `.cat-row` is itself an `<a>`.

**Type consistency:** candidate dicts are `{"id", "embedding", "digest_date"}` from `Store.embeddings_before` (Task 2) straight into `dedup.find_thread_parent` (Task 4) and `pipeline._thread_parents` (Task 6). Parent display dicts are `{"display", "date"}` from `Store.thread_parent_info` (Task 5), attached as `it["thread_parent"]` by Tasks 6-7 callers and exposed as `it["thread"]` by `render._annotate` (Task 7). `Store._row_to_item` is introduced in Task 1 and extended by Task 5.
