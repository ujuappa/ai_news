"""grounding 소스 품질 게이트 회귀 테스트.

배경(2026-07-31 실측, digest.db): `gemini_grounding` 은 이틀간 후보 10건 중 8건이 게시됐는데
**07-31 에 게시된 4건이 전부 라운드업/집계 페이지**였다. significance 0.7~0.9 를 받아서
카테고리 하한(0.40)·캡(10)으로는 걸리지 않는다 — LLM 이 "AI 뉴스 모음"을 중요한 뉴스로 읽는다.
게다가 3건은 경로가 없는 **맨 도메인**(홈페이지)이라 기사조차 아니었다.

2026-08-04 추가: `www.futunn.com/404` 가 significance 0.8 짜리 리드 기사로 실렸다. futunn 은
없는 기사를 `/404` 로 302 시키고 **그 페이지가 200 을 준다**(soft 404) — 상태코드 게이트도
URL 패턴도 원리적으로 못 잡는다. 그래서 도착 페이지의 <title> 을 같이 본다.

고정하는 계약:
  1. 그날 실제로 실린 4개 URL 은 전부 거부된다(회귀 가드).
  2. 같은 이틀에 정상적으로 실린 URL(nist.gov 등)은 통과한다 — 게이트가 과도하지 않다는 증거.
  3. 맨 도메인 거부는 블록리스트와 무관하게 동작한다(새 콘텐츠팜에도 통하는 유일한 규칙).
  4. 프롬프트에 primary-source 규칙이 들어간다.
  5. 거부는 조용히 일어나지 않는다(로그).
  6. soft 404 와 '주장한 기사가 아닌 페이지'는 제목으로 걸러진다.
  7. 제목을 못 얻었을 때(HEAD 폴백/파싱 실패/CJK 전용)는 내용 검사를 생략한다 — 우리 쪽
     실패를 이유로 멀쩡한 기사를 버리지 않는다.
"""
import pytest

import fetch
import llm

D = llm.GROUNDING_BLOCKED_DOMAINS
P = llm.GROUNDING_BLOCKED_URL_PATTERNS

# 2026-07-31 실행에서 실제로 게시된 4건. 전부 라운드업/맨 도메인이었다.
SHIPPED_JUNK = [
    ("https://aiweekly.co/", "bare_domain"),
    ("https://www.buildfastwithai.com/blogs/ai-news-today-july-30-2026", "blocked_domain"),
    ("https://ai.economictimes.com/", "bare_domain"),
    ("https://buttondown.com/ai-tldr/archive/aitldr-daily-digest-july-30-2026/",
     "blocked_domain"),
]

# 같은 이틀에 들어온 정상 항목. 게이트가 이걸 버리면 grounding 자체가 무의미해진다.
LEGIT = [
    "https://www.nist.gov/news-events/news/2026/07/department-commerce-announces-"
    "letters-intent-7-companies-874-million",
    "https://www.courthousenews.com/eu-lays-out-11-4-billion-for-7-ai-gigafactories-"
    "as-it-aims-to-catch-up-with-us-and-china/",
    "https://siliconangle.com/2026/07/23/databricks-microsoft-expand-azure-"
    "partnership-2030s/",
    "https://openai.com/index/gpt-5-6/",
    "https://www.anthropic.com/news/claude-opus-5",
    "https://arxiv.org/abs/2607.01234",
]


@pytest.mark.parametrize("url,expected", SHIPPED_JUNK)
def test_urls_that_actually_shipped_are_now_rejected(url, expected):
    assert llm._grounding_reject_reason(url, D, P) == expected


@pytest.mark.parametrize("url", LEGIT)
def test_real_articles_pass(url):
    assert llm._grounding_reject_reason(url, D, P) == ""


def test_bare_domain_rejected_without_any_blocklist():
    """맨 도메인 규칙은 리스트 관리가 필요 없어야 한다 — 내일 생기는 팜에도 통해야 하므로."""
    assert llm._grounding_reject_reason("https://brand-new-ai-farm.example/", [], []) \
        == "bare_domain"
    assert llm._grounding_reject_reason("https://example.com", [], []) == "bare_domain"


def test_roundup_slug_rejected_on_unknown_domain():
    """블록리스트에 없는 새 도메인이라도 슬러그로 잡는다."""
    assert llm._grounding_reject_reason(
        "https://unknown-site.example/posts/ai-news-today-august-01-2026", [], P
    ) == "roundup_pattern"


def test_subdomain_of_blocked_domain_is_blocked():
    assert llm._grounding_reject_reason(
        "https://blog.buildfastwithai.com/some-post", D, P) == "blocked_domain"


