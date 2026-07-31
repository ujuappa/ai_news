"""SQLite 저장소: 아이템 히스토리 + cross-day dedup 을 위한 seen-store."""
from __future__ import annotations

import json
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


def is_week_label(label: str) -> bool:
    """주간 라벨('2026-W31')인가. 일간('2026-07-31')이면 False.

    라벨 형식을 아는 곳은 이 모듈 하나여야 한다 — 아카이브 인덱스가 "N weeks of signal" 처럼
    개수를 세는 데 쓴다(주간은 백필 산출물, 일간은 라이브 실행분이라 성격이 다르다)."""
    return bool(_WEEK_LABEL_RE.match(label or ""))

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id           TEXT PRIMARY KEY,   -- url 해시
    source_id    TEXT,
    category     TEXT,
    title        TEXT,
    headline     TEXT DEFAULT '',    -- 표시용 짧은 제목 (LLM 생성). 비면 title 로 폴백
    url          TEXT,
    summary      TEXT,               -- LLM 요약 (없으면 원문 발췌)
    significance REAL DEFAULT 0,
    is_major     INTEGER DEFAULT 0,
    published    TEXT,               -- 기사 발행일(ISO). 게재 여부가 아님 — 그건 is_published
    fetched_at   TEXT,
    digest_date  TEXT,               -- 어느 날짜 다이제스트에 실렸는지
    is_published INTEGER DEFAULT 1,  -- 1=다이제스트에 실림, 0=수집했지만 탈락
    drop_reason  TEXT DEFAULT '',    -- is_published=0 일 때의 사유 (min_significance 등)
    cluster_sources TEXT DEFAULT '[]',  -- 같은 스토리를 함께 다룬 소스 이름 (JSON 배열)
    cluster_size    INTEGER DEFAULT 1,  -- 클러스터 크기(대표 1 + 병합된 N)
    thread_parent_id TEXT DEFAULT ''    -- 같은 스토리의 '앞 이야기' items.id (없으면 '')
);

CREATE TABLE IF NOT EXISTS seen (
    id         TEXT PRIMARY KEY,     -- url 해시
    title      TEXT,
    url        TEXT,
    embedding  BLOB,                 -- float32 벡터
    first_seen TEXT
);

CREATE TABLE IF NOT EXISTS item_emb (
    id          TEXT PRIMARY KEY,   -- items.id 와 동일
    embedding   BLOB,               -- float32 벡터
    digest_date TEXT                -- 일간 'YYYY-MM-DD' 또는 주간 'YYYY-Www'
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
    ("headline", "ALTER TABLE items ADD COLUMN headline TEXT DEFAULT ''"),
    ("cluster_sources", "ALTER TABLE items ADD COLUMN cluster_sources TEXT DEFAULT '[]'"),
    ("cluster_size", "ALTER TABLE items ADD COLUMN cluster_size INTEGER DEFAULT 1"),
    ("thread_parent_id", "ALTER TABLE items ADD COLUMN thread_parent_id TEXT DEFAULT ''"),
]


