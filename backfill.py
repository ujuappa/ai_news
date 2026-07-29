"""1회성 백필: 최근 N개월간 블로그/랩 발표 소스를 모아 주간 아카이브 다이제스트로 생성.

    python pipeline.py --purge-all   # ← 재백필이면 반드시 선행 (아래 주의 참고)
    python backfill.py               # 기본 6개월
    python backfill.py --months 12

⚠️ **재백필(이미 백필한 걸 소스 확장해서 다시) 전에는 `pipeline.py --purge-all` 로 DB 를 비울 것.**
   `save_items` 는 아이템 id 기준 INSERT OR REPLACE 라 같은 항목은 덮어쓰지만, 소스 구성이 바뀌면
   주간 클러스터링 결과가 달라져서 옛 실행에서 온 아이템이 그대로 남고 `digests` 라벨도 옛 집계로
   덮인다. 섞인 아카이브가 되니 처음부터 다시 만들 것.

- 대상 소스: BACKFILL_SOURCE_IDS (블로그/랩 발표만. arXiv/TechCrunch/HN 은 볼륨 폭탄이라 제외)
- 엔리치 모델: BACKFILL_MODEL (기본 gemini-2.5-flash-lite — 대량 처리라 비용 절감)
- seen-store 는 건드리지 않음: 14일 롤링 cross-day dedup 과 무관한 과거 데이터라 의미 없음
- 오늘자 output/index.html 은 건드리지 않음 (render.render_archive_digest 로 archive/ 에만 기록)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import config
import dedup
import fetch
import llm
import render
from config import CATEGORY_ORDER
from store import Store

BACKFILL_SOURCE_IDS = {
    "openai", "anthropic", "deepmind", "meta_ai",
    "huggingface_blog", "ahead_of_ai", "import_ai",
}
BACKFILL_MODEL = "gemini-2.5-flash-lite"


def _rank_and_cap(items: list[dict], settings) -> list[tuple[str, list[dict]]]:
    """pipeline._rank_and_cap 와 동일 로직(카테고리별 유의성 정렬 + 상한). community_takes 는 v1 제외."""
    groups: list[tuple[str, list[dict]]] = []
    for cat in CATEGORY_ORDER:
        if cat == "community_takes":
            continue
        picked = sorted(
            [it for it in items if it["category"] == cat],
            key=lambda it: it["significance"],
            reverse=True,
        )
        groups.append((cat, picked[: settings.max_items_per_category]))
    return groups


def _parse_dt(iso: str) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _iso_week_label(dt: datetime) -> str:
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def fetch_backfill_items(sources, since_dt: datetime) -> list[dict]:
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    items: list[dict] = []
    for src in sources:
        if src.id not in BACKFILL_SOURCE_IDS:
            continue
        if src.parse == "sitemap":
            got = fetch.fetch_sitemap_source(src, since=since_iso)
        elif src.id == "meta_ai":
            got = fetch.fetch_paginated_feed(src, since=since_iso)
        else:
            got = fetch.fetch_source(src, max_entries=1000)
            got = [it for it in got if (dt := _parse_dt(it["published"])) and dt >= since_dt]
        print(f"  {src.id:20s} {len(got):4d} items")
        items.extend(got)
    return items


def run(months: int = 6):
    cfg = config.load()
    settings = cfg.settings
    sources = [s for s in cfg.enabled_sources() if s.id in BACKFILL_SOURCE_IDS]
    since_dt = datetime.now(timezone.utc) - timedelta(days=months * 30)
    store = Store(config.DB_PATH)

    print(f"[1/4] 백필 수집 — {len(sources)} sources, 최근 {months}개월 (~{since_dt.date()} 이후)")
    raw = fetch_backfill_items(sources, since_dt)
    print(f"      총 {len(raw)} raw items")

    if not raw:
        print("      수집된 아이템 없음 — 종료")
        store.close()
        return

    print("[2/4] dedup (전체 배치 클러스터링 — cross-day/seen-store 는 사용 안 함)")
    clustered = dedup.dedup_batch(raw, settings.dedup_threshold)
    print(f"      {len(raw)} -> {len(clustered)} clusters")

    buckets: dict[str, list[dict]] = defaultdict(list)
    for it in clustered:
        dt = _parse_dt(it.get("published", "")) or datetime.now(timezone.utc)
        buckets[_iso_week_label(dt)].append(it)

    id_to_name = {s.id: s.name for s in cfg.sources}
    approx_total_records = len(clustered)  # 정확한 값은 마지막에 rerender.py 로 다시 맞춰짐

    print(f"[3/4] LLM 엔리치({BACKFILL_MODEL}) + 랭킹 + 리캡 + 저장 — {len(buckets)} 주")
    for label in sorted(buckets):
        week_items = buckets[label]
        enriched = llm.enrich(week_items, model=BACKFILL_MODEL)
        ranked_pool = [it for it in enriched if it["significance"] >= settings.min_significance]
        groups = _rank_and_cap(ranked_pool, settings)
        majors = [it for it in ranked_pool if it.get("is_major")] if settings.flag_major_at_top else []
        majors.sort(key=lambda it: it["significance"], reverse=True)

        flat = [it for _c, items in groups for it in items]
        store.save_items(flat, label)  # seen-store 는 건드리지 않음 (commit_seen 호출 안 함)

        recap = llm.generate_recap(flat, model=BACKFILL_MODEL) if flat else \
            {"headline": "", "dollar_committed": None, "category_one_liners": {}}
        store.save_recap(label, "", headline=recap["headline"],
                         stats_json=json.dumps({"dollar_committed": recap["dollar_committed"]}))
        for cat, one_liner in recap["category_one_liners"].items():
            store.save_recap(label, cat, one_liner=one_liner)

        render.render_archive_digest(label, groups, majors, config.OUTPUT_DIR,
                                      recap=recap, total_records=approx_total_records)
        for cat, cat_items in groups:
            render.render_category_page(
                label, cat, groups, config.OUTPUT_DIR, in_archive=True,
                one_liner=recap["category_one_liners"].get(cat, ""),
                cap=settings.max_items_per_category, min_sig=settings.min_significance,
                total_records=approx_total_records,
            )
        store.record_digest(label, len(flat), f"archive/{label}.html")
        print(f"      {label}: {len(week_items)} -> {len(flat)} items")

    print("[4/4] 아카이브 인덱스 + 검색 인덱스 재생성")
    render.render_archive_index(store.list_digests(), config.OUTPUT_DIR)
    all_items = store.all_items()
    for it in all_items:
        it["source_name"] = id_to_name.get(it["source_id"], it["source_id"])
    render.render_search_page(all_items, config.OUTPUT_DIR)
    store.close()
    print(f"백필 완료 — {config.OUTPUT_DIR/'archive'} 확인 (오늘자 index.html 은 미변경)")


if __name__ == "__main__":
    months = 6
    if "--months" in sys.argv:
        months = int(sys.argv[sys.argv.index("--months") + 1])
    run(months=months)
