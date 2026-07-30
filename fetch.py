"""RSS/Atom 피드 수집 + 정규화.

공식 RSS 가 없는 소스(no_feed)는 `parse: sitemap` 로 sitemap.xml + 기사 페이지
og:title/og:description 스크레이프로 대체 (fetch_sitemap_source)."""
from __future__ import annotations

import calendar
import hashlib
import html
import re
import time
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

import feedparser
import requests
import trafilatura
from gnews import GNews

from config import Source

_TAG_RE = re.compile(r"<[^>]+>")
_OG_TITLE_RE = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', re.I)
_OG_DESC_RE = re.compile(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']', re.I)
_TITLE_TAG_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
_MAIN_RE = re.compile(r"<main[^>]*>(.*?)</main>", re.I | re.S)
_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.I | re.S)
# 발행일 추출용. sitemap <lastmod> 는 사이트 리빌드 때 갱신되므로 발행일이 아님
# (2026-07-28 확인: Opus 4.5 는 lastmod 2026-07-23 이지만 실제 발행은 2025-11-24 — 8개월 차이).
_LD_PUBLISHED_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
_POST_DETAIL_DATE_RE = re.compile(
    r'PostDetail[^>]*?title"[^>]*>.*?<div[^>]*\bagate\b[^>]*>\s*'
    r'([A-Z][a-z]{2,8}\s+\d{1,2},\s*20\d{2})\s*<',
    re.S,
)
_PROSE_DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y")
_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_UA = {"User-Agent": "Mozilla/5.0 (compatible; ai-digest/1.0)"}
FEED_TIMEOUT = 20        # 초. urllib 기본값(None=무한 대기) 때문에 파이프라인이 멈추던 걸 방지
FEED_RETRIES = 3         # 피드당 총 시도 횟수
FEED_BACKOFF_BASE = 2.0  # 재시도 대기: 2s -> 4s