def test_www_prefix_does_not_evade_blocklist():
    assert llm._grounding_reject_reason("https://www.aiweekly.co/issues/42", D, P) \
        == "blocked_domain"


def test_bare_domain_with_query_is_kept():
    """`?p=123` 류는 경로가 없어도 특정 글을 가리킬 수 있다 — 맨 도메인으로 보지 않는다."""
    assert llm._grounding_reject_reason("https://example.com/?p=12345", [], []) == ""


def test_garbage_url_rejected():
    assert llm._grounding_reject_reason("not-a-url", D, P) == "invalid"


def test_empty_blocklist_disables_domain_filter_but_not_bare_check():
    """`[]` 는 '필터 끄기'로 존중한다(None 과 구분). 단 구조 규칙은 남는다."""
    assert llm._grounding_reject_reason(
        "https://www.buildfastwithai.com/blogs/ai-news-today-july-30-2026", [], []) == ""


# ── 통합: catch_missed_news 가 실제로 걸러내는지 ────────────────────────────────

class _Resp:
    def __init__(self, text):
        self.text = text


def _patch(monkeypatch, payload, record=None, titles=None):
    class _Models:
        def generate_content(self, **kwargs):
            if record is not None:
                record.append(kwargs)
            return _Resp(payload)

    class _Client:
        models = _Models()

    monkeypatch.setattr(llm.genai, "Client", lambda *a, **k: _Client())
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)
    # resolve_article 은 네트워크를 타므로 고정. 기본은 제목 없음 = 내용 검사 생략이라
    # URL 기반 게이트만 본다. `titles` 를 주면 도착 페이지 제목까지 흉내낸다.
    monkeypatch.setattr(llm.fetch, "resolve_article",
                        lambda u, **k: (u, (titles or {}).get(u, "")))


_ROWS = """[
 {"title": "Roundup", "url": "https://aiweekly.co/", "summary_raw": "x",
  "category": "policy_business", "source_name": "AI Weekly"},
 {"title": "Farm", "url": "https://www.buildfastwithai.com/blogs/ai-news-today-july-30-2026",
  "summary_raw": "x", "category": "policy_business", "source_name": "BuildFast"},
 {"title": "Commerce announces $874 million", "url": "https://www.nist.gov/news-events/news/x",
  "summary_raw": "x", "category": "policy_business", "source_name": "NIST"}
]"""


def test_catch_missed_news_keeps_only_the_real_article(monkeypatch):
    _patch(monkeypatch, _ROWS)
    items = llm.catch_missed_news(["existing"])
    assert [it["url"] for it in items] == ["https://www.nist.gov/news-events/news/x"]


def test_rejections_are_logged(monkeypatch, capsys):
    """grounding 은 drop_reason 을 안 남기는 경로라 로그가 유일한 증거다."""
    _patch(monkeypatch, _ROWS)
    llm.catch_missed_news(["existing"])
    out = capsys.readouterr().out
    assert "bare_domain" in out and "blocked_domain" in out
    assert "aiweekly.co" in out


def test_prompt_demands_primary_sources(monkeypatch):
    record = []
    _patch(monkeypatch, "[]", record)
    llm.catch_missed_news(["existing"])
    prompt = record[0]["contents"].lower()
    assert "primary" in prompt
    assert "roundup" in prompt
    assert "homepage" in prompt or "section index" in prompt


def test_explicit_empty_lists_disable_the_domain_filter(monkeypatch):
    """설정으로 필터를 끌 수 있다는 계약. 단 맨 도메인은 여전히 빠진다."""
    _patch(monkeypatch, _ROWS)
    items = llm.catch_missed_news(["e"], blocked_domains=[], blocked_url_patterns=[])
    urls = [it["url"] for it in items]
    assert "https://www.buildfastwithai.com/blogs/ai-news-today-july-30-2026" in urls
    assert "https://aiweekly.co/" not in urls   # 구조 규칙은 안 꺼진다


# ── 도착 페이지 내용 검사(soft 404 / 제목 불일치) ──────────────────────────────
# 실측 근거(2026-08-04, 게시된 grounding 14건 전수 재확인): 정상 8건은 주장 제목과 도착
# 제목이 최소 3토큰 겹쳤고(비율 1.00), 불량 6건은 전부 0토큰이었다.

FUTUNN_CLAIM = ("Performance on par with Anthropic's Fable 5! Alibaba has launched "
                "Qwen3.8-MAX, featuring 2.4 trillion parameters")


def test_soft_404_page_is_rejected_even_though_it_returns_200():
    """실제 사고 재현: futunn 은 죽은 기사를 200 짜리 /404 로 302 시킨다."""
    assert llm._grounding_reject_reason(
        "https://www.futunn.com/404", D, P,
        page_title="404", claimed_title=FUTUNN_CLAIM) == "soft_404"


