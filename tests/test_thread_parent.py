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


def test_lower_bound_is_inclusive():
    """lo 는 '이상'. 상한과 마찬가지로 실측 코사인을 그대로 lo 로 넘겨서 확인한다."""
    v = _v(0.80)
    exact = float(np.dot(X, v))
    cand = [{"id": "edge", "embedding": v, "digest_date": "2026-W07"}]
    assert dedup.find_thread_parent(X, cand, exact, 0.90)["id"] == "edge"
    # 대조군: lo 를 조금만 올리면 같은 후보가 떨어져야 한다.
    assert dedup.find_thread_parent(X, cand, exact + 1e-6, 0.90) is None


def test_ignores_unrelated_below_lower_bound():
    assert dedup.find_thread_parent(X, [_c("far", 0.40)], 0.75, 0.83) is None


def test_returns_none_without_candidates():
    assert dedup.find_thread_parent(X, [], 0.75, 0.83) is None


def test_skips_candidates_with_no_embedding():
    cands = [{"id": "null", "embedding": None, "digest_date": "2026-W07"}, _c("ok", 0.80)]
    assert dedup.find_thread_parent(X, cands, 0.75, 0.83)["id"] == "ok"


def test_skips_wrong_width_candidates_and_keeps_valid_parent():
    cands = [
        {"id": "corrupt", "embedding": np.array([1.0, 0.0, 0.0]), "digest_date": "2026-W07"},
        _c("ok", 0.80),
    ]
    assert dedup.find_thread_parent(X, cands, 0.75, 0.83)["id"] == "ok"
