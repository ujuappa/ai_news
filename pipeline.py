"""오케스트레이터: 하루치 다이제스트를 생성하는 엔드투엔드 파이프라인.

    python pipeline.py            # 정상 실행
    python pipeline.py --dry-run  # LLM 호출 없이 수집/dedup 까지만 (원문 발췌로 렌더, DB 미변경)
    python pipeline.py --reset    # seen-store/히스토리 초기화 (digest.db 삭제)
"""
from __future__ import annotations

import json
import sys
from datetime import date

import config
import dedup
import fetch
import llm
import render
from config import CATEGORY_ORDER
from store import Store


def _rank_and_cap(items: list[dict], settings) -> list[tuple[str, list[dict]]]:
    """카테고리별로 유의성 내림차순 정렬 + 상한 적용. community_takes 는 v1 제외."""
    groups: list[tuple[str, list[dict]]] = []
    for cat in CATEGORY_ORDER:
        if cat == "community_takes":
            continue  # v1 OFF
        picked = sorted(
            [it for it in items if it["category"] == cat],
            key=lambda it: it["significance"],
            reverse=True,
        )
        groups.append((cat, picked[: settings.max_items_per_category]))
    return groups


def _health_warnings(health: dict[str, int], sources) -> list[str]:
    id_to_name = {s.id: s.name for s in sources}
    return [id_to_name.get(sid, sid) for sid, n in health.items() if n == 0]


def run(dry_run: bool = False):
    cfg = config.load()
    settings = cfg.settings
    sources = cfg.enabled_sources()
    today = date.today().isoformat()
    store = Store(config.DB_PATH)

    print(f"[1/5] 수집 — {len(sources)} sources (freshness cutoff: {settings.max_item_age_days}일)")
    raw, health = fetch.fetch_all(sources, max_age_days=settings.max_item_age_days)
    print(f"      총 {len(raw)} raw items")

    print("[2/5] dedup (배치 내 클러스터링)")
    clustered = dedup.dedup_batch(raw, settings.dedup_threshold)
    print(f"      {len(raw)} -> {len(clustered)} clusters")

    if settings.dedup_cross_day:
        clustered = dedup.drop_cross_day(
            clustered, store, settings.dedup_threshold, settings.seen_store_retention_days
        )
        print(f"      cross-day 후 신규 {len(clustered)} items")

    if not clustered:
        # 여기서 그냥 return 하면 어제 페이지가 오늘 날짜인 척 그대로 남음 -> 빈 다이제스트로 렌더.
        print("      신규 아이템 없음 — 빈 다이제스트로 렌더")
        empty_groups = [(c, []) for c in CATEGORY_ORDER if c != "community_takes"]
        all_items = store.all_items()
        render.render_digest(today, empty_groups, [], _health_warnings(health, sources),
                             config.OUTPUT_DIR, total_records=len(all_items))
        if not dry_run:
            store.record_digest(today, 0, f"archive/{today}.html")
        render.render_archive_index(store.list_digests(), config.OUTPUT_DIR)
        store.close()
        return

    if dry_run:
        print("[3/5] LLM 스킵 (--dry-run): 원문 발췌로 채움")
        for it in clustered:
            it["summary"] = it["summary_raw"]
            it["significance"] = 0.5
            it["is_major"] = False
    else:
        print(f"[3/5] LLM 강화 — model={config.MODEL}")
        clustered = llm.enrich(clustered)

    ranked_pool = [it for it in clustered if it["significance"] >= settings.min_significance]
    dropped = len(clustered) - len(ranked_pool)

    print(f"[4/5] 랭킹 + 상한{' (dry-run: 저장 스킵)' if dry_run else ' + 저장'}"
          + (f" — significance<{settings.min_significance} {dropped}건 드롭(홍보성 필터)" if dropped else ""))
    groups = _rank_and_cap(ranked_pool, settings)
    majors = [it for it in ranked_pool if it.get("is_major")] if settings.flag_major_at_top else []
    majors.sort(key=lambda it: it["significance"], reverse=True)

    flat = [it for _c, items in groups for it in items]
    if not dry_run:
        store.save_items(flat, today)
        # 드롭된 저의미 아이템도 seen 처리 -> 내일 재스코어 안 함.
        # 단 LLM 배치가 죽어서 significance 0.0 으로 폴백된 건은 제외 — seen 에 넣으면
        # 판단도 못 받고 영영 사라짐. 내일 다시 시도하게 남겨둔다.
        dedup.commit_seen([it for it in clustered if it.get("_enriched", True)], store)
        store.purge_old_seen(settings.seen_store_retention_days)

    recap = {"headline": "", "dollar_committed": None, "category_one_liners": {}}
    if not dry_run and flat:
        print("      리캡 생성(헤드라인/카테고리 요약/$ 집계)")
        recap = llm.generate_recap(flat)
        store.save_recap(today, "", headline=recap["headline"],
                         stats_json=json.dumps({"dollar_committed": recap["dollar_committed"]}))
        for cat, one_liner in recap["category_one_liners"].items():
            store.save_recap(today, cat, one_liner=one_liner)

    print("[5/5] 렌더")
    warnings = _health_warnings(health, sources)
    id_to_name = {s.id: s.name for s in cfg.sources}
    all_items = store.all_items()
    for it in all_items:
        it["source_name"] = id_to_name.get(it["source_id"], it["source_id"])
    total_records = len(all_items)

    render.render_digest(today, groups, majors, warnings, config.OUTPUT_DIR, total_records=total_records)
    for cat, cat_items in groups:
        render.render_category_page(
            today, cat, groups, config.OUTPUT_DIR, in_archive=False,
            one_liner=recap["category_one_liners"].get(cat, ""),
            cap=settings.max_items_per_category, min_sig=settings.min_significance,
            total_records=total_records,
        )
    if not dry_run:
        store.record_digest(today, len(flat), f"archive/{today}.html")
    render.render_archive_index(store.list_digests(), config.OUTPUT_DIR)
    render.render_search_page(all_items, config.OUTPUT_DIR)

    print(f"완료 → {config.OUTPUT_DIR/'index.html'}  ({len(flat)} items, {len(majors)} major)")
    if dry_run:
        print("      (dry-run: seen-store/DB 미변경)")
    if warnings:
        print(f"⚠️ 소스 이상: {', '.join(warnings)}")
    store.close()


def reset_db():
    """seen-store + 히스토리 전체 초기화 (DB 파일 삭제)."""
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
        print(f"✅ {config.DB_PATH} 삭제 완료 — seen-store/히스토리 초기화됨")
    else:
        print(f"{config.DB_PATH} 없음 — 이미 깨끗함")


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset_db()
    else:
        run(dry_run="--dry-run" in sys.argv)