@pytest.mark.parametrize("title", [
    "404 頁面不存在",
    "Page not found",
    "Error 404 | Example",
    "404 - Oops",
    "页面不存在",
])
def test_soft_404_title_variants(title):
    assert llm._grounding_reject_reason(
        "https://example.com/some/article", [], [],
        page_title=title, claimed_title=FUTUNN_CLAIM) == "soft_404"


def test_landing_page_that_is_not_the_claimed_article_is_rejected():
    """2026-08-02 실제 사고: app.rebrandly.com/broken-links 가 실렸다(제목 'Rebrandly Dashboard')."""
    assert llm._grounding_reject_reason(
        "https://app.rebrandly.com/broken-links", D, P,
        page_title="Rebrandly Dashboard",
        claimed_title="AI Review Deadline Nears as Open-Weight Models Stir Conflict",
    ) == "title_mismatch"


@pytest.mark.parametrize("claim,page", [
    # 같은 이틀에 정상적으로 실린 항목들의 실제 제목 쌍. 하나라도 버리면 과잉 차단이다.
    ("Pentagon exploring AI to monitor military inmates' phone calls",
     "Pentagon exploring AI to monitor military inmates’ phone calls | DefenseScoop"),
    ("Building abundant intelligence", "Building abundant intelligence | OpenAI"),
    ("Databricks and Microsoft expand Azure partnership into the 2030s",
     "Databricks and Microsoft expand Azure partnership into the 2030s - SiliconANGLE"),
    ("Skunk Works® Advances Sensor-Powered AI Fighter Intercept",
     "Skunk Works® Advances Sensor-Powered AI Fighter Intercept - Aug 4, 2026"),
])
def test_real_articles_survive_the_title_check(claim, page):
    assert llm._grounding_reject_reason(
        "https://example.com/2026/08/story", [], [],
        page_title=page, claimed_title=claim) == ""


def test_missing_page_title_skips_the_content_check():
    """HEAD 폴백이나 파싱 실패로 제목이 없을 때 우리 실패를 아이템 탓으로 돌리지 않는다."""
    assert llm._grounding_reject_reason(
        "https://example.com/2026/08/story", [], [],
        page_title="", claimed_title=FUTUNN_CLAIM) == ""


def test_cjk_only_title_is_not_rejected_for_being_cjk():
    """라틴 토큰이 0개면 비교가 불가능하다 — 언어를 이유로 버리지 않는다."""
    assert llm._grounding_reject_reason(
        "https://example.cn/2026/08/story", [], [],
        page_title="人工智能新突破", claimed_title=FUTUNN_CLAIM) == ""


def test_short_claim_title_skips_the_content_check():
    """주장 제목이 너무 짧으면 겹침 판정이 신뢰할 수 없다."""
    assert llm._grounding_reject_reason(
        "https://example.com/2026/08/story", [], [],
        page_title="Rebrandly Dashboard", claimed_title="Gemini 4") == ""


def test_catch_missed_news_drops_the_soft_404(monkeypatch, capsys):
    """통합 회귀: 2026-08-04 에 실제로 실린 아이템이 이제 수집 단계에서 빠진다."""
    payload = ("""[
     {"title": "%s", "url": "https://www.futunn.com/404", "summary_raw": "x",
      "category": "model_releases", "source_name": "\u5bcc\u9014\u8d44\u8baf"},
     {"title": "Commerce announces $874 million to accelerate compute supply chain",
      "url": "https://www.nist.gov/news-events/news/x", "summary_raw": "x",
      "category": "policy_business", "source_name": "NIST"}
    ]""" % FUTUNN_CLAIM)
    _patch(monkeypatch, payload, titles={
        "https://www.futunn.com/404": "404",
        "https://www.nist.gov/news-events/news/x":
            "Department of Commerce Announces Letters of Intent With 7 Companies "
            "for $874 Million to Accelerate Compute Supply Chain",
    })
    items = llm.catch_missed_news(["existing"])
    assert [it["url"] for it in items] == ["https://www.nist.gov/news-events/news/x"]
    assert "soft_404" in capsys.readouterr().out


# `fetch.resolve_article`/`probe_url` 자체의 계약은 tests/test_linkcheck.py 에 있다
# (링크 점검과 같은 코드를 공유하므로 한 군데서 본다).


def test_yaml_settings_reach_the_filter():
    """sources.yaml 의 grounding 블록이 실제로 로드되는지 — 배선 확인."""
    import config
    s = config.load().settings
    assert s.grounding_blocked_domains is not None
    assert "buildfastwithai.com" in s.grounding_blocked_domains
    assert "ai-news-today" in s.grounding_blocked_url_patterns
