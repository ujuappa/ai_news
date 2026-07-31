"""sitemap_paths (소스별 sitemap 경로 필터) 회귀 테스트.

배경: `_sitemap_news_urls` 는 원래 `/news/` 하드코딩이라 Anthropic 의 /research 149건이
안 보였다. 다중 경로로 바꾸면서 (1) 인덱스 페이지 제외가 경로마다 유지되는지,
(2) 설정 안 한 소스가 기존 동작(=뉴스만)을 그대로 쓰는지를 고정한다."""
import config
import fetch

SITEMAP_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://x.test/news</loc><lastmod>2026-07-30</lastmod></url>
  <url><loc>https://x.test/news/opus-5</loc><lastmod>2026-07-25</lastmod></url>
  <url><loc>https://x.test/news/partnership</loc><lastmod>2026-07-28</lastmod></url>
  <url><loc>https://x.test/research</loc><lastmod>2026-07-30</lastmod></url>
  <url><loc>https://x.test/research/drones</loc><lastmod>2026-07-24</lastmod></url>
  <url><loc>https://x.test/engineering/containment</loc><lastmod>2026-06-06</lastmod></url>
  <url><loc>https://x.test/legal/disclosure</loc><lastmod>2026-07-29</lastmod></url>
</urlset>
"""


class _Resp:
    content = SITEMAP_XML

    def raise_for_status(self):
        return None


def _patch(monkeypatch):
    monkeypatch.setattr(fetch.requests, "get", lambda *a, **k: _Resp())


def test_defaults_to_news_only(monkeypatch):
    _patch(monkeypatch)
    urls = [u for u, _ in fetch._sitemap_news_urls("https://x.test/sitemap.xml")]
    assert urls == ["https://x.test/news/partnership", "https://x.test/news/opus-5"]


def test_multiple_paths_are_merged_and_sorted_by_lastmod(monkeypatch):
    _patch(monkeypatch)
    rows = fetch._sitemap_news_urls("https://x.test/sitemap.xml", ["/news/", "/research/"])
    assert [u for u, _ in rows] == [
        "https://x.test/news/partnership",
        "https://x.test/news/opus-5",
        "https://x.test/research/drones",
    ]


def test_index_pages_excluded_for_every_path(monkeypatch):
    """`/news` 와 `/research` 인덱스는 기사가 아니라 목록이라 들어오면 안 된다."""
    _patch(monkeypatch)
    urls = [u for u, _ in fetch._sitemap_news_urls(
        "https://x.test/sitemap.xml", ["/news/", "/research/"])]
    assert "https://x.test/news" not in urls
    assert "https://x.test/research" not in urls


def test_unlisted_paths_are_not_collected(monkeypatch):
    """/engineering 은 발행일이 없어서 의도적으로 제외 — 설정에 없으면 안 잡혀야 한다."""
    _patch(monkeypatch)
    urls = [u for u, _ in fetch._sitemap_news_urls(
        "https://x.test/sitemap.xml", ["/news/", "/research/"])]
    assert not any("/engineering/" in u or "/legal/" in u for u in urls)


def test_anthropic_config_has_news_and_research_only():
    src = next(s for s in config.load().sources if s.id == "anthropic")
    assert src.sitemap_paths == ["/news/", "/research/"]


def test_rss_sources_keep_default_sitemap_paths():
    """sitemap_paths 는 parse: sitemap 전용이지만, 미지정 소스도 기본값을 갖고 있어야
    Source(...) 생성이 깨지지 않는다."""
    src = next(s for s in config.load().sources if s.id == "techcrunch_ai")
    assert src.sitemap_paths == ["/news/"]