class Store:
    def __init__(self, path: Path, read_only: bool = False):
        self.conn = sqlite3.connect(
            f"file:{path.resolve()}?mode=ro" if read_only else path,
            uri=read_only,
        )
        self.conn.row_factory = sqlite3.Row
        if not read_only:
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
            for t in ("seen", "items", "digests", "recaps", "item_emb")
        }

    def unsee(self, ids: list[str]) -> int:
        """seen 에서 제거 (지운 행 수 반환). 같은 날 재실행에서 오전에 실렸던 항목이 오후 고득점에
        밀려 탈락하는 경우가 있는데, 그때 seen 에 남겨두면 캡 드롭인데도 내일 재시도를 못 받는다."""
        if not ids:
            return 0
        cur = self.conn.execute(
            f"DELETE FROM seen WHERE id IN ({','.join('?' * len(ids))})", ids
        )
        self.conn.commit()
        return cur.rowcount

    def clear_seen(self) -> int:
        """seen-store 전체 비우기 (지운 행 수 반환). items/digests/recaps 는 그대로 —
        dedup 백엔드를 바꿔서 임베딩을 못 쓰게 됐을 때 아카이브를 잃지 않고 초기화하는 용도."""
        n = self.conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
        self.conn.execute("DELETE FROM seen")
        self.conn.commit()
        return n

    def clear_embeddings(self) -> int:
        """재생성 가능한 장기 임베딩 전체 비우기 (백엔드 교체 뒤 폭 불일치 방지용)."""
        n = self.conn.execute("SELECT COUNT(*) FROM item_emb").fetchone()[0]
        self.conn.execute("DELETE FROM item_emb")
        self.conn.commit()
        return n

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

    # ---- items + digests ----
    def save_items(self, items: list[dict], digest_date: str,
                   is_published: bool = True, drop_reason: str = ""):
        """아이템 저장. is_published=False 면 탈락분 아카이브 — drop_reason 에 사유를 남긴다
        (컷 튜닝할 때 "뭘 버렸는지" 를 나중에 볼 수 있게). 읽기 API 는 기본적으로 게재분만 반환.
        아이템별 사유가 다르면 사유별로 나눠서 호출할 것."""
        for it in items:
            self.conn.execute(
                """INSERT OR REPLACE INTO items
                   (id, source_id, category, title, headline, url, summary, significance,
                    is_major, published, fetched_at, digest_date, is_published, drop_reason,
                    cluster_sources, cluster_size, thread_parent_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    it["id"], it["source_id"], it["category"], it["title"],
                    it.get("headline", ""), it["url"],
                    it.get("summary", ""), it.get("significance", 0.0),
                    int(it.get("is_major", False)), it.get("published", ""),
                    _now(), digest_date, int(is_published),
                    "" if is_published else drop_reason,
                    json.dumps(it.get("cluster_sources") or [], ensure_ascii=False),
                    int(it.get("cluster_size", 1) or 1),
                    it.get("thread_parent_id") or "",
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
        텍스트 정렬로는 시간순이 안 나옴.

        `top_title` 은 `headline`(LLM 이 만든 60자 이하 표시용 제목)을 우선 쓰고 없으면 원제목으로
        폴백한다 — 렌더의 `display_title` 과 같은 규칙이다(2026-07-31). 아카이브 414건은 headline
        컬럼이 생기기 전 데이터라 폴백을 타고, 그쪽 긴 제목은 CSS 로 2줄에서 자른다(§13 T3.3).
        재엔리치는 유료 배치라 하지 않기로 결정(사용자, 2026-07-31)."""
        rows = self.conn.execute(
            """SELECT d.date, d.item_count, d.html_path,
                      (SELECT COALESCE(NULLIF(headline, ''), title) FROM items
                       WHERE digest_date = d.date AND is_published = 1
                       ORDER BY significance DESC LIMIT 1) AS top_title
               FROM digests d"""
        ).fetchall()
        return sorted((dict(r) for r in rows),
                      key=lambda r: label_sort_key(r["date"]), reverse=True)

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

    def items_for_digest(self, digest_date: str) -> list[dict]:
        """저장된 게재 아이템 재조회 (템플릿 변경 후 재렌더용). 탈락분(is_published=0)은 제외 —
        재렌더가 원본 다이제스트와 달라지면 안 됨. source_name 은 저장하지 않으므로
        호출부에서 source_id -> 소스 이름 매핑을 채워줘야 함(config.py 참고)."""
        rows = self.conn.execute(
            """SELECT id, source_id, category, title, headline, url, summary, significance,
                      is_major, published, cluster_sources, cluster_size, thread_parent_id
               FROM items WHERE digest_date=? AND is_published=1""",
            (digest_date,),
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

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

    def recent_digest_entries(self, limit: int = 20) -> list[dict]:
        """RSS 피드용: 최근 `limit` 개 다이제스트를 최신순으로, 각 다이제스트의 게재 항목까지.

        렌더가 store 를 몰라야 해서(§13 T3.1 이후 render.py 는 데이터 가공만 한다) 여기서
        평평한 dict 로 만들어 준다. 항목은 significance 내림차순 — 피드 본문의 순서가
        사이트의 랭킹과 같아야 한다.

        `headline` 은 recaps 의 편집 헤드라인(없으면 빈 문자열). 리캡 생성이 실패한 날도
        있으므로(2026-07-31 사고) 비어 있는 걸 정상으로 다뤄야 한다."""
        out: list[dict] = []
        for d in self.list_digests()[:limit]:
            label = d["date"]
            items = sorted(self.items_for_digest(label),
                           key=lambda it: it.get("significance") or 0.0, reverse=True)
            whole = self.recaps_for(label).get("", {})
            out.append({
                "label": label,
                "headline": (whole.get("headline") or "").strip(),
                "item_count": d["item_count"],
                "items": items,
            })
        return out

    def all_items(self) -> list[dict]:
        """검색 인덱스용: 게재된 전체 아이템 (최신순). 탈락분은 제외 — 사이트에 없는 글이
        검색 결과에 뜨면 안 됨. source_name 매핑은 호출부 책임(config.py 참고)."""
        rows = self.conn.execute(
            """SELECT id, source_id, category, title, headline, url, summary, significance,
                      is_major, published, digest_date, cluster_sources, cluster_size,
                      thread_parent_id FROM items
               WHERE is_published=1
               ORDER BY published DESC"""
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def dropped_items(self, digest_date: str | None = None) -> list[dict]:
        """탈락분 조회 (사유 포함). 카테고리 상한/min_significance 튜닝할 때
        "실제로 뭘 버렸는지" 보려고 — 렌더에는 안 쓰임."""
        sql = """SELECT id, source_id, category, title, headline, url, summary, significance,
                        is_major, published, digest_date, drop_reason,
                        cluster_sources, cluster_size, thread_parent_id FROM items
                 WHERE is_published=0"""
        params: tuple = ()
        if digest_date is not None:
            sql += " AND digest_date=?"
            params = (digest_date,)
        return [self._row_to_item(r)
                for r in self.conn.execute(sql + " ORDER BY significance DESC", params)]

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

    def close(self):
        self.conn.close()