def _clean(text: str, limit: int = 800) -> str:
    text = _TAG_RE.sub(" ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def extract_full_text(url: str, fallback_snippet: str, limit: int = 3000) -> str:
    """기사 URL 을 받아 trafilatura 로 본문을 뽑아 반환. 실패하면 fallback_snippet 그대로.

    피드 발췌가 잘려 오는 소스(TechCrunch 등)의 요약 품질을 올리는 용도. 기사 1건마다
    HTTP 요청이 붙고(측정 ~0.35s/건) `summary_raw` 가 800 -> 3000자로 커져 LLM 입력 토큰도
    약 3.75배가 되므로, **소스별 `full_text: true` 옵트인 + 신선도 컷 통과분에만** 적용한다
    (`_fill_full_text` 참고). 파이프라인/그라운딩 양쪽에서 쓰므로 공개 이름."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            extracted = trafilatura.extract(downloaded, include_links=False, include_images=False, include_tables=False)
            if extracted:
                return _clean(extracted, limit=limit)
    except Exception as e:  # noqa: BLE001
        print(f"  [!] trafilatura fetch 실패 ({url}): {type(e).__name__}: {e}")
    return fallback_snippet


def _fill_full_text(items: list[dict], enabled: bool) -> None:
    """enabled 면 아이템의 summary_raw 를 본문 추출로 교체(제자리 수정).

    **반드시 신선도 컷/`since` 필터 뒤에 호출할 것.** 앞에서 부르면 곧바로 버릴 항목까지
    긁는다 — 소스 12개 x 25건이면 매 실행 최대 300건을 받아서 대부분 몇 초 뒤 폐기했다."""
    if not enabled:
        return
    for it in items:
        it["summary_raw"] = extract_full_text(it["url"], it["summary_raw"])
        time.sleep(0.15)  # 기사마다 페이지 요청 -> 서버 매너


def _apply_cutoff(items: list[dict], max_age_days: int | None) -> list[dict]:
    """max_age_days 보다 오래된 항목 드롭. 발행일 파싱 실패 항목은 통과시킨다
    (날짜 메타데이터가 없는 소스를 과도하게 걸러내지 않으려는 의도)."""
    if max_age_days is None:
        return items
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    return [it for it in items if (_parse_dt(it["published"]) or cutoff) >= cutoff]


def resolve_url(url: str, timeout: int = 15) -> str:
    """리다이렉트를 끝까지 따라가 최종 URL 을 반환. 도달 불가면 ''.

    grounding(catch_missed_news)용. 두 가지를 동시에 해결한다:
    (1) Gemini 가 `vertexaisearch.cloud.google.com/grounding-api-redirect/...` 같은 불투명한
        리다이렉트 주소를 주는 경우 → 실제 기사 주소로 바꾼다(id 해시도 안정된다),
    (2) 모델이 그럴듯하게 지어낸 URL(404) → 걸러낸다.
    HEAD 를 막는 사이트가 있어 실패 시 GET(stream)으로 한 번 더 시도한다."""
    if not url.startswith("http"):
        return ""
    for use_get in (False, True):
        try:
            if use_get:
                resp = requests.get(url, headers=_UA, allow_redirects=True,
                                    timeout=timeout, stream=True)
                resp.close()
            else:
                resp = requests.head(url, headers=_UA, allow_redirects=True, timeout=timeout)
            if resp.status_code < 400:
                return resp.url
        except Exception:  # noqa: BLE001
            continue
    return ""


def _item_url(entry) -> str:
    # 대부분 entry.link. HF 블로그처럼 <link> 누락 시 guid(id) 로 폴백.
    url = getattr(entry, "link", "") or ""
    if not url:
        gid = getattr(entry, "id", "") or getattr(entry, "guid", "")
        if gid and gid.startswith("http"):
            url = gid
    return url


def _published(entry) -> str:
    """feedparser 의 *_parsed 는 이미 UTC struct_time. time.mktime 은 struct 를 로컬시간으로
    해석하므로 그걸 쓰면 머신의 UTC 오프셋만큼 발행일이 밀린다(로컬 UTC-6 에서 +7h 밀려
    '내일 발행' 항목이 생겼음, CI 는 TZ=UTC 라 안 보였음) -> calendar.timegm 사용."""
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None)
        if val:
            return datetime.fromtimestamp(calendar.timegm(val), tz=timezone.utc).isoformat()
    return ""


def _hash(url: str, title: str) -> str:
    return hashlib.sha1((url or title).encode("utf-8")).hexdigest()[:16]


def _sitemap_news_urls(sitemap_url: str, path_filter: str = "/news/") -> list[tuple[str, str]]:
    """sitemap.xml 에서 path_filter 를 포함하는 URL+lastmod 를 최신순으로 반환 (인덱스 페이지 자체는 제외)."""
    resp = requests.get(sitemap_url, headers=_UA, timeout=15)
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)
    out = []
    for url_el in root.findall("sm:url", _SITEMAP_NS):
        loc = url_el.findtext("sm:loc", default="", namespaces=_SITEMAP_NS)
        lastmod = url_el.findtext("sm:lastmod", default="", namespaces=_SITEMAP_NS)
        if path_filter in loc and not loc.rstrip("/").endswith(path_filter.rstrip("/")):
            out.append((loc, lastmod))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def _first_paragraph(html: str, min_len: int = 40) -> str:
    """<main> 안 첫 실제 문단 텍스트. og:description 이 사이트 공통 문구(boilerplate)인
    페이지가 있어서(예: Anthropic 일부 글) 실제 본문을 우선 시도."""
    m = _MAIN_RE.search(html)
    scope = m.group(1) if m else html
    for p in _P_RE.findall(scope):
        text = _clean(p)
        if len(text) >= min_len:
            return text
    return ""


def _norm_date(text: str) -> str:
    """'Nov 24, 2025' 같은 표기나 ISO 문자열 -> tz-aware ISO(UTC). 실패 시 ''."""
    text = (text or "").strip()
    if not text:
        return ""
    dt = _parse_dt(text)
    if dt is None:
        for fmt in _PROSE_DATE_FORMATS:
            try:
                dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
    return dt.isoformat() if dt else ""


def _article_published(page_html: str) -> str:
    """기사 페이지에서 실제 발행일 추출 (sitemap lastmod 는 리빌드 타임스탬프라 신뢰 불가).
    1) JSON-LD datePublished  2) PostDetail 헤더 바로 밑 날짜 줄. 둘 다 없으면 ''.
    (1)을 먼저 보는 이유: Webflow 계열 페이지는 HTML 맨 앞에 'Last Published' 빌드 시각
    주석이 있어서 '문서의 첫 날짜'를 쓰면 그걸 집어버림."""
    m = _LD_PUBLISHED_RE.search(page_html)
    if m:
        iso = _norm_date(m.group(1))
        if iso:
            return iso
    m = _POST_DETAIL_DATE_RE.search(page_html)
    if m:
        return _norm_date(m.group(1))
    return ""


def _scrape_article_meta(url: str) -> tuple[str, str, str]:
    """공식 RSS 없는 기사 페이지에서 title + 요약 + 발행일 추출.
    요약은 <main> 첫 문단(실제 본문) 우선, 없으면 og:description 폴백.
    발행일은 못 찾으면 '' -> 호출부가 sitemap lastmod 로 폴백."""
    resp = requests.get(url, headers=_UA, timeout=15)
    resp.raise_for_status()
    html = resp.text
    title_m = _OG_TITLE_RE.search(html) or _TITLE_TAG_RE.search(html)
    title = _clean(title_m.group(1), 300) if title_m else ""
    summary = _first_paragraph(html)
    if not summary:
        desc_m = _OG_DESC_RE.search(html)
        summary = _clean(desc_m.group(1)) if desc_m else ""
    published = _article_published(html)
    return title, summary, published


def fetch_sitemap_source(source: Source, max_entries: int = 25,
                          since: str | None = None) -> list[dict]:
    """공식 RSS 없는 소스(status: no_feed)용: sitemap.xml 로 최근 기사 URL 을 찾고
    각 페이지를 스크레이프. `since`(ISO 날짜) 지정 시 그 이후 lastmod 전부 수집(백필용),
    없으면 최신 max_entries 개만."""
    try:
        candidates = _sitemap_news_urls(source.feed_url)
    except Exception as e:  # noqa: BLE001
        print(f"  [!] {source.id} sitemap 실패: {e}")
        return []

    if since:
        candidates = [(u, lm) for u, lm in candidates if lm >= since]
    else:
        candidates = candidates[:max_entries]

    items: list[dict] = []
    for url, lastmod in candidates:
        try:
            title, summary_raw, page_published = _scrape_article_meta(url)
        except Exception as e:  # noqa: BLE001
            print(f"  [!] {source.id} 스크레이프 실패 ({url}): {e}")
            continue
        if not title:
            continue
        # 실제 발행일 우선. 못 찾으면 lastmod 로 폴백하지만 그건 리빌드 시각일 수 있음.
        published = page_published or _norm_date(lastmod)
        items.append(
            {
                "id": _hash(url, title),
                "source_id": source.id,
                "source_name": source.name,
                "category": source.category,
                "title": title,
                "url": url,
                "summary_raw": summary_raw,
                "published": published,
            }
        )
        time.sleep(0.15)  # 기사마다 페이지 요청 -> 서버 매너
    # 본문 추출은 여기서 하지 않는다 — 일간 경로는 fetch_source_counted 가 신선도 컷 뒤에
    # 처리하고, 백필(since 직접 호출)은 스크레이프한 첫 문단으로 충분(6개월치에 본문 추출을
    # 붙이면 수천 건 요청이 된다).
    return items


def _parse_dt(iso: str) -> datetime | None:
    """항상 tz-aware 로 정규화. 타임존 없는 값(sitemap 의 '2026-07-28' 같은 date-only)을
    그대로 돌려주면 신선도 컷오프의 aware cutoff 와 비교할 때 TypeError 로 파이프라인이 죽음."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fetch_paginated_feed(source: Source, since: str, max_pages: int = 30) -> list[dict]:
    """WordPress 계열 피드의 `?paged=N` 페이지네이션으로 since(ISO) 이후 항목을 모두 수집.
    (백필 전용. hnrss/Substack 등 대부분 피드는 `?paged=` 를 지원하지 않으니 WordPress 소스에만 사용)"""
    since_dt = _parse_dt(since)
    sep = "&" if "?" in source.feed_url else "?"
    items: list[dict] = []
    for page in range(1, max_pages + 1):
        url = source.feed_url if page == 1 else f"{source.feed_url}{sep}paged={page}"
        try:
            parsed = _parse_feed(url)  # requests 경유 (타임아웃/SSL/UA — _parse_feed 주석 참고)
        except Exception as e:  # noqa: BLE001
            print(f"  [!] {source.id} page {page} 실패: {type(e).__name__}: {e}")
            break
        if not parsed.entries:
            break

        oldest_on_page: datetime | None = None
        for entry in parsed.entries:
            entry_url = _item_url(entry)
            title = _clean(getattr(entry, "title", ""), 300)
            if not title:
                continue
            published = _published(entry)
            dt = _parse_dt(published)
            if dt and (oldest_on_page is None or dt < oldest_on_page):
                oldest_on_page = dt
            if dt and since_dt and dt < since_dt:
                continue
            items.append(
                {
                    "id": _hash(entry_url, title),
                    "source_id": source.id,
                    "source_name": source.name,
                    "category": source.category,
                    "title": title,
                    "url": entry_url,
                    "summary_raw": _clean(getattr(entry, "summary", "")
                                          or getattr(entry, "description", "")),
                    "published": published,
                }
            )
        if oldest_on_page and since_dt and oldest_on_page < since_dt:
            break
        time.sleep(0.2)
    _fill_full_text(items, source.full_text)  # since 필터를 통과한 것만
    return items


