"""RSS 피드 (PROJECT_MEMO §13 T3.4 / §5 파킹 항목).

검증 전략: **우리가 뱉은 피드를 `feedparser` 로 다시 읽는다.** feedparser 는 이 프로젝트가
남의 피드를 *소비*할 때 쓰는 라이브러리라(fetch.py), 그걸로 파싱된다는 건 실제 리더에서도
읽힌다는 뜻에 가깝다. 손으로 문자열을 비교하는 것보다 훨씬 강한 보장이다.

고정하는 계약:
  1. well-formed XML 이고 feedparser 가 bozo 없이 읽는다.
  2. **다이제스트 1개 = item 1개** (기사 단위가 아니다).
  3. 링크는 전부 절대 URL. `site_url` 이 없으면 **피드를 만들지 않는다**(깨진 링크 배포 방지).
  4. description 은 이스케이프된 HTML(RSS 규약) — 리더가 마크업으로 렌더할 수 있어야 한다.
  5. 주간 라벨도 시간순이 맞다(월요일 날짜).
"""
import feedparser
import pytest

import render

ENTRIES = [
    {
        "label": "2026-07-31", "headline": "Agents hack real systems", "item_count": 2,
        "items": [
            {"title": "Long original title about Opus", "headline": "Opus 5 ships",
             "url": "https://www.anthropic.com/news/claude-opus-5",
             "summary": "A frontier release with 2x throughput.",
             "category": "model_releases", "is_major": True, "significance": 0.9},
            {"title": "Some paper", "headline": "", "url": "https://arxiv.org/abs/2607.01",
             "summary": "Incremental.", "category": "research",
             "is_major": False, "significance": 0.5},
        ],
    },
    {
        "label": "2026-W31", "headline": "", "item_count": 1,
        "items": [
            {"title": "Weekly backfill item", "headline": "",
             "url": "https://example.com/a?x=1&y=2",
             "summary": 'Quotes " and <angles> & ampersands',
             "category": "policy_business", "is_major": False, "significance": 0.7},
        ],
    },
]
SITE = "https://ujuappa.github.io/ai_news"
FIXED_DATE = "Fri, 31 Jul 2026 12:00:00 +0000"


def _parse(tmp_path, entries=None, site=SITE):
    out = render.render_feed(entries if entries is not None else ENTRIES, tmp_path, site,
                             build_date=FIXED_DATE)
    assert out is not None
    return feedparser.parse(out.read_text(encoding="utf-8")), out


# ── 계약 1: well-formed ───────────────────────────────────────────────────────

def test_feed_parses_without_errors(tmp_path):
    feed, _ = _parse(tmp_path)
    assert not feed.bozo, getattr(feed, "bozo_exception", None)
    assert feed.version.startswith("rss")


def test_special_characters_do_not_break_the_xml(tmp_path):
    """제목/요약에 & " < > 와 CJK 가 들어와도 깨지지 않아야 한다(원문을 그대로 싣는 필드)."""
    entries = [{"label": "2026-07-31", "headline": 'A & B "quoted" <tag> 한글',
                "item_count": 1,
                "items": [{"title": "T & <b>", "headline": "", "url": "https://e.com/?a=1&b=2",
                           "summary": "5 < 6 & 7 > 3", "category": "research",
                           "is_major": False, "significance": 0.5}]}]
    feed, _ = _parse(tmp_path, entries)
    assert not feed.bozo
    assert feed.entries[0].title == 'A & B "quoted" <tag> 한글'


# ── 계약 2: 다이제스트 단위 ───────────────────────────────────────────────────

def test_one_item_per_digest_not_per_story(tmp_path):
    feed, _ = _parse(tmp_path)
    assert len(feed.entries) == 2          # 다이제스트 2개 (기사는 총 3개)


def test_entry_title_uses_recap_headline_and_falls_back_to_label(tmp_path):
    feed, _ = _parse(tmp_path)
    assert feed.entries[0].title == "Agents hack real systems"
    # 리캡 실패한 날은 headline 이 비므로 라벨로 폴백해야 한다(2026-07-31 리캡 크래시 참고)
    assert feed.entries[1].title == "AI Digest — 2026-W31"


def test_every_story_appears_in_the_body_in_ranked_order(tmp_path):
    feed, _ = _parse(tmp_path)
    body = feed.entries[0].summary
    assert "Opus 5 ships" in body and "Some paper" in body
    assert body.index("Opus 5 ships") < body.index("Some paper")


def test_body_uses_headline_but_falls_back_to_title(tmp_path):
    feed, _ = _parse(tmp_path)
    body = feed.entries[0].summary
    assert "Opus 5 ships" in body                          # headline 우선
    assert "Long original title" not in body
    assert "Some paper" in body                            # headline 없으면 원제목


# ── 계약 3: 절대 URL / site_url 없으면 생성 안 함 ─────────────────────────────

def test_all_feed_level_links_are_absolute(tmp_path):
    feed, _ = _parse(tmp_path)
    assert feed.feed.link == f"{SITE}/index.html"
    for e in feed.entries:
        assert e.link.startswith(f"{SITE}/archive/")
    assert feed.entries[0].link == f"{SITE}/archive/2026-07-31.html"


