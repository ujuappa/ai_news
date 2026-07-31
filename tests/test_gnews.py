"""Google News 갭필러 회귀 테스트 (2026-07-31 재활성화분).

고정하는 계약 세 가지:
(1) RFC 822 날짜가 파싱된다 — 못 읽으면 `_apply_cutoff` 를 통과해 7일 컷을 통째로 우회한다.
(2) URL 디코딩 실패 시 **아이템을 버린다** — 불투명 링크가 DB/사이트에 남으면 안 된다.
(3) 디코딩은 신선도 컷 **뒤에** 돈다 — 항목당 ~567KB 라 버릴 기사까지 풀면 낭비."""
import json
from datetime import datetime, timedelta, timezone

import pytest

import fetch
from config import Source

SOURCE = Source(id="gnews_ai", name="Google News",
                feed_url='(AI) site:apnews.com', category="policy_business", parse="gnews")


# ---------------------------------------------------------------- _norm_date

@pytest.mark.parametrize("text,expect_year", [
    ("Thu, 30 Jul 2026 10:01:00 GMT", 2026),      # RFC 822 (GNews)
    ("Wed, 29 Jul 2026 07:00:00 +0000", 2026),
    ("2026-07-30T10:01:00Z", 2026),               # 기존 ISO 경로 회귀
    ("Nov 24, 2025", 2025),                       # 기존 산문 경로 회귀
])
def test_norm_date_parses_supported_formats(text, expect_year):
    iso = fetch._norm_date(text)
    dt = fetch._parse_dt(iso)
    assert dt is not None, f"{text!r} 파싱 실패"
    assert dt.year == expect_year
    assert dt.tzinfo is not None, "naive datetime 은 aware cutoff 와 비교할 때 터진다"


@pytest.mark.parametrize("text", ["", "   ", "not a date", None])
def test_norm_date_returns_empty_on_garbage(text):
    assert fetch._norm_date(text) == ""


def test_rfc822_date_now_survives_the_freshness_cut():
    """이 소스를 껐던 이유의 회귀 가드: 날짜를 못 읽으면 오래된 기사가 컷을 통과한다."""
    old = "Mon, 01 Jan 2024 10:00:00 GMT"
    items = [{"published": fetch._norm_date(old)}]
    assert fetch._apply_cutoff(items, 7) == [], "2024년 기사가 7일 컷을 통과했다"


# ------------------------------------------------------- decode_google_news_url

