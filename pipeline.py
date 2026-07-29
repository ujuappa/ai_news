"""오케스트레이터: 하루치 다이제스트를 생성하는 엔드투엔드 파이프라인.

    python pipeline.py            # 정상 실행
    python pipeline.py --dry-run  # LLM 호출 없이 수집/dedup 까지만 (원문 발췌로 렌더, DB 미변경)
    python pipeline.py --reset      # seen 테이블만 비움 (items/digests/recaps 보존)
    python pipeline.py --purge-all  # digest.db 파일 통째 삭제 (확인 프롬프트, --yes 로 생략)
                                    # 재백필 전에 반드시 선행
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
    """seen-store 초기화 — `seen` 테이블만 비우고 items/digests/recaps 는 보존.

    예전엔 digest.db 를 통째로 지웠는데 그러면 아카이브 히스토리까지 날아갔음
    (백필 27주치를 그렇게 잃음). 전체 삭제가 필요하면 --purge-all."""
    if not config.DB_PATH.exists():
        print(f"{config.DB_PATH} 없음 — 이미 깨끗함")
        return
    store = Store(config.DB_PATH)
    c = store.counts()
    n = store.clear_seen()
    store.close()
    print(f"✅ seen-store 초기화 완료 — {n}건 삭제 "
          f"(items {c['items']} / digests {c['digests']} / recaps {c['recaps']} 보존)")
    print("   다음 실행에서 모든 아이템이 '신규'로 잡힘. 전체 삭제는 --purge-all")


def purge_all(assume_yes: bool = False):
    """digest.db 파일 통째 삭제 — seen-store + 아카이브 히스토리 전부 소멸, 복구 불가.

    **재백필(§5 '아카이브 재백필') 전에 반드시 선행**: 소스를 늘려 과거를 다시 만들 때
    옛 아카이브가 남아 있으면 같은 주가 두 벌 생기고 digests 라벨이 충돌한다.
    일상적인 dedup 초기화는 --reset 으로 충분하니 이건 정말 재구축할 때만."""
    if not config.DB_PATH.exists():
        print(f"{config.DB_PATH} 없음 — 이미 깨끗함")
        return
    store = Store(config.DB_PATH)
    c = store.counts()
    store.close()
    print(f"⚠️ {config.DB_PATH} 전체 삭제 — seen {c['seen']} / items {c['items']} / "
          f"digests {c['digests']} / recaps {c['recaps']} 전부 사라짐 (복구 불가).")
    print(f"   output/ 의 HTML 은 남지만 아카이브 인덱스에서는 빠짐. "
          f"dedup 기록만 지우려면 --reset.")
    if not assume_yes and input("   정말 삭제하려면 'yes' 입력: ").strip() != "yes":
        print("취소됨 — 아무것도 지우지 않음")
        return
    config.DB_PATH.unlink()
    print(f"✅ {config.DB_PATH} 삭제 완료")


if __name__ == "__main__":
    if "--purge-all" in sys.argv:
        purge_all(assume_yes="--yes" in sys.argv)
    elif "--reset" in sys.argv:
        reset_db()
    else:
        run(dry_run="--dry-run" in sys.argv)
