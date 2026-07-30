"""실제 digest.db 로 threading 을 검증. DB 나 임베딩이 없으면 skip (CI 는 DB 없이 돈다)."""
import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

import config
import dedup
from store import Store, label_sort_key

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "threading_vectors.npz"
LIVE_DB_PATH = Path(os.environ.get("THREADING_TEST_DB", config.DB_PATH))
PAIRS_IN_BAND = [("Series G -> Series H", "d7d47956", "a3d8c6fa", 0.8286)]
PAIRS_ABOVE_BAND = [("Sonnet 4.5 -> Sonnet 4.6", "1ccc22f7", "45f898f6", 0.8445)]
SAME_DAY = ("7909c613", "06b8d0ad")
SAME_DAY_MEASURED = 0.8238


@pytest.fixture(scope="module")
def snapshot():
    with np.load(FIXTURE_PATH, allow_pickle=False) as data:
        return {
            item_id[:8]: {
                "id": item_id,
                "embedding": embedding,
                "digest_date": digest_date,
                "display_title": title,
            }
            for item_id, embedding, digest_date, title in zip(
                data["ids"], data["embeddings"], data["digest_dates"], data["display_titles"],
                strict=True,
            )
        }


@pytest.fixture(scope="module")
def live():
    if not LIVE_DB_PATH.exists():
        pytest.skip("digest.db 없음")
    store = Store(LIVE_DB_PATH, read_only=True)
    embs = {r["id"]: np.frombuffer(r["embedding"], dtype=np.float32)
            for r in store.conn.execute("SELECT id, embedding FROM item_emb")
            if r["embedding"]}
    if not embs:
        pytest.skip("item_emb 비어 있음 — backfill_embeddings.py 를 먼저 실행할 것")
    meta = {r["id"]: r["digest_date"]
            for r in store.conn.execute("SELECT id, digest_date FROM items")}
    full = {}
    for item_id in meta:
        prefix = item_id[:8]
        if prefix in full:
            store.close()
            pytest.fail(f"id prefix 충돌: {prefix}: {full[prefix]} / {item_id}")
        full[prefix] = item_id
    yield {"embs": embs, "meta": meta,
           "full": full,
           "settings": config.load().settings}
    store.close()


def _snapshot_pair(snapshot, a, b):
    va, vb = snapshot[a]["embedding"], snapshot[b]["embedding"]
    return float(np.dot(va, vb)), snapshot[a]["id"], snapshot[b]["id"]


def _is_retention_expired(digest_date, settings):
    cutoff = date.today() - timedelta(days=settings.embedding_retention_days)
    return date.fromisoformat(label_sort_key(digest_date)) < cutoff


def _live_pair(live, a, b):
    ids = live["full"]
    for short in (a, b):
        if short not in ids:
            pytest.fail(f"id prefix {short} 아이템이 DB 에 없음")
        if ids[short] not in live["embs"]:
            if _is_retention_expired(live["meta"][ids[short]], live["settings"]):
                pytest.skip(
                    f"id prefix {short} 임베딩이 {live['settings'].embedding_retention_days}일 "
                    "보존 기간을 지나 삭제됨 — backfill_embeddings.py 로 현재 창을 다시 채울 것"
                )
            pytest.fail(f"id prefix {short} 아이템의 임베딩이 없음")
    va, vb = live["embs"][ids[a]], live["embs"][ids[b]]
    return float(np.dot(va, vb)), ids[a], ids[b]


@pytest.mark.parametrize("name,a,b,measured", PAIRS_IN_BAND)
def test_in_band_pairs_land_in_the_threading_band(snapshot, name, a, b, measured):
    s = config.load().settings
    sim, _ia, _ib = _snapshot_pair(snapshot, a, b)
    assert abs(sim - measured) < 0.005, (
        f"{name}: cos={sim:.4f} 가 기록된 실측 {measured} 에서 벗어남 — 임베딩 입력이나 "
        f"모델이 바뀌었을 수 있다. 원인을 확인하고 값을 갱신할 것")
    assert s.thread_min_similarity <= sim < s.thread_max_similarity, (
        f"{name}: cos={sim:.4f} 가 [{s.thread_min_similarity}, "
        f"{s.thread_max_similarity}) 밖 (2026-07-30 실측 {measured})")


