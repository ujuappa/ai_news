"""LLM 강화 단계: 분류 + 요약 + 유의성 랭킹 + major 플래그.

원 프로젝트 스펙을 시스템 프롬프트로 못박고, dedup 된 아이템 배치를
넘겨 JSON 으로 돌려받는다. (dedup 은 코드에서 이미 처리 -> LLM 은 판단만)
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from google import genai
from google.genai import types

import config
import fetch
from config import CATEGORY_LABELS, MAX_TOPICS_PER_ITEM, TOPIC_ORDER

MAX_RETRIES = 3     # 배치당 총 시도 횟수
BACKOFF_BASE = 2.0  # 재시도 대기: 2s -> 4s

# ── grounding 소스 품질 게이트 ────────────────────────────────────────────────
# 근거(2026-07-31 실측, digest.db): grounding 은 이틀간 10건 중 8건이 게시됐는데
# **07-31 에 게시된 4건이 전부 라운드업/집계 페이지였다** — aiweekly.co/ ·
# buildfastwithai.com/blogs/ai-news-today-july-30-2026 · ai.economictimes.com/ ·
# buttondown.com/ai-tldr/archive/aitldr-daily-digest-july-30-2026/.
# significance 0.7~0.9 를 받아서 하한·캡으로는 안 걸린다(LLM 은 "AI 뉴스 모음"을 중요한
# 뉴스로 읽는다). 그래서 **수집 단계에서 구조로 막는다.**
#
# 다섯 겹으로 막는 이유 — 블록리스트 하나로는 내일 생기는 새 콘텐츠팜을 못 잡는다:
#   1) 맨 도메인(경로 없음)  = 홈페이지/섹션 인덱스. 기사가 아니다. **도메인과 무관하게 항상 유효.**
#   2) 도메인 블록리스트    = 이미 관측된 팜/뉴스레터 플랫폼.
#   3) URL 슬러그 패턴      = 'ai-news-today', 'daily-digest' 류. 새 도메인에도 걸린다.
#   4) soft 404 제목       = 200 을 주는 에러 페이지. URL 만 봐서는 절대 못 잡는다(아래 참고).
#   5) 제목 불일치         = 도착한 페이지가 주장한 기사가 아닌 경우. **리스트 관리가 필요 없다.**
# 실제 설정값은 sources.yaml `settings.grounding` 이고, 아래는 그게 없을 때의 폴백이다
# (직접 호출/테스트 경로). 빈 리스트([])를 넘기면 "필터 끄기"로 동작한다 — None 과 구분됨.
GROUNDING_BLOCKED_DOMAINS = (
    "buildfastwithai.com",   # 2026-07-30·31 양일 통과. "AI news today" 일일 라운드업 팜
    "ainewstoday.com",       # 2026-07-31 (캡에 걸려 우연히 안 실림)
    "aiweekly.co",           # 2026-07-31 게시됨. 뉴스레터 아카이브
    "crescendo.ai",          # 2026-07-31 (하한에 걸려 우연히 안 실림)
    "unrot.co",              # 2026-07-30 리뷰에서 관측된 라운드업
    "buttondown.com",        # 뉴스레터 호스팅 플랫폼 — 원문이 있을 수 없다
)
GROUNDING_BLOCKED_URL_PATTERNS = (
    "ai-news-today", "news-roundup", "daily-digest", "weekly-digest",
    "this-week-in", "ai-news-", "/newsletter/", "/digest/",
)

def _url_domain(url: str) -> str:
    """호스트만 소문자로. `www.` 와 포트는 뗀다."""
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _grounding_reject_reason(url: str,
                             blocked_domains: tuple[str, ...] | list[str],
                             blocked_patterns: tuple[str, ...] | list[str],
                             page_title: str = "",
                             claimed_title: str = "") -> str:
    """grounding URL 을 버릴 이유. 실으면 안 될 이유가 없으면 ''.

    맨 도메인 검사를 **가장 먼저** 두는 이유: 리스트 관리가 필요 없는 유일한 규칙이고,
    07-31 에 실린 4건 중 3건이 여기서 잡힌다.

    `page_title` 은 `fetch.resolve_article` 이 실제로 받아온 도착 페이지의 제목이다.
    안 주면(HEAD 폴백/파싱 실패) 내용 검사는 조용히 생략된다 — 우리 쪽 실패를 이유로
    멀쩡한 기사를 버리지 않는다."""
    parts = urlsplit(url)
    if not _url_domain(url):
        return "invalid"
    if parts.path in ("", "/") and not parts.query:
        # 홈페이지/섹션 인덱스. resolve_article 은 통과시킨다(200 이니까) — 여기서 잡아야 한다.
        return "bare_domain"
    domain = _url_domain(url)
    if any(domain == b or domain.endswith("." + b) for b in blocked_domains):
        return "blocked_domain"
    low = url.lower()
    if any(p in low for p in blocked_patterns):
        return "roundup_pattern"
    # 여기부터는 URL 이 아니라 **실제로 도착한 페이지**를 본다.
    # 판정 자체는 fetch 가 갖고 있다 — linkcheck.py 가 같은 기준을 써야 하므로.
    return fetch.dead_page_reason(page_title, claimed_title)

SYSTEM = """You curate a personal daily AI-news digest. Items are pre-deduplicated.
For EACH item, decide:
1. category — exactly one of: model_releases, research, tools_products, policy_business, community_takes
2. summary — 2-3 sentences, in your own words (do NOT copy the source). PRESERVE key
   numbers verbatim (benchmark scores, parameter counts, dollar amounts, dates).
