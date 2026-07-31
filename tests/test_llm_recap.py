"""`generate_recap` 실패 내성 회귀 테스트.

배경(2026-07-31 사고): 리캡 호출이 모델의 JSON 오타 하나(콤마 누락)로 `JSONDecodeError` 를
그대로 올려 파이프라인 전체가 죽었다. 이 호출은 enrich 가 **다 끝난 뒤**에 오기 때문에,
여기서 터지면 그날 쓴 LLM 비용을 통째로 버리고 렌더까지 못 한다(실제 6분 45초 손실).

고정하는 계약: **리캡은 장식이다. 어떤 이유로 실패하든 예외 대신 빈 리캡을 돌려준다.**"""
import json

import pytest

import llm

ITEMS = [{"title": "Opus 5 ships", "category": "model_releases",
          "significance": 0.9, "summary": "s"}]
GOOD = {"headline": "Opus 5 lands", "dollar_committed": "$65B",
        "category_one_liners": {"model_releases": "A frontier release."}}


class _Resp:
    def __init__(self, text):
        self.text = text


def _patch(monkeypatch, texts, record=None):
    """`texts` 를 순서대로 뱉는 가짜 클라이언트. 문자열 대신 예외를 넣으면 던진다."""
    seq = list(texts)

    class _Models:
        def generate_content(self, **kwargs):
            if record is not None:
                record.append(kwargs)
            nxt = seq.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return _Resp(nxt)

    class _Client:
        models = _Models()

    monkeypatch.setattr(llm.genai, "Client", lambda *a, **k: _Client())
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)


def test_parses_a_well_formed_recap(monkeypatch):
    _patch(monkeypatch, [json.dumps(GOOD)])
    out = llm.generate_recap(ITEMS)
    assert out["headline"] == "Opus 5 lands"
    assert out["dollar_committed"] == "$65B"
    assert out["category_one_liners"]["model_releases"] == "A frontier release."


def test_strips_markdown_fences(monkeypatch):
    _patch(monkeypatch, ["```json\n" + json.dumps(GOOD) + "\n```"])
    assert llm.generate_recap(ITEMS)["headline"] == "Opus 5 lands"


def test_salvages_json_wrapped_in_prose(monkeypatch):
    _patch(monkeypatch, ["Sure, here you go:\n" + json.dumps(GOOD) + "\nHope that helps!"])
    assert llm.generate_recap(ITEMS)["headline"] == "Opus 5 lands"


def test_malformed_json_does_not_raise(monkeypatch):
    """사고 재현: 콤마 누락. 예외 대신 빈 리캡이어야 한다."""
    broken = '{"headline": "x", "category_one_liners": {"a": "1" "b": "2"}}'
    _patch(monkeypatch, [broken, broken, broken, broken, broken])
    out = llm.generate_recap(ITEMS)
    assert out == {"headline": "", "dollar_committed": None, "category_one_liners": {}}


def test_retries_then_succeeds(monkeypatch):
    """한 번 깨져도 다음 시도가 멀쩡하면 리캡을 살린다 — 비용 대비 재시도가 싸다."""
    _patch(monkeypatch, ["not json at all", json.dumps(GOOD)])
    assert llm.generate_recap(ITEMS)["headline"] == "Opus 5 lands"


def test_network_error_does_not_raise(monkeypatch):
    _patch(monkeypatch, [RuntimeError("503")] * 5)
    assert llm.generate_recap(ITEMS) == {"headline": "", "dollar_committed": None,
                                         "category_one_liners": {}}


def test_empty_response_does_not_raise(monkeypatch):
    _patch(monkeypatch, [""] * 5)
    assert llm.generate_recap(ITEMS)["headline"] == ""


@pytest.mark.parametrize("payload", [
    '["a list, not a dict"]',
    '"just a string"',
    "null",
])
def test_non_dict_json_does_not_raise(monkeypatch, payload):
    _patch(monkeypatch, [payload] * 5)
    assert llm.generate_recap(ITEMS) == {"headline": "", "dollar_committed": None,
                                         "category_one_liners": {}}


def test_wrong_typed_one_liners_are_dropped_not_fatal(monkeypatch):
    """헤드라인은 살리고 형식이 깨진 부분만 버린다 — 렌더가 .get() 으로 쓰기 때문."""
    _patch(monkeypatch, [json.dumps({"headline": "ok", "category_one_liners": "oops"})])
    out = llm.generate_recap(ITEMS)
    assert out["headline"] == "ok"
    assert out["category_one_liners"] == {}


def test_no_api_call_when_there_are_no_items(monkeypatch):
    calls = []
    _patch(monkeypatch, [json.dumps(GOOD)], record=calls)
    assert llm.generate_recap([]) == {"headline": "", "dollar_committed": None,
                                      "category_one_liners": {}}
    assert calls == [], "빈 입력에 API 를 부르면 돈만 쓴다"


def test_retry_count_matches_house_convention(monkeypatch):
    calls = []
    _patch(monkeypatch, [RuntimeError("boom")] * llm.MAX_RETRIES, record=calls)
    llm.generate_recap(ITEMS)
    assert len(calls) == llm.MAX_RETRIES