def _parse_feed(feed_url: str):
    """피드를 requests 로 받아서 bytes 를 feedparser 에 넘긴다.

    `feedparser.parse(url)` 에 URL 을 직접 주면 feedparser 가 urllib 으로 받는데, 그러면
      - **타임아웃이 없다**(urllib 기본 소켓 타임아웃 None) → 서버가 연결만 받고 응답을 안 주면
        파이프라인이 무한 대기. CI 에서는 job 한도까지 돌다 죽는다.
      - 파이썬 기본 SSL 컨텍스트를 쓴다 → python.org macOS 설치본은 CA 스토어가 비어 있어
        전 소스가 `CERTIFICATE_VERIFY_FAILED` 로 0건이 된다(2026-07-29 로컬 3.12 전환에서 실제 발생).
      - feedparser 기본 UA(`feedparser/6.0.x ...`)로 나가서 이 파일의 `_UA` 와 어긋난다.
      - HTTP 에러에 예외를 안 던지고 빈 `entries` 를 돌려줘서 403/429 가 "새 글 없음"과 구분이 안 된다.
    requests 는 certifi 를 쓰고 timeout·status_code 를 주므로 네 가지가 한 번에 해결된다.
    일시적 실패(레이트리밋/5xx)는 지수 백오프로 재시도."""
    last: Exception | None = None
    for attempt in range(1, FEED_RETRIES + 1):
        try:
            resp = requests.get(feed_url, headers=_UA, timeout=FEED_TIMEOUT)
            resp.raise_for_status()
            return feedparser.parse(resp.content)
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt == FEED_RETRIES:
                break
            wait = FEED_BACKOFF_BASE**attempt
            print(f"      ↻ {feed_url} 재시도 {attempt}/{FEED_RETRIES - 1} "
                  f"({type(e).__name__}) — {wait:.0f}s 대기")
            time.sleep(wait)
    raise last  # type: ignore[misc]