3. significance — 0.0-1.0, using this rubric (high to low):
   frontier model release > major funding/acquisition > benchmark record or new capability
   > notable policy shift > incremental research > community reaction
4. is_major — true only for a genuine frontier-model release, major funding/acquisition,
   or notable policy shift. Be strict; most items are false.
5. headline — a display title, AT MOST 60 characters. Keep the specific subject (model name,
   company, dollar amount) and PRESERVE numbers verbatim. Drop subtitles after a colon,
   marketing adjectives, and any " - Publisher" suffix. No trailing period.
   Example: "Gemini Robotics ER 2: powering robotics with video understanding, task
   orchestration, and multi-robot collaboration" -> "Gemini Robotics ER 2"

6. topics — 0 to 3 tags describing WHAT THE STORY IS ABOUT (its subject domain). This is a
   DIFFERENT axis from `category`, which says what KIND of event it is. A funding round for an
   AI music startup is category "policy_business" with topic "music".
   Allowed values ONLY (copy exactly, never invent, never translate):
{topics}
   Return [] when none clearly applies — do NOT stretch to fill the list. Most items get 0-2.

Prioritize signal over volume: if an item is minor or purely promotional, give it a low
significance. Return ONLY a JSON array, no prose, no markdown fences. Each element:
{{"id": "...", "category": "...", "summary": "...", "significance": 0.0, "is_major": false,
 "headline": "...", "topics": ["..."]}}"""

# 토픽 설명은 프롬프트에만 쓰는 것이라 config 가 아니라 여기 둔다(config.TOPIC_LABELS 는
# 화면에 나가는 짧은 라벨이고, 모델에는 경계를 알려줄 문장이 필요하다).
_TOPIC_GLOSS = {
    "code": "software engineering, developer tools, programming",
    "money": "funding, valuations, IPOs, acquisitions, stock moves",
    "chips": "semiconductors, GPUs, datacenters, compute infrastructure",
    "government": "regulation, legislation, courts, defense, the public sector",
    "security": "cyberattacks, vulnerabilities, fraud, model misuse",
    "science": "physics, chemistry, biology, mathematics, climate research",
    "health": "medicine, clinical care, drug discovery, patients",
    "art": "image generation, design, visual artists",
    "music": "music generation, audio, voice",
    "video": "video generation, film, animation",
    "robotics": "robots, drones, embodied AI",
    "cars": "autonomous driving, vehicles",
    "education": "schools, students, teaching, training people",
}
SYSTEM = SYSTEM.format(topics="\n".join(
    f"     {key} — {_TOPIC_GLOSS[key]}" for key in TOPIC_ORDER))

# 이미지 카탈로그가 있을 때만 SYSTEM 뒤에 붙는 규칙. 별도 호출이 아니라 **같은 배치에 얹는다** —
# 판정에 필요한 정보(제목/본문)가 이미 프롬프트에 있어서 추가 호출은 순수 낭비다.
# 비용은 배치당 키 목록 ~250 토큰 + 아이템당 출력 ~10 토큰.
_IMAGE_RULES = """

