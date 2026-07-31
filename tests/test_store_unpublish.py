"""게재 취소(`unpublish`) + 개수 재계산(`recount_digest`) 회귀 테스트.

배경(2026-07-31): grounding 품질 게이트(§13 T2.1)는 **앞으로 들어올 것만** 막아서, 그 전에
저장된 라운드업/홈페이지 URL 5건이 사이트와 RSS 피드에 남아 있었다. 사용자 결정으로 내렸고
(`recheck_grounding_urls.py --apply`), 그 경로를 여기서 고정한다.

고정하는 계약:
  1. 내려도 **행을 지우지 않는다** — `drop_reason` 이 남아야 근거를 볼 수 있다.
  2. 여러 번 돌려도 안전하다(멱등).
  3. 내린 뒤 `digests.item_count` 를 반드시 다시 계산해야 아카이브 인덱스 숫자가 맞는다.
"""
import pytest

from store import Store


def _save(store, id_, label, sig=0.9, published=True):
    store.save_items([{
        "id": id_, "source_id": "gemini_grounding", "category": "model_releases",
        "title": f"title {id_}", "url": f"https://example.com/{id_}", "summary": "s",
        "significance": sig, "is_major": False, "published": "", "headline": f"H {id_}",
    }], label, is_published=published)
    return id_


def test_unpublish_hides_the_item_but_keeps_the_row(tmp_path):
    store = Store(tmp_path / "t.db")
    _save(store, "a", "2026-07-31")
    assert store.unpublish(["a"], "source_quality") == 1
    assert store.items_for_digest("2026-07-31") == []
    dropped = store.dropped_items("2026-07-31")
    assert [d["id"] for d in dropped] == ["a"]
    assert dropped[0]["drop_reason"] == "source_quality"
    store.close()


def test_unpublish_is_idempotent(tmp_path):
    """스크립트를 두 번 돌려도 두 번 세지 않아야 한다."""
    store = Store(tmp_path / "t.db")
    _save(store, "a", "2026-07-31")
    assert store.unpublish(["a"], "source_quality") == 1
    assert store.unpublish(["a"], "source_quality") == 0
    store.close()


def test_unpublish_empty_list_is_a_noop(tmp_path):
    store = Store(tmp_path / "t.db")
    _save(store, "a", "2026-07-31")
    assert store.unpublish([], "source_quality") == 0
    assert len(store.items_for_digest("2026-07-31")) == 1
    store.close()


def test_unpublish_only_touches_the_given_ids(tmp_path):
    store = Store(tmp_path / "t.db")
    _save(store, "keep", "2026-07-31")
    _save(store, "drop", "2026-07-31")
    store.unpublish(["drop"], "source_quality")
    assert [it["id"] for it in store.items_for_digest("2026-07-31")] == ["keep"]
    store.close()


def test_recount_digest_matches_reality_after_unpublish(tmp_path):
    """아카이브 인덱스의 행·막대·푸터 숫자가 digests.item_count 에서 나온다 —
    내리고 재계산을 안 하면 표시가 실제와 어긋난다."""
    store = Store(tmp_path / "t.db")
    _save(store, "a", "2026-07-31")
    _save(store, "b", "2026-07-31")
    _save(store, "c", "2026-07-31")
    store.record_digest("2026-07-31", 3, "archive/2026-07-31.html")
    store.unpublish(["a"], "source_quality")
    assert store.recount_digest("2026-07-31") == 2
    assert {d["date"]: d["item_count"] for d in store.list_digests()}["2026-07-31"] == 2
    store.close()


def test_recount_digest_handles_an_emptied_digest(tmp_path):
    store = Store(tmp_path / "t.db")
    _save(store, "a", "2026-07-31")
    store.record_digest("2026-07-31", 1, "archive/2026-07-31.html")
    store.unpublish(["a"], "source_quality")
    assert store.recount_digest("2026-07-31") == 0
    store.close()


def test_unpublished_items_leave_the_search_index(tmp_path):
    """검색은 all_items() 를 쓴다 — 사이트에 없는 글이 검색에 뜨면 안 된다."""
    store = Store(tmp_path / "t.db")
    _save(store, "a", "2026-07-31")
    _save(store, "b", "2026-07-31")
    store.unpublish(["a"], "source_quality")
    assert [it["id"] for it in store.all_items()] == ["b"]
    store.close()


def test_unpublished_items_leave_the_feed(tmp_path):
    store = Store(tmp_path / "t.db")
    _save(store, "a", "2026-07-31")
    _save(store, "b", "2026-07-31")
    store.record_digest("2026-07-31", 2, "archive/2026-07-31.html")
    store.unpublish(["a"], "source_quality")
    entry = store.recent_digest_entries()[0]
    assert [it["id"] for it in entry["items"]] == ["b"]
    store.close()
