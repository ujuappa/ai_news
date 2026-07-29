"""SQLite 저장소: 아이템 히스토리 + cross-day dedup 을 위한 seen-store."""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

_WEEK_LABEL_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def label_sort_key(label: str) -> str:
    """다이제스트 라벨(일간 'YYYY-MM-DD' / 주간 'YYYY-Www')을 비교 가능한 날짜 문자열로 변환.
    그냥 문자열 정렬하면 'W'(0x57) > '0'(0x30) 이라 주간 라벨이 모든 일간 날짜보다 위로 올라가서
    '최신 다이제스트'를 고를 때 과거 주가 뽑힌다."""
    m = _WEEK_LABEL_RE.match(label or "")
    if m:
        return date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1).isoformat()
    return label or ""

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id           TEXT PRIMARY KEY,   -- url 해시
    source_id    TEXT,
    category     TEXT,
    title        TEXT,
    url          TEXT,
    summary      TEXT,               -- LLM 요약 (없으면 원문 발췌)
    significance REAL DEFAULT 0,
    is_major     INTEGER DEFAULT 0,
    published    TEXT,               -- 기사 발행일(ISO). 게재 여부가 아님 — 그건 is_published
    fetched_at   TEXT,
    digest_date  TEXT,               -- 어느 날짜 다이제스트에 실렸는지
    is_published INTEGER DEFAULT 1,  -- 1=다이제스트에 실림, 0=수집했지만 탈락
    drop_reason  TEXT DEFAULT ''     -- is_published=0 일 때의 사유 (min_significance 등)
);

CREATE TABLE IF NOT EXISTS seen (
    id         TEXT PRIMARY KEY,     -- url 해시
    title      TEXT,
    url        TEXT,
    embedding  BLOB,                 -- float32 벡터
    first_seen TEXT
);