ADDITIONALLY, add one more field to every element:
7. image_key — the brand mark to show beside the story. Rules:
   - Pick the mark of the story's SUBJECT (the company/lab/org the story is ABOUT), not the
     publisher that reported it. A TechCrunch story about OpenAI gets "openai", not
     "techcrunch_ai".
   - Prefer a specific organization over a "generic_" key.
   - If several orgs appear, pick the one the headline is actually about.
   - Use the matching "generic_" key when no specific organization fits.
   - Use null if nothing in the catalog fits. Never invent a key, never translate or reword
     one: copy it EXACTLY as written below.

Catalog (key — what it depicts):
{catalog}

So each element becomes:
{{"id": "...", "category": "...", "summary": "...", "significance": 0.0, "is_major": false,
 "headline": "...", "topics": ["..."], "image_key": "..." or null}}"""


def _system_instruction(image_catalog: dict[str, str] | None) -> str:
    """카탈로그가 비어 있으면(=이미지 미업로드, 백필) 원래 프롬프트 그대로. 규칙을 조건부로 붙이는
    이유: 고를 수 있는 게 없는데 image_key 를 요구하면 모델이 키를 지어낸다."""
    if not image_catalog:
        return SYSTEM
    lines = "\n".join(f"- {key} — {label}" for key, label in sorted(image_catalog.items()))
    return SYSTEM + _IMAGE_RULES.format(catalog=lines)


def _payload(items: list[dict]) -> str:
    slim = [
        {
            "id": it["id"],
            "source": it["source_name"],
            "source_category_hint": it["category"],
            "also_covered_by": it.get("cluster_sources", []),
            "title": it["title"],
            "text": it["summary_raw"],
        }
        for it in items
    ]
    return json.dumps(slim, ensure_ascii=False)


def _parse(text: str):
    """응답 텍스트에서 JSON 을 뽑는다. 반환은 list 또는 dict — 정규화는 `_rows` 담당.

    `raw_decode` 로 앞에서부터 문서를 차례로 읽는 이유: 모델이 배열 하나를 온전히 낸 뒤
    **또 배열을 이어붙이거나** 산문을 덧붙이는 경우가 있다(2026-07-29 백필에서
    gemini-3.1-flash-lite 가 실제로 그랬고 `JSONDecodeError: Extra data` 로 4개 주 32건이 누락).
    예전 폴백은 `find("[")` ~ `rfind("]")` 로 잘라서 배열 둘을 한 덩어리로 만들어 여전히 실패했다.
    문서가 하나면 그대로 반환해 기존 동작(단일 객체 / `{"items": [...]}` 래핑)을 유지한다."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1].lstrip("json").strip()
    decoder = json.JSONDecoder()
    docs: list = []
    first_err: json.JSONDecodeError | None = None
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] not in "[{":  # 다음 문서 시작으로 이동(선행 산문 스킵)
            i += 1
        if i >= n:
            break
        try:
            doc, i = decoder.raw_decode(text, i)
        except json.JSONDecodeError as e:
            if first_err is None:
                first_err = e
            if docs:
                break  # 앞에서 건진 게 있으면 뒤쪽 잡음은 무시
            i += 1     # 아직 없으면 산문 속 괄호였을 수 있으니 계속 훑는다
            continue   # (grounding 응답처럼 JSON 모드를 못 쓰는 경우 앞에 설명이 붙는다)
        docs.append(doc)
    if not docs:
        raise first_err or json.JSONDecodeError("JSON 을 찾지 못함", text, 0)
    if len(docs) == 1:
        return docs[0]
    merged: list = []
    for doc in docs:
        merged.extend(doc if isinstance(doc, list) else [doc])
    return merged