class _Resp:
    def __init__(self, text="", status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


PAGE_OK = '<c-wiz><div jscontroller="x" data-n-a-sg="SIG123" data-n-a-ts="1700000000">'

# 아래 두 픽스처는 2026-07-31 실제 응답에서 그대로 떠온 형태다(추측 금지 — 처음엔 지어냈다가
# 형식이 달라 테스트가 헛돌았다). 성공 응답엔 길이 프리픽스가 없고, 에러 응답엔 있다.
DECODED_URL = "https://apnews.com/article/real-story"
BATCH_OK = ")]}'\n\n" + json.dumps([
    ["wrb.fr", "Fbv4je", json.dumps(["garturlres", DECODED_URL, 1]), None, None, None, ""],
    ["di", 38],
    ["af.httprm", 37, "-4177262999775668769", 17],
])
BATCH_ERR = (")]}'\n\n96\n"
             '[["wrb.fr","Fbv4je",null,null,null,[3],""],["di",18],'
             '["af.httprm",18,"7338016033765615300",7]]\n25\n[["e",4,null,null,131]]\n')


class _Session:
    def __init__(self, page=PAGE_OK, batch=BATCH_OK, page_status=200):
        self._page, self._batch, self._page_status = page, batch, page_status
        self.gets = self.posts = 0

    def get(self, *a, **k):
        self.gets += 1
        return _Resp(self._page, self._page_status)

    def post(self, *a, **k):
        self.posts += 1
        return _Resp(self._batch)


def test_decode_returns_publisher_url():
    s = _Session()
    got = fetch.decode_google_news_url(
        "https://news.google.com/rss/articles/CBMiABC?oc=5", session=s)
    assert got == DECODED_URL
    assert (s.gets, s.posts) == (1, 1)


def test_decode_returns_empty_when_rpc_errors():
    """Google 이 페이로드 형식을 바꾸면 `[3]` 에러가 온다 — 조용히 ''."""
    assert fetch.decode_google_news_url(
        "https://news.google.com/rss/articles/CBMiABC", session=_Session(batch=BATCH_ERR)) == ""


def test_decode_returns_empty_when_signature_missing():
    assert fetch.decode_google_news_url(
        "https://news.google.com/rss/articles/CBMiABC",
        session=_Session(page="<html>no c-wiz</html>")) == ""


def test_decode_returns_empty_for_non_gnews_url():
    s = _Session()
    assert fetch.decode_google_news_url("https://apnews.com/article/x", session=s) == ""
    assert s.gets == 0, "GNews URL 이 아니면 네트워크를 아예 안 타야 한다"


def test_decode_survives_network_error():
    class _Boom:
        def get(self, *a, **k):
            raise RuntimeError("reset")
    assert fetch.decode_google_news_url(
        "https://news.google.com/rss/articles/CBMiABC", session=_Boom()) == ""


# ------------------------------------------------------------ fetch_gnews_source

def _feed(entries):
    """feedparser 결과를 흉내내는 최소 객체."""
    class _E(dict):
        __getattr__ = dict.get
    class _F:
        pass
    f = _F()
    f.entries = [_E(e) for e in entries]
    return f


def _entry(title, link, when_days_ago, publisher="AP News"):
    dt = datetime.now(timezone.utc) - timedelta(days=when_days_ago)
    return {
        "title": f"{title} - {publisher}",
        "link": link,
        "summary": "snippet",
        "source": {"title": publisher},
        "published_parsed": dt.utctimetuple(),
    }


def _patch(monkeypatch, entries, decoder):
    monkeypatch.setattr(fetch, "_parse_feed", lambda url: _feed(entries))
    monkeypatch.setattr(fetch, "decode_google_news_url",
                        lambda url, session=None, timeout=20: decoder(url))
    monkeypatch.setattr(fetch.time, "sleep", lambda *_: None)


def test_decoded_url_replaces_link_and_id(monkeypatch):
    _patch(monkeypatch, [_entry("Story", "https://news.google.com/rss/articles/A", 1)],
           lambda u: "https://apnews.com/article/story")
    (item,) = fetch.fetch_gnews_source(SOURCE, max_age_days=7)
    assert item["url"] == "https://apnews.com/article/story"
    assert item["id"] == fetch._hash("https://apnews.com/article/story", "Story")


def test_undecodable_items_are_dropped(monkeypatch):
    _patch(monkeypatch, [
        _entry("Good", "https://news.google.com/rss/articles/A", 1),
        _entry("Bad", "https://news.google.com/rss/articles/B", 1),
    ], lambda u: "https://apnews.com/ok" if u.endswith("A") else "")
    items = fetch.fetch_gnews_source(SOURCE, max_age_days=7)
    assert [it["title"] for it in items] == ["Good"]
    assert not any("news.google.com" in it["url"] for it in items)


def test_publisher_suffix_stripped_from_title(monkeypatch):
    _patch(monkeypatch, [_entry("Anthropic ships Opus 5",
                                "https://news.google.com/rss/articles/A", 1)],
           lambda u: "https://apnews.com/x")
    (item,) = fetch.fetch_gnews_source(SOURCE, max_age_days=7)
    assert item["title"] == "Anthropic ships Opus 5"
    assert item["source_name"] == "Google News (AP News)"


def test_stale_items_never_reach_the_decoder(monkeypatch):
    """디코딩은 컷 뒤에. 항목당 ~567KB 라 버릴 기사까지 풀면 안 된다."""
    calls = []
    _patch(monkeypatch, [
        _entry("Fresh", "https://news.google.com/rss/articles/A", 1),
        _entry("Stale", "https://news.google.com/rss/articles/B", 90),
    ], lambda u: calls.append(u) or "https://apnews.com/x")
    items = fetch.fetch_gnews_source(SOURCE, max_age_days=7)
    assert [it["title"] for it in items] == ["Fresh"]
    assert len(calls) == 1, "만료된 항목까지 디코딩했다"


def test_max_entries_caps_decode_volume(monkeypatch):
    calls = []
    _patch(monkeypatch,
           [_entry(f"S{i}", f"https://news.google.com/rss/articles/{i}", 1) for i in range(20)],
           lambda u: calls.append(u) or "https://apnews.com/x")
    fetch.fetch_gnews_source(SOURCE, max_entries=3, max_age_days=7)
    assert len(calls) == 3


def test_feed_failure_returns_empty(monkeypatch):
    def boom(url):
        raise RuntimeError("503")
    monkeypatch.setattr(fetch, "_parse_feed", boom)
    assert fetch.fetch_gnews_source(SOURCE, max_age_days=7) == []


def test_source_config_is_site_scoped_and_capped():
    import config
    src = next(s for s in config.load().sources if s.id == "gnews_ai")
    assert src.enabled and src.parse == "gnews"
    assert "site:apnews.com" in src.feed_url
    assert src.max_entries == 10, "디코딩 비용 때문에 25 가 아니라 10 이어야 한다"
