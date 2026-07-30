"""중복 제거: (1) 배치 내 클러스터링 (2) seen-store 대비 cross-day 중복 스킵.

임베딩은 sentence-transformers(all-MiniLM-L6-v2) 사용.
가벼운 대안: TfidfVectorizer 로 embed() 만 갈아끼우면 됨 (README 참고).
"""
from __future__ import annotations

import numpy as np

from store import Store

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # lazy import (torch 무거움)
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    vecs = _get_model().encode(texts, normalize_embeddings=True)
    return np.asarray(vecs, dtype=np.float32)


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # 정규화되어 있으므로 내적 = 코사인


def dedup_batch(items: list[dict], threshold: float) -> list[dict]:
    """배치 내에서 유사 아이템을 클러스터로 묶어 대표 1개만 남김.
    대표에는 cluster_sources(중복 커버한 소스들)를 기록."""
    if not items:
        return []
    embs = embed([f"{it['title']}. {it['summary_raw']}" for it in items])
    for it, e in zip(items, embs):
        it["_emb"] = e

    clusters: list[list[dict]] = []
    for it in items:
        placed = False
        for cl in clusters:
            if _cos(it["_emb"], cl[0]["_emb"]) >= threshold:
                cl.append(it)
                placed = True
                break
        if not placed:
            clusters.append([it])

    reps: list[dict] = []
    for cl in clusters:
        rep = cl[0]
        rep["cluster_sources"] = sorted({c["source_name"] for c in cl})
        rep["cluster_size"] = len(cl)
        reps.append(rep)
    return reps


def drop_cross_day(items: list[dict], store: Store, threshold: float,
                   retention_days: int) -> list[dict]:
    """지난 N일 seen-store 와 비교해 이미 다룬 스토리는 제외.
    (v1은 '스킵'만. '새 각도면 업데이트' 로직은 v2 diff 뷰에서 확장)"""
    seen = store.recent_seen(retention_days)
    seen_embs = [s["embedding"] for s in seen if s["embedding"] is not None]

    fresh: list[dict] = []
    for it in items:
        if store.is_known(it["id"]):
            continue  # 동일 URL 재등장
        emb = it["_emb"]
        if any(_cos(emb, se) >= threshold for se in seen_embs):
            continue  # 며칠 전 다룬 스토리와 사실상 동일
        fresh.append(it)
    return fresh


def drop_similar_to(items: list[dict], others: list[dict], threshold: float) -> list[dict]:
    """others 중 하나와 사실상 같은 항목을 제외. 양쪽 다 `_emb` 가 채워져 있어야 한다.

    `drop_cross_day` 가 DB(seen)를 상대한다면 이건 **같은 실행 안의 다른 리스트**를 상대한다.
    grounding 처럼 `dedup_batch` 를 이미 지나간 뒤에 합류하는 아이템을 걸러내는 용도."""
    other_embs = [o["_emb"] for o in others if o.get("_emb") is not None]
    if not other_embs:
        return items
    return [it for it in items
            if not any(_cos(it["_emb"], oe) >= threshold for oe in other_embs)]


def find_thread_parent(emb: np.ndarray, candidates: list[dict],
                       lo: float, hi: float) -> dict | None:
    """`emb` 와 [lo, hi) 유사도 구간에서 가장 가까운 후보 하나. 없으면 None.

    구간의 위를 여는(hi 미만) 게 설계의 핵심이다. hi 이상은 '같은 스토리'라 이어붙일 게
    아니라 dedup 이 합쳐야 하는 값이고, lo 미만은 그냥 남남. 그 사이 —
    "Series G 투자" -> "Series H 투자" 같은 후속편 — 만 링크 대상이다.

    후보를 **이전 날짜로만** 한정하는 책임은 호출부(store.embeddings_before)에 있다.
    여기서 날짜를 안 보는 이유는 이 함수가 순수 벡터 연산이라 테스트가 쉬워지기 때문."""
    best, best_sim = None, -1.0
    for c in candidates:
        ce = c.get("embedding")
        if ce is None:
            continue
        sim = _cos(emb, ce)
        if lo <= sim < hi and sim > best_sim:
            best, best_sim = c, sim
    return best


def commit_seen(items: list[dict], store: Store):
    for it in items:
        store.add_seen(it["id"], it["title"], it["url"], it.get("_emb"))