def _rows(text: str) -> list[dict]:
    """_parse 결과를 dict 행 리스트로 정규화. 배열이 아니면(객체 하나만 오거나
    {"items": [...]} 로 한 겹 싸서 오는 경우) 건져내고, 그래도 아니면 ValueError -> 재시도."""
    data = _parse(text)
    if isinstance(data, dict):
        if "id" in data:
            data = [data]  # 배치에 1건이라 객체 하나만 온 경우
        else:
            data = next((v for v in data.values() if isinstance(v, list)), None)
    if not isinstance(data, list):
        raise ValueError("응답이 JSON 배열이 아님")
    return [r for r in data if isinstance(r, dict)]


def _clean_str(value) -> str:
    """LLM 이 준 값을 안전한 문자열로. None/숫자/리스트가 와도 죽지 않게."""
    return value.strip() if isinstance(value, str) else ""


def _as_float(value, default: float = 0.0) -> float:
    """LLM 이 null/문자열/범위 밖 숫자를 줄 수 있어 방어. 0.0-1.0 로 클램프."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(f):
        return default
    return min(1.0, max(0.0, f))


def _clean_headline(value, fallback_title: str, limit: int = 70) -> str:
    """표시용 짧은 제목. 모델이 비우거나 이상한 걸 주면 원제목으로 폴백.

    limit 을 넘기면 단어 경계에서 자른다 — 제목의 42%가 60자를 넘고 최대 150자라
    (2026-07-30 측정) 그대로 두면 .lead-title(최대 62px)에서 레이아웃이 깨진다.
    프롬프트로 60자를 요구하지만 모델이 넘길 때가 있어 저장 전에 여기서 막는다."""
    text = _clean_str(value).rstrip(".")
    if not text:
        return fallback_title
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "\u2026"


def _merge_row(it: dict, row: dict, image_catalog: dict[str, str] | None = None) -> None:
    """모델 응답 한 줄을 아이템에 반영. enrich 의 배치 루프에서 분리해 둔 이유는
    이 병합 규칙이 테스트 가능한 유일한 지점이기 때문(배치 호출은 네트워크가 필요)."""
    cat = row.get("category")
    if cat in CATEGORY_LABELS:
        it["category"] = cat
    it["summary"] = (row.get("summary") or it.get("summary_raw") or "")[:600]
    it["significance"] = _as_float(row.get("significance"))
    it["is_major"] = bool(row.get("is_major", False))
    it["headline"] = _clean_headline(row.get("headline"), it["title"])
    # 카탈로그에 없는 키는 조용히 버린다. 모델은 그럴듯한 키를 지어내고("anthropic_ai"),
    # 그대로 저장하면 렌더가 매번 없는 파일을 찾는다 -> 여기서 걸러 소스/제네릭 폴백으로 보낸다.
    key = _clean_str(row.get("image_key")).lower()
    it["image_key"] = key if key in (image_catalog or {}) else ""
    it["topics"] = clean_topics(row.get("topics"))
    it["_enriched"] = True


def clean_topics(raw) -> list[str]:
    """모델이 준 토픽을 어휘에 맞춰 정리. 모르는 값은 버리고, 중복 제거, 상한까지 자른다.

    image_key 와 같은 이유로 검증한다 — 모델은 그럴듯한 값을 지어내고("ai_safety", "Music"),
    그대로 저장하면 pill 에 없는 토픽이 붙은 아이템이 어떤 필터에도 안 걸린다.
    상한(config.MAX_TOPICS_PER_ITEM)이 없으면 모델이 관대하게 5개씩 달아서
    모든 pill 이 모든 기사를 담고 필터가 아무것도 구분하지 못한다.
    순서는 TOPIC_ORDER 로 정규화한다 — 저장값이 모델의 나열 순서에 흔들리면
    같은 아이템의 data-topics 가 실행마다 달라진다."""
    if not isinstance(raw, list):
        return []
    picked = {t.strip().lower() for t in raw if isinstance(t, str)}
    return [t for t in TOPIC_ORDER if t in picked][:MAX_TOPICS_PER_ITEM]


# 토픽만 매기는 프롬프트(백필용). 요약/랭킹을 다시 시키지 않는 게 요점이다 —
# 아카이브 497건은 이미 요약·significance 가 있고, 그걸 다시 생성하면 비싸질 뿐 아니라
# 과거 다이제스트의 내용이 바뀐다(재렌더가 원본과 달라지면 안 된다).
TOPIC_ONLY_SYSTEM = """You tag AI-news stories by subject domain.