def fetch_gnews_source(source: Source, max_entries: int = 25, max_age_days: int | None = None) -> list[dict]:
    period = f"{max_age_days}d" if max_age_days else "7d"
    google_news = GNews(period=period, max_results=max_entries)
    try:
        articles = google_news.get_news(source.feed_url)
    except Exception as e:
        print(f"  [!] {source.id} gnews 실패: {type(e).__name__}: {e}")
        return []

    items = []
    for article in articles:
        url = article.get("url", "")
        title = _clean(article.get("title", ""), 300)
        if not title or not url:
            continue

        published_str = article.get("published date", "")
        publisher = article.get("publisher", {}).get("title")
        source_name = f"{source.name} ({publisher})" if publisher else source.name

        items.append({
            "id": _hash(url, title),
            "source_id": source.id,
            "source_name": source_name,
            "category": source.category,
            "title": title,
            "url": url,
            "summary_raw": _clean(article.get("description", "")),
            "published": _norm_date(published_str),
        })
    return items


def fetch_source(source: Source, max_entries: int = 25, max_age_days: int | None = None,
                 full_text: bool | None = None) -> list[dict]:
    """단일 소스 수집(신선도 컷 적용분만). backfill.py 등 개수 통계가 필요 없는 호출부용."""
    fresh, _raw = fetch_source_counted(source, max_entries, max_age_days, full_text)
    return fresh