CREATE TABLE IF NOT EXISTS digests (
    date        TEXT PRIMARY KEY,
    item_count  INTEGER,
    html_path   TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS recaps (
    digest_date  TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT '',  -- '' = 다이제스트 전체, 아니면 카테고리별 한 줄 요약
    headline     TEXT,                       -- 전체용: 편집자 헤드라인. 카테고리용: 안 씀
    one_liner    TEXT,                       -- 카테고리용: 한 줄 요약. 전체용: 안 씀
    stats_json   TEXT,                       -- 전체용: {"dollar_committed": "$260M" | null} — 개수류는 DB에서 직접 계산
    created_at   TEXT,
    PRIMARY KEY (digest_date, category)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# CREATE TABLE IF NOT EXISTS 는 기존 테이블에 새 컬럼을 추가해주지 않으므로,
# 이미 있는 DB 를 위한 ALTER 도 따로 필요. (컬럼명, DDL 조각)
_MIGRATIONS = [
    ("is_published", "ALTER TABLE items ADD COLUMN is_published INTEGER DEFAULT 1"),
    ("drop_reason", "ALTER TABLE items ADD COLUMN drop_reason TEXT DEFAULT ''"),
]


class Store:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        """기존 DB 에 없는 컬럼만 추가. 여러 번 호출해도 안전(멱등) — 매 Store() 마다 돈다.
        기존 행은 DEFAULT 1 로 채워지는데, 예전엔 게재된 아이템만 저장했으니 그게 맞다."""
        have = {r["name"] for r in self.conn.execute("PRAGMA table_info(items)")}
        for column, ddl in _MIGRATIONS:
            if column not in have:
                self.conn.execute(ddl)

    # ---- seen-store (cross-day dedup) ----
    def recent_seen(self, retention_days: int) -> list[dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        rows = self.conn.execute(
            "SELECT id, title, url, embedding, first_seen FROM seen WHERE first_seen >= ?",
            (cutoff,),
        ).fetchall()
        out = []
        for r in rows:
            emb = np.frombuffer(r["embedding"], dtype=np.float32) if r["embedding"] else None
            out.append({"id": r["id"], "title": r["title"], "url": r["url"], "embedding": emb})
        return out

    def add_seen(self, item_id: str, title: str, url: str, embedding: np.ndarray | None):
        blob = embedding.astype(np.float32).tobytes() if embedding is not None else None
        self.conn.execute(
            "INSERT OR IGNORE INTO seen (id, title, url, embedding, first_seen) VALUES (?,?,?,?,?)",
            (item_id, title, url, blob, _now()),
        )
        self.conn.commit()

    def is_known(self, item_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM seen WHERE id=?", (item_id,)).fetchone() is not None

    def purge_old_seen(self, retention_days: int):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        self.conn.execute("DELETE FROM seen WHERE first_seen < ?", (cutoff,))
        self.conn.commit()

    def counts(self) -> dict[str, int]:
        """테이블별 행 수 — 파괴적 작업 전에 "뭘 잃는지" 보여주는 용도."""
        return {
            t: self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("seen", "items", "digests", "recaps")
        }

    def clear_seen(self) -> int:
        """seen-store 전체 비우기 (지운 행 수 반환). items/digests/recaps 는 그대로 —
        dedup 백엔드를 바꿔서 임베딩을 못 쓰게 됐을 때 아카이브를 잃지 않고 초기화하는 용도."""
        n = self.conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
        self.conn.execute("DELETE FROM seen")
        self.conn.commit()
        return n

    # ---- items + digests ----
    def save_items(self, items: list[dict], digest_date: str,
                   is_published: bool = True, drop_reason: str = ""):
        """아이템 저장. is_published=False 면 탈락분 아카이브 — drop_reason 에 사유를 남긴다
        (컷 튜닝할 때 "뭘 버렸는지" 를 나중에 볼 수 있게). 읽기 API 는 기본적으로 게재분만 반환.
        아이템별 사유가 다르면 사유별로 나눠서 호출할 것."""
        for it in items:
            self.conn.execute(
                """INSERT OR REPLACE INTO items
                   (id, source_id, category, title, url, summary, significance,
                    is_major, published, fetched_at, digest_date, is_published, drop_reason)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    it["id"], it["source_id"], it["category"], it["title"], it["url"],
                    it.get("summary", ""), it.get("significance", 0.0),
                    int(it.get("is_major", False)), it.get("published", ""),
                    _now(), digest_date, int(is_published),
                    "" if is_published else drop_reason,
                ),
            )
        self.conn.commit()

    def record_digest(self, date: str, item_count: int, html_path: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO digests (date, item_count, html_path, created_at) VALUES (?,?,?,?)",
            (date, item_count, html_path, _now()),
        )
        self.conn.commit()

    def list_digests(self) -> list[dict]:
        """아카이브 인덱스용: 각 다이제스트의 최고 significance 항목 제목(top_title)도 함께 반환.
        정렬은 SQL 이 아니라 label_sort_key 로 — 일간/주간 라벨이 한 컬럼에 섞여 있어서
        텍스트 정렬로는 시간순이 안 나옴."""
        rows = self.conn.execute(
            """SELECT d.date, d.item_count, d.html_path,
                      (SELECT title FROM items WHERE digest_date = d.date AND is_published = 1
                       ORDER BY significance DESC LIMIT 1) AS top_title
               FROM digests d"""
        ).fetchall()
        return sorted((dict(r) for r in rows),
                      key=lambda r: label_sort_key(r["date"]), reverse=True)

    def items_for_digest(self, digest_date: str) -> list[dict]:
        """저장된 게재 아이템 재조회 (템플릿 변경 후 재렌더용). 탈락분(is_published=0)은 제외 —
        재렌더가 원본 다이제스트와 달라지면 안 됨. source_name/cluster_sources 는 저장 안 되므로
        호출부에서 source_id -> 소스 이름 매핑을 채워줘야 함(config.py 참고)."""
        rows = self.conn.execute(
            """SELECT id, source_id, category, title, url, summary, significance,
                      is_major, published FROM items
               WHERE digest_date=? AND is_published=1""",
            (digest_date,),
        ).fetchall()
        items = []
        for r in rows:
            it = dict(r)
            it["is_major"] = bool(it["is_major"])
            it["cluster_sources"] = []
            items.append(it)
        return items

    def save_recap(self, digest_date: str, category: str, headline: str = "",
                   one_liner: str = "", stats_json: str = "{}"):
        self.conn.execute(
            """INSERT OR REPLACE INTO recaps (digest_date, category, headline, one_liner, stats_json, created_at)
               VALUES (?,?,?,?,?,?)""",
            (digest_date, category, headline, one_liner, stats_json, _now()),
        )
        self.conn.commit()

    def recaps_for(self, digest_date: str) -> dict:
        """{"": {headline, stats_json}, "model_releases": {one_liner}, ...} 형태로 반환."""
        rows = self.conn.execute(
            "SELECT category, headline, one_liner, stats_json FROM recaps WHERE digest_date=?",
            (digest_date,),
        ).fetchall()
        return {r["category"]: dict(r) for r in rows}

    def all_items(self) -> list[dict]:
        """검색 인덱스용: 게재된 전체 아이템 (최신순). 탈락분은 제외 — 사이트에 없는 글이
        검색 결과에 뜨면 안 됨. source_name 매핑은 호출부 책임(config.py 참고)."""
        rows = self.conn.execute(
            """SELECT id, source_id, category, title, url, summary, significance,
                      is_major, published, digest_date FROM items
               WHERE is_published=1
               ORDER BY published DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    def dropped_items(self, digest_date: str | None = None) -> list[dict]:
        """탈락분 조회 (사유 포함). 카테고리 상한/min_significance 튜닝할 때
        "실제로 뭘 버렸는지" 보려고 — 렌더에는 안 쓰임."""
        sql = """SELECT id, source_id, category, title, url, summary, significance,
                        is_major, published, digest_date, drop_reason FROM items
                 WHERE is_published=0"""
        params: tuple = ()
        if digest_date is not None:
            sql += " AND digest_date=?"
            params = (digest_date,)
        return [dict(r) for r in self.conn.execute(sql + " ORDER BY significance DESC", params)]

    def close(self):
        self.conn.close()