For EACH item return 0 to 3 topics describing WHAT THE STORY IS ABOUT.
Allowed values ONLY (copy exactly, never invent, never translate):
{topics}

Return [] when none clearly applies — do NOT stretch to fill the list. Most items get 0-2.
Return ONLY a JSON array, no prose, no markdown fences. Each element:
{{"id": "...", "topics": ["..."]}}"""


def classify_topics(items: list[dict], batch_size: int = 60,
                    model: str | None = None) -> dict[str, list[str]]:
    """{item_id: [토픽...]}. 실패한 배치는 건너뛴다 — 안 돌아온 id 는 그냥 빠지고,
    호출부는 그걸 '아직 미분류'로 남겨 다음 실행에서 다시 시도한다(재개 가능)."""
    if not items:
        return {}
    client = genai.Client()
    model_name = model or config.MODEL
    system = TOPIC_ONLY_SYSTEM.format(topics="\n".join(
        f"  {key} — {_TOPIC_GLOSS[key]}" for key in TOPIC_ORDER))
    out: dict[str, list[str]] = {}
    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    for n, chunk in enumerate(batches, 1):
        try:
            rows = _call_batch(client, model_name, chunk, system)
        except Exception as e:  # noqa: BLE001
            print(f"      ⚠️ 배치 {n}/{len(batches)} 실패 — {len(chunk)}건 건너뜀 "
                  f"({type(e).__name__}: {e})")
            continue
        for row in rows:
            item_id = row.get("id")
            if item_id:
                out[item_id] = clean_topics(row.get("topics"))
        print(f"      배치 {n}/{len(batches)} 완료 (누적 {len(out)}건)")
    return out


def _thinking_config(model: str) -> types.ThinkingConfig:
    """모델 계열에 맞는 thinking 설정.

    Gemini 3 Pro 계열은 thinking_level 을 쓰고 budget=0 을 거부한다.
    gemini-2.5-flash 는 thinking_level 자체를 거부한다(CI DIGEST_MODEL) — budget=0 으로
    thinking 을 끈다. 3.1-flash-lite(백필)도 budget=0 이 검증된 경로."""
    name = (model or "").lower()
    if "gemini-3" in name and "pro" in name:
        return types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH)
    return types.ThinkingConfig(thinking_budget=0)


def _call_batch(client, model: str, chunk: list[dict], system: str = SYSTEM) -> list[dict]:
    """배치 하나를 호출 + 파싱. 일시적 실패(레이트리밋/5xx/JSON 깨짐)는 지수 백오프로
    재시도하고, 마지막 시도까지 실패하면 그대로 raise (호출자가 배치 단위로 격리)."""
    thinking = _thinking_config(model)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=_payload(chunk),
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=16000,
                    thinking_config=thinking,
                    response_mime_type="application/json",
                ),
            )
            return _rows(resp.text or "")
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            wait = BACKOFF_BASE**attempt
            print(f"      ↻ 재시도 {attempt}/{MAX_RETRIES - 1} ({type(e).__name__}: {e}) — {wait:.0f}s 대기")
            time.sleep(wait)
    raise AssertionError("unreachable")


def enrich(items: list[dict], batch_size: int = 40, model: str | None = None,
           image_catalog: dict[str, str] | None = None) -> list[dict]:
    """items 에 category/summary/significance/is_major/image_key/_enriched 를 채워 반환.
    model 미지정 시 config.MODEL(환경변수 DIGEST_MODEL) 사용 — 백필처럼 다른 모델을 쓰고
    싶을 때만 명시적으로 넘기면 됨.

    `image_catalog` 는 {키: 사람이 읽는 이름}(images.labels()). 넘기지 않으면 이미지 선택
    자체를 요청하지 않는다 -> 기존 호출부(backfill 등)는 프롬프트도 비용도 그대로다.

    배치 하나가 죽어도 나머지는 살린다(실패 배치의 아이템은 `_enriched: False` + 원문 폴백).
    단 전량 실패면 RuntimeError — 조용히 빈 다이제스트를 커밋하고 CI 가 초록불이 되는 걸 막는다."""
    if not items:
        return []
    client = genai.Client()  # .env 의 GEMINI_API_KEY(Developer API) 또는 GOOGLE_GENAI_USE_VERTEXAI 계열(Vertex AI) 로 자동 인증
    by_id = {it["id"]: it for it in items}
    model_name = model or config.MODEL
    system = _system_instruction(image_catalog)

    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
    failed = 0
    for n, chunk in enumerate(batches, 1):
        try:
            rows = _call_batch(client, model_name, chunk, system)
        except Exception as e:
            failed += 1
            print(f"      ⚠️ 배치 {n}/{len(batches)} 포기 — {len(chunk)}건 원문 폴백 ({type(e).__name__}: {e})")
            continue
        for row in rows:
            it = by_id.get(row.get("id"))
            if not it:
                continue
            _merge_row(it, row, image_catalog)

    # LLM 이 빠뜨렸거나 배치가 죽은 아이템 폴백
    for it in items:
        it.setdefault("summary", it.get("summary_raw", ""))
        it.setdefault("significance", 0.0)
        it.setdefault("is_major", False)
        it.setdefault("headline", it["title"])
        it.setdefault("image_key", "")   # 소스 마크 -> 카테고리 제네릭 순으로 폴백된다
        it.setdefault("_enriched", False)

    done = sum(1 for it in items if it["_enriched"])
    if not done:
        raise RuntimeError(
            f"LLM 강화 전량 실패 — {len(batches)}개 배치 전부 실패, {len(items)}건 미처리. "
            "API 키/쿼터/모델명을 확인할 것."
        )
    if done < len(items):
        print(f"      ⚠️ 부분 실패 — {done}/{len(items)}건만 강화됨 (배치 {failed}/{len(batches)} 실패)")
    return items


RECAP_SYSTEM = """You write a short editorial recap for a personal AI-news digest covering one
period (a day or a week). You receive already-curated stories: title, category, significance
(0-1), one-line summary.

