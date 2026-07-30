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