@pytest.mark.parametrize("name,a,b,measured", PAIRS_IN_BAND)
def test_child_selects_the_parent(live, name, a, b, measured):
    """자식이 '이전 날짜 후보' 전체 중에서 실제로 그 부모를 고르는지.
    구간 안에 있다는 것만으로는 부족하다 — 더 가까운 다른 후보가 있으면 그쪽이 뽑힌다."""
    s = live["settings"]
    _sim, ida, idb = _live_pair(live, a, b)
    store = Store(LIVE_DB_PATH, read_only=True)
    cands = store.embeddings_before(live["meta"][idb])
    got = dedup.find_thread_parent(live["embs"][idb], cands,
                                   s.thread_min_similarity, s.thread_max_similarity)
    store.close()
    assert got is not None and got["id"] == ida, (
        f"{name}: 부모로 {got and got['id']} 를 골랐음 (기대: {ida})")


@pytest.mark.parametrize("name,a,b,measured", PAIRS_ABOVE_BAND)
def test_above_band_pairs_are_not_threaded(snapshot, name, a, b, measured):
    """상한 위 쌍은 '중복'으로 취급되어 연결되지 않는다는 결정을 고정한다.

    사람 눈엔 후속편이라 연결되길 기대하게 되는데, 그러려면 thread_max 를 dedup 임계값
    위로 올려야 하고 그 순간 진짜 중복까지 앞 이야기로 붙는다. 그래서 '연결 안 됨'이
    의도된 동작 — 누가 구간을 넓히면 이 테스트가 깨지면서 결정을 다시 보게 만든다."""
    s = config.load().settings
    sim, _ida, _idb = _snapshot_pair(snapshot, a, b)
    assert abs(sim - measured) < 0.005, (
        f"{name}: cos={sim:.4f} 가 기록된 실측 {measured} 에서 벗어남 — 임베딩 입력이나 "
        f"모델이 바뀌었을 수 있다. 원인을 확인하고 값을 갱신할 것")
    assert sim >= s.thread_max_similarity, (
        f"{name}: cos={sim:.4f} 가 상한 {s.thread_max_similarity} 아래로 내려옴 "
        f"(2026-07-30 실측 {measured}) — 이제 연결 가능하니 결정을 재검토할 것")
def test_same_day_siblings_are_never_linked(snapshot, live):
    """Gemini Robotics 2 / ER 2 는 cos 0.824 로 구간 안이지만 같은 날 다른 모델이다.
    embeddings_before 가 같은 날짜를 빼주므로 후보에조차 안 들어와야 한다."""
    a, b = SAME_DAY
    sim, _snapshot_ida, _snapshot_idb = _snapshot_pair(snapshot, a, b)
    _live_sim, ida, idb = _live_pair(live, a, b)
    assert live["meta"][ida] == live["meta"][idb], "같은 날 항목이어야 이 테스트가 의미 있음"
    s = live["settings"]
    # 이 검증이 없으면 cos 가 밴드 밖으로 내려가도 후보 제외만 통과하는 tautology 가 된다.
    assert s.thread_min_similarity <= sim < s.thread_max_similarity, (
        f"same-day Gemini: cos={sim:.4f} 가 [{s.thread_min_similarity}, "
        f"{s.thread_max_similarity}) 밖")
    assert abs(sim - SAME_DAY_MEASURED) < 0.005, (
        f"same-day Gemini: cos={sim:.4f} 가 기록된 실측 {SAME_DAY_MEASURED} 에서 벗어남 — "
        f"임베딩 입력이나 모델이 바뀌었을 수 있다. 원인을 확인하고 값을 갱신할 것")
    store = Store(LIVE_DB_PATH, read_only=True)
    cand_ids = {c["id"] for c in store.embeddings_before(live["meta"][idb])}
    store.close()
    assert ida not in cand_ids, f"같은 날 항목이 후보에 들어옴 (cos={sim:.4f})"