Produce:
1. headline — a punchy, specific newspaper-style headline (under 12 words) capturing the single
   most notable theme or story of this period. Prefer a specific product/company/number over
   generic phrasing ("The week Anthropic shipped six models", not "A busy week for AI").
2. dollar_committed — best-effort total of genuine NEW funding/investment/monetary-commitment
   amounts explicitly mentioned across the stories (funding rounds, grants, research
   commitments), as one rounded string like "$260M" or "$1.2B". Do NOT include valuations,
   revenue, or ambiguous figures, and do NOT double-count the same deal mentioned twice. This
   number is shown to the user as a rough approximation — if you are not confident multiple
   distinct genuine commitments exist, or none do, return null. Prefer null over a guess.
3. category_one_liners — for each category present in the input, ONE sentence (under 20 words)
   capturing what is distinctive about THAT category in THIS period specifically, not a generic
   description of the category.

Return ONLY JSON, no prose, no markdown fences:
{"headline": "...", "dollar_committed": "$XXXM" or null, "category_one_liners": {"model_releases": "...", ...}}"""


def _empty_recap() -> dict:
    return {"headline": "", "dollar_committed": None, "category_one_liners": {}}


def generate_recap(items: list[dict], model: str | None = None) -> dict:
    """전체 다이제스트용 편집 헤드라인 + $ 집계(최선 추정) + 카테고리별 한 줄 요약.
    개수 통계(항목 수/최고 significance/카테고리별 개수)는 DB 데이터로 직접 계산하므로 여기 없음.

    **실패해도 예외를 올리지 않는다.** 리캡은 장식이고(없으면 헤드라인·한 줄 요약만 빠진다),
    무엇보다 이 호출은 enrich 가 전부 끝난 **뒤**에 온다. 여기서 터지면 그날 쓴 LLM 비용을
    통째로 버리고 렌더도 못 한다 — 실제로 2026-07-31 실행이 모델의 JSON 오타(콤마 누락) 하나로
    6분 45초치 작업을 날렸다. 그래서 다른 LLM 경로(`_call_batch`/`catch_missed_news`)와 같은
    재시도 + 로그 후 빈 값 반환 계약으로 맞춘다."""
    if not items:
        return _empty_recap()
    client = genai.Client()  # .env 로 자동 인증 (Developer API 키 또는 Vertex AI)
    payload = json.dumps(
        [
            {"title": it["title"], "category": it["category"], "significance": it["significance"],
             "summary": it.get("summary", "")}
            for it in items
        ],
        ensure_ascii=False,
    )
    model_name = model or config.MODEL
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=payload,
                config=types.GenerateContentConfig(
                    system_instruction=RECAP_SYSTEM,
                    max_output_tokens=8000,  # thinking 토큰이 출력 예산에 잡히므로 여유를 둠
                    thinking_config=_thinking_config(model_name),
                    response_mime_type="application/json",
                ),
            )
            text = (resp.text or "").strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1].lstrip("json").strip()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                # 중괄호 구간만 잘라 재시도. 이것도 실패하면 except 로 떨어져 재시도/포기.
                start, end = text.find("{"), text.rfind("}")
                if start == -1 or end == -1:
                    raise
                data = json.loads(text[start : end + 1])
            if not isinstance(data, dict):
                raise ValueError(f"dict 가 아닌 응답: {type(data).__name__}")
            one_liners = data.get("category_one_liners")
            return {
                "headline": _clean_str(data.get("headline")),
                "dollar_committed": data.get("dollar_committed"),
                "category_one_liners": one_liners if isinstance(one_liners, dict) else {},
            }
        except Exception as e:  # noqa: BLE001 — 장식 기능이라 파이프라인을 죽이지 않는다
            if attempt == MAX_RETRIES:
                print(f"      [!] 리캡 생성 실패, 헤드라인 없이 계속: {type(e).__name__}: {e}")
                return _empty_recap()
            time.sleep(BACKOFF_BASE**attempt)
    return _empty_recap()


def catch_missed_news(existing_titles: list[str], model: str | None = None,
                      blocked_domains: list[str] | None = None,
                      blocked_url_patterns: list[str] | None = None) -> list[dict]:
    """Gemini 의 Google Search grounding 으로 우리가 놓친 주요 AI 뉴스를 찾는다.

    `response_mime_type="application/json"` 을 쓰지 않는다 — 툴 사용과 함께 지정하면
    API 가 `400 Tool use with a response mime type: 'application/json' is unsupported` 로 거부한다
    (2026-07-29 확인. 그 전까지 이 함수는 매번 400 을 맞고 조용히 빈 리스트를 반환하고 있었음).
    대신 프롬프트로 JSON 만 요구하고 `_parse` 가 앞뒤 산문/코드펜스를 걷어낸다.

    **소스 품질 게이트**(2026-07-31 추가): 프롬프트로 primary source 를 요구하고,
    그걸 안 지킬 때를 대비해 코드에서 라운드업/맨 도메인을 버린다. 프롬프트만으로는 부족하다 —
    07-31 실행에서 게시된 grounding 4건이 전부 라운드업이었고 significance 0.7~0.9 를 받아서
    하한·캡을 그냥 통과했다. `blocked_*` 를 `None` 으로 두면 모듈 기본값, `[]` 로 주면 필터 없음.

    실패해도 예외를 올리지 않는다 — 보조 경로라 여기서 파이프라인을 죽일 이유가 없다."""
    client = genai.Client()
    doms = GROUNDING_BLOCKED_DOMAINS if blocked_domains is None else blocked_domains
    pats = GROUNDING_BLOCKED_URL_PATTERNS if blocked_url_patterns is None else blocked_url_patterns

    prompt = (
        "Search the web for the top 3 major Artificial Intelligence announcements or news from the last 24 hours. "
        "Do NOT include any of the following stories, as we already have them:\n"
        + "\n".join(f"- {t}" for t in existing_titles) +
        "\n\nSource requirements — these matter as much as the story choice:\n"
        "- Prefer the PRIMARY source: the company or lab's own announcement, the regulator's or "
        "government's own release, the paper itself, or an established news outlet reporting "
        "original reporting.\n"
        "- NEVER return a news roundup, link digest, newsletter, or aggregator page "
        "(anything like 'AI news today', 'daily digest', 'this week in AI'). Those are "
        "collections of other people's reporting, not a story.\n"
        "- Each url must link DIRECTLY to one article. Never a site homepage or a section index.\n"
        "\nReturn ONLY a JSON array of the missed stories — no prose, no markdown fences. Each element:\n"
        '{"title": "...", "url": "...", "summary_raw": "...", '
        '"category": "model_releases" (or research, tools_products, policy_business), "source_name": "..."}'
    )

    data = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(
                model=model or config.MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    temperature=0.3,
                ),
            )
            data = _rows(resp.text or "")
            break
        except Exception as e:  # noqa: BLE001
            # 간헐적으로 빈 응답/산문만 오는 경우가 있어 재시도. 하루 한 번 도는 보조 경로라
            # 조용히 0건이 되면 기능이 죽은 걸 눈치채기 어렵다 -> 실패해도 로그는 남긴다.
            if attempt == MAX_RETRIES:
                print(f"      [!] catch_missed_news 실패: {type(e).__name__}: {e}")
                return []
            time.sleep(BACKOFF_BASE**attempt)

    items, unreachable = [], 0
    rejected: list[tuple[str, str]] = []
    for it in data or []:
        title = _clean_str(it.get("title"))
        raw_url = _clean_str(it.get("url"))
        if not title or not raw_url:
            continue
        # grounding 은 불투명한 리다이렉트 주소를 주거나 URL 자체를 지어내기도 한다.
        # 최종 주소로 풀고, 도달 안 되면 버린다(깨진 링크를 싣느니 빼는 게 낫다).
        url, page_title = fetch.resolve_article(raw_url)
        if not url:
            unreachable += 1
            continue
        # 품질 게이트는 **resolve 뒤**에 본다. grounding 이 주는 raw_url 은 리다이렉트
        # 래퍼일 때가 많아서 도메인/슬러그를 봐도 의미가 없다. 하루 3건이라 요청 낭비도 무의미.
        # 도착 페이지 제목도 같이 넘긴다 — soft 404 는 URL 로는 판정이 불가능하다.
        reason = _grounding_reject_reason(url, doms, pats,
                                          page_title=page_title, claimed_title=title)
        if reason:
            rejected.append((reason, url))
            continue
        cat = it.get("category")
        items.append({
            "id": hashlib.sha1(url.encode("utf-8")).hexdigest()[:16],
            "source_id": "gemini_grounding",
            "source_name": _clean_str(it.get("source_name")) or "Google Search",
            # enrich(_payload) 가 category/summary_raw 를 필수로 읽으므로 기본값을 반드시 채운다
            "category": cat if cat in CATEGORY_LABELS else "tools_products",
            "title": title,
            "url": url,
            "summary_raw": _clean_str(it.get("summary_raw")) or title,
            "published": datetime.now(timezone.utc).isoformat(),
            "cluster_sources": [],
        })
    if unreachable:
        print(f"      [!] grounding URL {unreachable}건 도달 불가(404/환각) — 제외")
    for reason, url in rejected:
        # 조용히 버리지 않는다 — 프롬프트가 안 먹히는지, 블록리스트에 새 팜을 넣어야 하는지는
        # 실행 로그에서만 보인다(grounding 은 drop_reason 이 남는 경로를 안 탄다).
        print(f"      [!] grounding 소스 품질 제외({reason}): {url}")
    return items
