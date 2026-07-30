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

from google import genai
from google.genai import types

import config
import fetch
from config import CATEGORY_LABELS

MAX_RETRIES = 3     # 배치당 총 시도 횟수
BACKOFF_BASE = 2.0  # 재시도 대기: 2s -> 4s

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

Prioritize signal over volume: if an item is minor or purely promotional, give it a low
significance. Return ONLY a JSON array, no prose, no markdown fences. Each element:
{"id": "...", "category": "...", "summary": "...", "significance": 0.0, "is_major": false,
 "headline": "..."}"""


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


def _merge_row(it: dict, row: dict) -> None:
    """모델 응답 한 줄을 아이템에 반영. enrich 의 배치 루프에서 분리해 둔 이유는
    이 병합 규칙이 테스트 가능한 유일한 지점이기 때문(배치 호출은 네트워크가 필요)."""
    cat = row.get("category")
    if cat in CATEGORY_LABELS:
        it["category"] = cat
    it["summary"] = (row.get("summary") or it.get("summary_raw") or "")[:600]
    it["significance"] = _as_float(row.get("significance"))
    it["is_major"] = bool(row.get("is_major", False))
    it["headline"] = _clean_headline(row.get("headline"), it["title"])
    it["_enriched"] = True


def _thinking_config(model: str) -> types.ThinkingConfig:
    """모델 계열에 맞는 thinking 설정.

    Gemini 3 Pro 계열은 thinking_level 을 쓰고 budget=0 을 거부한다.
    gemini-2.5-flash 는 thinking_level 자체를 거부한다(CI DIGEST_MODEL) — budget=0 으로
    thinking 을 끈다. 3.1-flash-lite(백필)도 budget=0 이 검증된 경로."""
    name = (model or "").lower()
    if "gemini-3" in name and "pro" in name:
        return types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH)
    return types.ThinkingConfig(thinking_budget=0)


def _call_batch(client, model: str, chunk: list[dict]) -> list[dict]:
    """배치 하나를 호출 + 파싱. 일시적 실패(레이트리밋/5xx/JSON 깨짐)는 지수 백오프로
    재시도하고, 마지막 시도까지 실패하면 그대로 raise (호출자가 배치 단위로 격리)."""
    thinking = _thinking_config(model)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=_payload(chunk),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM,
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


def enrich(items: list[dict], batch_size: int = 40, model: str | None = None) -> list[dict]:
    """items 에 category/summary/significance/is_major/_enriched 를 채워 반환.
    model 미지정 시 config.MODEL(환경변수 DIGEST_MODEL) 사용 — 백필처럼 다른 모델을 쓰고
    싶을 때만 명시적으로 넘기면 됨.

    배치 하나가 죽어도 나머지는 살린다(실패 배치의 아이템은 `_enriched: False` + 원문 폴백).
    단 전량 실패면 RuntimeError — 조용히 빈 다이제스트를 커밋하고 CI 가 초록불이 되는 걸 막는다."""
    if not items:
        return []
    client = genai.Client()  # .env 의 GEMINI_API_KEY(Developer API) 또는 GOOGLE_GENAI_USE_VERTEXAI 계열(Vertex AI) 로 자동 인증
    by_id = {it["id"]: it for it in items}
    model_name = model or config.MODEL

    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
    failed = 0
    for n, chunk in enumerate(batches, 1):
        try:
            rows = _call_batch(client, model_name, chunk)
        except Exception as e:
            failed += 1
            print(f"      ⚠️ 배치 {n}/{len(batches)} 포기 — {len(chunk)}건 원문 폴백 ({type(e).__name__}: {e})")
            continue
        for row in rows:
            it = by_id.get(row.get("id"))
            if not it:
                continue
            _merge_row(it, row)

    # LLM 이 빠뜨렸거나 배치가 죽은 아이템 폴백
    for it in items:
        it.setdefault("summary", it.get("summary_raw", ""))
        it.setdefault("significance", 0.0)
        it.setdefault("is_major", False)
        it.setdefault("headline", it["title"])
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


def generate_recap(items: list[dict], model: str | None = None) -> dict:
    """전체 다이제스트용 편집 헤드라인 + $ 집계(최선 추정) + 카테고리별 한 줄 요약.
    개수 통계(항목 수/최고 significance/카테고리별 개수)는 DB 데이터로 직접 계산하므로 여기 없음."""
    if not items:
        return {"headline": "", "dollar_committed": None, "category_one_liners": {}}
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
        start, end = text.find("{"), text.rfind("}")
        data = json.loads(text[start : end + 1]) if start != -1 and end != -1 else {}
    return {
        "headline": data.get("headline", ""),
        "dollar_committed": data.get("dollar_committed"),
        "category_one_liners": data.get("category_one_liners", {}),
    }


def catch_missed_news(existing_titles: list[str], model: str | None = None) -> list[dict]:
    """Gemini 의 Google Search grounding 으로 우리가 놓친 주요 AI 뉴스를 찾는다.

    `response_mime_type="application/json"` 을 쓰지 않는다 — 툴 사용과 함께 지정하면
    API 가 `400 Tool use with a response mime type: 'application/json' is unsupported` 로 거부한다
    (2026-07-29 확인. 그 전까지 이 함수는 매번 400 을 맞고 조용히 빈 리스트를 반환하고 있었음).
    대신 프롬프트로 JSON 만 요구하고 `_parse` 가 앞뒤 산문/코드펜스를 걷어낸다.

    실패해도 예외를 올리지 않는다 — 보조 경로라 여기서 파이프라인을 죽일 이유가 없다."""
    client = genai.Client()

    prompt = (
        "Search the web for the top 3 major Artificial Intelligence announcements or news from the last 24 hours. "
        "Do NOT include any of the following stories, as we already have them:\n"
        + "\n".join(f"- {t}" for t in existing_titles) +
        "\n\nReturn ONLY a JSON array of the missed stories — no prose, no markdown fences. Each element:\n"
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
    for it in data or []:
        title = _clean_str(it.get("title"))
        raw_url = _clean_str(it.get("url"))
        if not title or not raw_url:
            continue
        # grounding 은 불투명한 리다이렉트 주소를 주거나 URL 자체를 지어내기도 한다.
        # 최종 주소로 풀고, 도달 안 되면 버린다(깨진 링크를 싣느니 빼는 게 낫다).
        url = fetch.resolve_url(raw_url)
        if not url:
            unreachable += 1
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
    return items
