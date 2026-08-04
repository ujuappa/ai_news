"""링크 사후 점검(link rot) 회귀 테스트.

배경(2026-08-04): `www.futunn.com/404` 가 리드 기사로 실렸다. 수집 게이트는 고쳤지만
**이미 실린 글은 나중에 죽는다** → `linkcheck.py` 가 게재분을 다시 찔러 `items.link_status`
를 남기고, 렌더는 죽은 링크의 href 를 뗀다.

이 파일이 지키는 가장 중요한 계약은 **"무엇을 죽었다고 부르지 않는가"** 다.
첫 구현은 "못 받았으면 죽은 링크"였는데, 최근 40건 실측에서 멀쩡한 기사 3건을 잡을 뻔했다:
wsj.com 은 401(페이월), washingtonpost.com 은 ConnectionError(봇 차단). 497건 전수에서는
deepmind.google · apnews.com 이 **제목을 개편**해 title_mismatch 로 떴다 — 전부 살아있는 글이다.
"""
import pytest

import fetch
import linkcheck
import render
from store import DEAD_LINK_STATUSES


def _p(status=200, title="", error=""):
    return fetch.Probe(url="https://example.com/a", title=title, status=status, error=error)


# ── 분류표: 무엇이 '죽은 링크'인가 ────────────────────────────────────────────

@pytest.mark.parametrize("status", [404, 410])
def test_server_saying_it_is_gone_is_dead(status):
    assert linkcheck.classify(_p(status), "Some Article") == "gone"
    assert "gone" in DEAD_LINK_STATUSES


def test_soft_404_is_dead():
    assert linkcheck.classify(_p(200, title="404"), "Alibaba launches a huge model") == "soft_404"
    assert "soft_404" in DEAD_LINK_STATUSES


@pytest.mark.parametrize("status", [401, 402, 403, 429])
def test_paywall_and_botwall_are_not_dead(status):
    """wsj.com 이 401 을 준다. 구독자에겐 멀쩡한 기사다 — 링크를 떼면 안 된다."""
    assert linkcheck.classify(_p(status), "Some Article") == "blocked"
    assert "blocked" not in DEAD_LINK_STATUSES


def test_connection_failure_is_not_dead():
    """washingtonpost.com 은 봇을 막아 ConnectionError 가 난다. 기사는 살아 있다."""
    assert linkcheck.classify(_p(0, error="ConnectionError"), "Some Article") == "unreachable"
    assert "unreachable" not in DEAD_LINK_STATUSES


def test_server_error_is_not_dead():
    assert linkcheck.classify(_p(503), "Some Article") == "http_503"


def test_renamed_headline_is_reported_but_not_dead():
    """실측: deepmind.google 이 게시 후 제목을 갈아끼운다. 링크는 멀쩡하다."""
    status = linkcheck.classify(
        _p(200, title="AI co-clinician: researching the path toward AI-augmented care"),
        "Enabling a new model for healthcare with AI co-clinician")
    assert status == "title_mismatch"
    assert "title_mismatch" not in DEAD_LINK_STATUSES


def test_matching_article_is_ok():
    assert linkcheck.classify(
        _p(200, title="Pentagon exploring AI to monitor inmates’ calls | DefenseScoop"),
        "Pentagon exploring AI to monitor inmates' calls") == "ok"


# ── 렌더: 죽은 링크는 href 가 없다 ────────────────────────────────────────────

def _item(link_status=""):
    return {
        "title": "A real story", "headline": "A real story", "summary": "s",
        "url": "https://example.com/a", "source_id": "openai", "source_name": "OpenAI",
        "category": "model_releases", "significance": 0.5, "is_major": False,
        "digest_date": "2026-08-04", "cluster_size": 1, "cluster_sources": [],
        "thread_parent": None, "link_status": link_status,
    }


@pytest.mark.parametrize("status,expected", [
    ("", False), ("ok", False), ("blocked", False), ("unreachable", False),
    ("title_mismatch", False), ("gone", True), ("soft_404", True),
])
def test_annotate_marks_only_dead_statuses(status, expected):
    it = _item(status)
    render._annotate(it)
    assert it["url_dead"] is expected


def test_missing_link_status_is_treated_as_alive():
    """구 DB/미점검 항목에 link_status 키가 아예 없어도 링크가 사라지면 안 된다."""
    it = _item()
    del it["link_status"]
    render._annotate(it)
    assert it["url_dead"] is False


def _render_home(items, tmp_path):
    groups = [("model_releases", items), ("research", []),
              ("tools_products", []), ("policy_business", [])]
    render.render_digest("2026-08-04", groups, [], tmp_path)
    return (tmp_path / "index.html").read_text(encoding="utf-8")


def test_live_item_keeps_its_link(tmp_path):
    assert 'href="https://example.com/a"' in _render_home([_item("ok")], tmp_path)


