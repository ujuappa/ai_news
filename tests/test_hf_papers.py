"""HF Daily Papers 파서 회귀 테스트.

핵심 설계 두 가지를 고정한다:
(1) 신선도 컷을 **정렬보다 먼저** 적용한다 — 순서가 뒤바뀌면 "17일치 중 최고 인기"가 뽑혀
    오래된 논문이 오늘 자리를 차지한다.
(2) upvote 는 후보 선별에만 쓰고 파이프라인 뒤로 넘기지 않는다(랭킹 rubric 은 고정)."""
from datetime import datetime, timedelta, timezone

import pytest

import fetch
from config import Source


def _iso(days_ago: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _row(pid, title, upvotes, days_ago, summary="abstract text"):
    return {
        "title": title,
        "publishedAt": _iso(days_ago),
        "paper": {"id": pid, "title": title, "summary": summary, "upvotes": upvotes},
    }


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


SOURCE = Source(id="hf_daily_papers", name="Hugging Face Daily Papers",
                feed_url=fetch.HF_PAPERS_API, category="research", parse="hf_papers")


def _patch(monkeypatch, payload):
    monkeypatch.setattr(fetch.requests, "get", lambda *a, **k: _Resp(payload))


def test_maps_api_fields_to_pipeline_item(monkeypatch):
    _patch(monkeypatch, [_row("2607.1", "Metis: Memory Foundation Model", 211, 1)])
    (item,) = fetch.fetch_hf_papers_source(SOURCE, max_age_days=7)
    assert item["title"] == "Metis: Memory Foundation Model"
    assert item["url"] == "https://huggingface.co/papers/2607.1"
    assert item["summary_raw"] == "abstract text"
    assert item["category"] == "research"
    assert item["source_id"] == "hf_daily_papers"
    assert fetch._parse_dt(item["published"]) is not None


def test_sorted_by_upvotes_descending(monkeypatch):
    _patch(monkeypatch, [
        _row("a", "low", 5, 1), _row("b", "high", 229, 2), _row("c", "mid", 90, 1),
    ])
    items = fetch.fetch_hf_papers_source(SOURCE, max_age_days=7)
    assert [it["title"] for it in items] == ["high", "mid", "low"]


def test_freshness_cut_applied_before_upvote_sort(monkeypatch):
    """오래된 초인기 논문이 최근 논문을 밀어내면 안 된다 — 컷이 정렬보다 먼저다."""
    _patch(monkeypatch, [
        _row("old", "viral but stale", 999, 30),
        _row("new", "recent", 10, 1),
    ])
    items = fetch.fetch_hf_papers_source(SOURCE, max_age_days=7)
    assert [it["title"] for it in items] == ["recent"]


def test_max_entries_keeps_the_most_upvoted(monkeypatch):
    _patch(monkeypatch, [_row(str(i), f"p{i}", i, 1) for i in range(10)])
    items = fetch.fetch_hf_papers_source(SOURCE, max_entries=3, max_age_days=7)
    assert [it["_upvotes"] for it in items] == [9, 8, 7]


def test_upvotes_not_persisted_as_public_field(monkeypatch):
    """`_upvotes` 는 정렬용 임시 키. `_emb`/`_enriched` 처럼 밑줄 접두사여야
    save_items 가 무시하고 significance 와도 섞이지 않는다."""
    _patch(monkeypatch, [_row("a", "t", 5, 1)])
    (item,) = fetch.fetch_hf_papers_source(SOURCE, max_age_days=7)
    assert "upvotes" not in item
    assert "significance" not in item
    assert item["_upvotes"] == 5


def test_missing_id_or_title_rows_skipped(monkeypatch):
    _patch(monkeypatch, [
        {"title": "no paper id", "paper": {"summary": "x"}},
        {"paper": {"id": "2607.9", "summary": "x"}},   # 제목 없음
        "not-a-dict",
        _row("2607.1", "good", 1, 1),
    ])
    items = fetch.fetch_hf_papers_source(SOURCE, max_age_days=7)
    assert [it["title"] for it in items] == ["good"]


def test_missing_upvotes_treated_as_zero(monkeypatch):
    _patch(monkeypatch, [
        {"title": "novotes", "publishedAt": _iso(1),
         "paper": {"id": "a", "summary": "x", "upvotes": None}},
        _row("b", "voted", 3, 1),
    ])
    items = fetch.fetch_hf_papers_source(SOURCE, max_age_days=7)
    assert [it["title"] for it in items] == ["voted", "novotes"]
    assert items[1]["_upvotes"] == 0


def test_non_list_response_returns_empty(monkeypatch):
    _patch(monkeypatch, {"error": "nope"})
    assert fetch.fetch_hf_papers_source(SOURCE, max_age_days=7) == []


def test_network_failure_is_absorbed(monkeypatch):
    """소스 하나가 죽어도 파이프라인은 살아야 한다 — 다른 소스와 같은 계약."""
    def boom(*a, **k):
        raise RuntimeError("connection reset")
    monkeypatch.setattr(fetch.requests, "get", boom)
    assert fetch.fetch_hf_papers_source(SOURCE, max_age_days=7) == []


def test_dispatched_by_parse_type(monkeypatch):
    """fetch_source_counted 가 parse: hf_papers 를 새 함수로 보내는지."""
    _patch(monkeypatch, [_row("a", "routed", 7, 1)])
    items, raw = fetch.fetch_source_counted(SOURCE, max_age_days=7)
    assert raw == 1
    assert [it["title"] for it in items] == ["routed"]


@pytest.mark.parametrize("value,expected", [(5, 5), ("7", 7), (None, 0), ("x", 0), (3.9, 3)])
def test_as_int_is_defensive(value, expected):
    assert fetch._as_int(value) == expected
