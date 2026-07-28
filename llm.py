"""LLM 강화 단계: 분류 + 요약 + 유의성 랭킹 + major 플래그.

원 프로젝트 스펙을 시스템 프롬프트로 못박고, dedup 된 아이템 배치를
넘겨 JSON 으로 돌려받는다. (dedup 은 코드에서 이미 처리 -> LLM 은 판단만)
"""
from __future__ import annotations

import json

from google import genai
from google.genai import types

import config
from config import CATEGORY_LABELS

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


def enrich(items: list[dict], batch_size: int = 40, model: str | None = None) -> list[dict]:
    """items 에 category/summary/significance/is_major 를 채워 반환.
    model 미지정 시 config.MODEL(환경변수 DIGEST_MODEL) 사용 — 백필처럼 다른 모델을 쓰고
    싶을 때만 명시적으로 넘기면 됨."""
    if not items:
        return []
    client = genai.Client()  # .env 의 GEMINI_API_KEY(Developer API) 또는 GOOGLE_GENAI_USE_VERTEXAI 계열(Vertex AI) 로 자동 인증
    by_id = {it["id"]: it for it in items}

    for i in range(0, len(items), batch_size):
        chunk = items[i : i + batch_size]
        resp = client.models.generate_content(
            model=model or config.MODEL,
            contents=_payload(chunk),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                max_output_tokens=16000,
                thinking_config=types.ThinkingConfig(thinking_budget=0),  # 분류/요약은 추론 불필요, thinking 끄면 출력 토큰 잘림 방지
                response_mime_type="application/json",
            ),
        )
        text = resp.text or ""
        for row in _parse(text):
            it = by_id.get(row.get("id"))
            if not it:
                continue
            cat = row.get("category")
            if cat in CATEGORY_LABELS:
                it["category"] = cat
            it["summary"] = row.get("summary", it.get("summary_raw", ""))[:600]
            it["significance"] = float(row.get("significance", 0.0))
            it["is_major"] = bool(row.get("is_major", False))

    # LLM 이 빠뜨린 아이템 폴백
    for it in items:
        it.setdefault("summary", it.get("summary_raw", ""))
        it.setdefault("significance", 0.0)
        it.setdefault("is_major", False)
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
