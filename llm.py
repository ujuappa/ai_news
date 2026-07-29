"""LLM 강화 단계: 분류 + 요약 + 유의성 랭킹 + major 플래그.

원 프로젝트 스펙을 시스템 프롬프트로 못박고, dedup 된 아이템 배치를
넘겨 JSON 으로 돌려받는다. (dedup 은 코드에서 이미 처리 -> LLM 은 판단만)
"""
from __future__ import annotations

import json
import math
import time

from google import genai
from google.genai import types

import config
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

Prioritize signal over volume: if an item is minor or purely promotional, give it a low
significance. Return ONLY a JSON array, no prose, no markdown fences. Each element:
{"id": "...", "category": "...", "summary": "...", "significance": 0.0, "is_major": false}"""


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


def _parse(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1].lstrip("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])
        raise


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


def _as_float(value, default: float = 0.0) -> float:
    """LLM 이 null/문자열/범위 밖 숫자를 줄 수 있어 방어. 0.0-1.0 로 클램프."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(f):
        return default
    return min(1.0, max(0.0, f))


def _call_batch(client, model: str, chunk: list[dict]) -> list[dict]:
    """배치 하나를 호출 + 파싱. 일시적 실패(레이트리밋/5xx/JSON 깨짐)는 지수 백오프로
    재시도하고, 마지막 시도까지 실패하면 그대로 raise (호출자가 배치 단위로 격리)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=_payload(chunk),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM,
                    max_output_tokens=16000,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),  # 분류/요약은 추론 불필요, thinking 끄면 출력 토큰 잘림 방지
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
            cat = row.get("category")
            if cat in CATEGORY_LABELS:
                it["category"] = cat
            it["summary"] = (row.get("summary") or it.get("summary_raw") or "")[:600]
            it["significance"] = _as_float(row.get("significance"))
            it["is_major"] = bool(row.get("is_major", False))
            it["_enriched"] = True

    # LLM 이 빠뜨렸거나 배치가 죽은 아이템 폴백
    for it in items:
        it.setdefault("summary", it.get("summary_raw", ""))
        it.setdefault("significance", 0.0)
        it.setdefault("is_major", False)
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
    resp = client.models.generate_content(
        model=model or config.MODEL,
        contents=payload,
        config=types.GenerateContentConfig(
            system_instruction=RECAP_SYSTEM,
            max_output_tokens=4000,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
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