def fetch_source_counted(source: Source, max_entries: int = 25,
                         max_age_days: int | None = None,
                         full_text: bool | None = None) -> tuple[list[dict], int]:
    """(신선도 컷 통과분, 컷 적용 전 수집 개수) 반환. 실패해도 예외 대신 ([], 0).

    raw 개수를 따로 돌려주는 이유: "피드가 죽었다"(raw==0)와 "저빈도 소스라 이번 주 발행이
    없다"(raw>0, fresh==0)는 완전히 다른 상태인데, 컷 적용 후 개수만 보면 구분이 안 돼서
    월간 발행 소스(Ahead of AI 등)에 가짜 ⚠️ 배지가 붙었다.

    순서가 중요하다: 수집 -> 신선도 컷 -> 본문 추출. 추출을 먼저 하면 버릴 항목까지 긁는다.
    full_text 로 소스 설정을 덮어쓸 수 있다(백필은 False 고정 — max_entries=1000 이라
    켜져 있으면 수천 건을 받는다)."""
    if source.parse == "sitemap":
        items = fetch_sitemap_source(source, max_entries)
    elif source.parse == "gnews":
        items = fetch_gnews_source(source, max_entries, max_age_days)
    else:
        try:
            parsed = _parse_feed(source.feed_url)
        except Exception as e:  # noqa: BLE001
            print(f"  [!] {source.id} fetch 실패: {type(e).__name__}: {e}")
            return [], 0

        items = []
        for entry in parsed.entries[:max_entries]:
            url = _item_url(entry)
            title = _clean(getattr(entry, "title", ""), 300)
            if not title:
                continue
            items.append(
                {
                    "id": _hash(url, title),
                    "source_id": source.id,
                    "source_name": source.name,
                    "category": source.category,
                    "title": title,
                    "url": url,
                    "summary_raw": _clean(getattr(entry, "summary", "")
                                          or getattr(entry, "description", "")),
                    "published": _published(entry),
                }
            )

    raw_count = len(items)
    items = _apply_cutoff(items, max_age_days)
    _fill_full_text(items, source.full_text if full_text is None else full_text)
    return items, raw_count


def fetch_all(sources: list[Source],
              max_age_days: int | None = None) -> tuple[list[dict], dict[str, tuple[int, int]]]:
    """전체 수집. (아이템 목록, {source_id: (fresh, raw)}) 반환.

    fresh = 신선도 컷 통과분, raw = 컷 이전 수집분. source-health 경고는 raw==0 일 때만
    (피드가 죽었거나 파싱 실패). raw>0 · fresh==0 은 저빈도 소스의 정상 상태다."""
    all_items: list[dict] = []
    health: dict[str, tuple[int, int]] = {}
    for src in sources:
        got, raw = fetch_source_counted(src, max_age_days=max_age_days)
        health[src.id] = (len(got), raw)
        aged_out = f"  (피드 {raw}건 중 {raw - len(got)}건 기간 밖)" if raw > len(got) else ""
        print(f"  {src.id:22s} {len(got):3d} items  ({src.status}){aged_out}")
        all_items.extend(got)
    return all_items, health