def test_dead_item_is_rendered_without_a_link(tmp_path):
    html = _render_home([_item("soft_404")], tmp_path)
    assert 'href="https://example.com/a"' not in html
    assert "A real story" in html          # 글은 남는다 — 링크만 없앤다
    assert "Link no longer available" in html


# ── fetch.probe_url 계약 ──────────────────────────────────────────────────────

class _StreamResp:
    def __init__(self, body, status=200, url="https://example.com/final", headers=None):
        self._body, self.status_code, self.url = body, status, url
        self.headers = headers or {}
        self.encoding = "ISO-8859-1"   # requests 가 charset 없을 때 넣는 기본값

    def iter_content(self, n):
        for i in range(0, len(self._body), n):
            yield self._body[i:i + n]

    def close(self):
        pass


def test_title_is_decoded_as_utf8_when_no_charset_is_declared(monkeypatch):
    """실측: charset 미선언 페이지를 requests 기본값(ISO-8859-1)으로 읽어 'â' 가 나왔다.
    CJK 소프트404 문구도 이 경로로 깨지면 못 잡는다."""
    body = "<title>AI care — DeepMind</title>".encode("utf-8")
    monkeypatch.setattr(fetch.requests, "get", lambda *a, **k: _StreamResp(body))
    assert fetch.probe_url("https://x.test/a").title == "AI care — DeepMind"


def test_declared_charset_is_honoured(monkeypatch):
    body = "<title>Café</title>".encode("iso-8859-1")
    resp = _StreamResp(body, headers={"content-type": "text/html; charset=iso-8859-1"})
    monkeypatch.setattr(fetch.requests, "get", lambda *a, **k: resp)
    assert fetch.probe_url("https://x.test/a").title == "Café"


def test_probe_keeps_the_status_code_on_error(monkeypatch):
    monkeypatch.setattr(fetch.requests, "get",
                        lambda *a, **k: _StreamResp(b"", status=404))
    p = fetch.probe_url("https://x.test/gone")
    assert (p.status, p.ok) == (404, False)


def test_probe_records_the_exception_name(monkeypatch):
    def _boom(*a, **k):
        raise ConnectionError("blocked")
    monkeypatch.setattr(fetch.requests, "get", _boom)
    monkeypatch.setattr(fetch.requests, "head", _boom)
    p = fetch.probe_url("https://x.test/a")
    assert (p.status, p.error) == (0, "ConnectionError")


def test_page_title_handles_attributes_on_the_title_tag(monkeypatch):
    body = b'<html><head><title data-rh="true">Real &amp; Article</title></head>'
    monkeypatch.setattr(fetch.requests, "get", lambda *a, **k: _StreamResp(body))
    assert fetch.probe_url("https://x.test/a").title == "Real & Article"


def test_page_title_stops_reading_after_the_cap(monkeypatch):
    """제목 하나 보려고 거대한 페이지를 통째로 받지 않는다."""
    monkeypatch.setattr(fetch, "TITLE_READ_BYTES", 1024)
    body = b"<html><head>" + b"x" * 50_000 + b"<title>Late</title>"
    monkeypatch.setattr(fetch.requests, "get", lambda *a, **k: _StreamResp(body))
    assert fetch.probe_url("https://x.test/a").title == ""


def test_resolve_article_returns_url_and_title(monkeypatch):
    monkeypatch.setattr(fetch.requests, "get",
                        lambda *a, **k: _StreamResp(b"<title>Real Article</title>"))
    assert fetch.resolve_article("https://x.test/a") == \
        ("https://example.com/final", "Real Article")


def test_resolve_article_rejects_non_http():
    assert fetch.resolve_article("javascript:alert(1)") == ("", "")


def test_resolve_article_drops_unreachable(monkeypatch):
    """grounding 경로는 애매하면 버린다 — 점검 경로(probe_url)와 다른 정책이다."""
    monkeypatch.setattr(fetch.requests, "get", lambda *a, **k: _StreamResp(b"", status=404))
    monkeypatch.setattr(fetch.requests, "head", lambda *a, **k: _StreamResp(b"", status=404))
    assert fetch.resolve_article("https://x.test/gone") == ("", "")


def test_resolve_article_falls_back_to_head_without_a_title(monkeypatch):
    """GET 을 막는 서버. 도달은 확인하되 제목이 없으니 내용 검사는 생략된다."""
    def _boom(*a, **k):
        raise RuntimeError("GET blocked")

    class _Head:
        status_code, url = 200, "https://example.com/final"

    monkeypatch.setattr(fetch.requests, "get", _boom)
    monkeypatch.setattr(fetch.requests, "head", lambda *a, **k: _Head())
    assert fetch.resolve_article("https://x.test/a") == ("https://example.com/final", "")