def test_missing_site_url_skips_the_feed_entirely(tmp_path, capsys):
    """상대경로 RSS 는 리더에서 전 링크가 깨진다 — 조용히 깨진 걸 내보내지 않는다."""
    assert render.render_feed(ENTRIES, tmp_path, "") is None
    assert not (tmp_path / "feed.xml").exists()
    assert "site_url" in capsys.readouterr().out


def test_trailing_slash_in_site_url_does_not_double_up(tmp_path):
    feed, _ = _parse(tmp_path, site=SITE + "/")
    assert feed.entries[0].link == f"{SITE}/archive/2026-07-31.html"
    assert "//archive" not in feed.entries[0].link


def test_story_links_point_at_the_original_source(tmp_path):
    feed, _ = _parse(tmp_path)
    assert "https://www.anthropic.com/news/claude-opus-5" in feed.entries[0].summary


# ── 계약 4: description 은 이스케이프된 HTML ──────────────────────────────────

def test_description_is_markup_after_unescaping(tmp_path):
    """RSS 는 description 에 이스케이프된 HTML 을 담는 규약 — feedparser 가 풀면 진짜 태그가 나온다."""
    feed, _ = _parse(tmp_path)
    body = feed.entries[0].summary
    assert "<ol>" in body and "<li>" in body and "<a href=" in body


def test_raw_xml_keeps_the_html_escaped(tmp_path):
    """원문 XML 에는 <ol> 이 그대로 있으면 안 된다(그러면 XML 구조가 깨진다)."""
    _feed, out = _parse(tmp_path)
    raw = out.read_text(encoding="utf-8")
    assert "&lt;ol&gt;" in raw
    assert "<description><ol>" not in raw


# ── 계약 5: 날짜 ──────────────────────────────────────────────────────────────

def test_daily_label_becomes_its_own_date(tmp_path):
    feed, _ = _parse(tmp_path)
    assert feed.entries[0].published_parsed[:3] == (2026, 7, 31)


def test_weekly_label_becomes_that_weeks_monday(tmp_path):
    """일간/주간이 한 피드에 섞여도 리더에서 시간순이 맞아야 한다. 2026-W31 월요일 = 07-27."""
    feed, _ = _parse(tmp_path)
    assert feed.entries[1].published_parsed[:3] == (2026, 7, 27)


def test_unparseable_label_omits_pubdate_instead_of_crashing(tmp_path):
    entries = [{"label": "not-a-date", "headline": "x", "item_count": 0, "items": []}]
    feed, _ = _parse(tmp_path, entries)
    assert not feed.bozo
    assert "published" not in feed.entries[0]


# ── guid ─────────────────────────────────────────────────────────────────────

def test_guids_are_stable_and_unique(tmp_path):
    feed, _ = _parse(tmp_path)
    ids = [e.id for e in feed.entries]
    assert ids == ["ai-digest:2026-07-31", "ai-digest:2026-W31"]
    assert len(set(ids)) == len(ids)


# ── 빈 상태 ──────────────────────────────────────────────────────────────────

def test_empty_digest_list_still_produces_a_valid_feed(tmp_path):
    feed, _ = _parse(tmp_path, [])
    assert not feed.bozo
    assert feed.entries == []
    assert feed.feed.title == "AI Digest"


def test_digest_with_no_items_is_still_an_entry(tmp_path):
    entries = [{"label": "2026-07-31", "headline": "Quiet day", "item_count": 0, "items": []}]
    feed, _ = _parse(tmp_path, entries)
    assert len(feed.entries) == 1
    assert feed.entries[0].title == "Quiet day"


# ── HTML 페이지의 자동 검색 링크 ──────────────────────────────────────────────

ITEM = {
    "title": "T", "headline": "H", "url": "https://e.com/a", "summary": "s",
    "source_id": "openai", "source_name": "OpenAI", "category": "model_releases",
    "significance": 0.9, "is_major": False, "digest_date": "2026-07-31",
    "cluster_size": 1, "cluster_sources": [], "thread_parent": None,
}


def test_pages_advertise_the_feed_at_the_right_depth(tmp_path):
    """리더에 사이트 주소만 붙여넣어도 피드를 찾게 하려면 <link rel=alternate> 가 필요하다."""
    groups = [("model_releases", [dict(ITEM)]), ("research", []),
              ("tools_products", []), ("policy_business", [])]
    render.render_digest("2026-07-31", groups, [], tmp_path, total_records=1)
    render.render_archive_index([{"date": "2026-07-31", "item_count": 1, "top_title": "t"}],
                                tmp_path)
    root = (tmp_path / "index.html").read_text(encoding="utf-8")
    arch = (tmp_path / "archive" / "index.html").read_text(encoding="utf-8")
    assert 'type="application/rss+xml" title="AI Digest" href="feed.xml"' in root
    assert 'type="application/rss+xml" title="AI Digest" href="../feed.xml"' in arch
