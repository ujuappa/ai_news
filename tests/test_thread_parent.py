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


def test_ignores_duplicates_at_or_above_upper_bound():
    """0.83 이상은 '중복'이라 이어붙일 게 아니라 dedup 이 합쳤어야 하는 값."""
    assert dedup.find_thread_parent(X, [_c("dup", 0.90)], 0.75, 0.83) is None
    assert dedup.find_thread_parent(X, [_c("edge", 0.83)], 0.75, 0.83) is None


def test_ignores_unrelated_below_lower_bound():
    assert dedup.find_thread_parent(X, [_c("far", 0.40)], 0.75, 0.83) is None


def test_returns_none_without_candidates():
    assert dedup.find_thread_parent(X, [], 0.75, 0.83) is None


def test_skips_candidates_with_no_embedding():
    cands = [{"id": "null", "embedding": None, "digest_date": "2026-W07"}, _c("ok", 0.80)]
    assert dedup.find_thread_parent(X, cands, 0.75, 0.83)["id"] == "ok"
