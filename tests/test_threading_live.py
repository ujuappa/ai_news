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
SAME_DAY_MEASURED = 0.8238


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


def _pair(live, a, b):
    ids = live["full"]
    for short in (a, b):
        if short not in ids:
            pytest.fail(f"id prefix {short} 아이템이 DB 에 없음")
        if ids[short] not in live["embs"]:
            pytest.fail(f"id prefix {short} 아이템의 임베딩이 없음")
    va, vb = live["embs"][ids[a]], live["embs"][ids[b]]
    return float(np.dot(va, vb)), ids[a], ids[b]


@pytest.mark.parametrize("name,a,b,measured", PAIRS_IN_BAND)
def test_in_band_pairs_land_in_the_threading_band(live, name, a, b, measured):
    s = live["settings"]
    sim, _ia, _ib = _pair(live, a, b)
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
    assert abs(sim - measured) < 0.005, (
        f"{name}: cos={sim:.4f} 가 기록된 실측 {measured} 에서 벗어남 — 임베딩 입력이나 "
        f"모델이 바뀌었을 수 있다. 원인을 확인하고 값을 갱신할 것")
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
    s = live["settings"]
    # 이 검증이 없으면 cos 가 밴드 밖으로 내려가도 후보 제외만 통과하는 tautology 가 된다.
    assert s.thread_min_similarity <= sim < s.thread_max_similarity, (
        f"same-day Gemini: cos={sim:.4f} 가 [{s.thread_min_similarity}, "
        f"{s.thread_max_similarity}) 밖")
    assert abs(sim - SAME_DAY_MEASURED) < 0.005, (
        f"same-day Gemini: cos={sim:.4f} 가 기록된 실측 {SAME_DAY_MEASURED} 에서 벗어남 — "
        f"임베딩 입력이나 모델이 바뀌었을 수 있다. 원인을 확인하고 값을 갱신할 것")
    store = Store(config.DB_PATH)
    cand_ids = {c["id"] for c in store.embeddings_before(live["meta"][idb])}
    store.close()
    assert ida not in cand_ids, f"같은 날 항목이 후보에 들어옴 (cos={sim:.4f})"
