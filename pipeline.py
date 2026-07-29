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
from store import Store


def _todays_pool(store: Store, clustered: list[dict], today: str,
                 id_to_name: dict[str, str]) -> list[dict]:
    """오늘의 후보 풀 = DB 에 저장된 오늘자 아이템(게재분+탈락분) + 이번 실행분.
    id 가 겹치면 이번 실행분이 이김(판정이 더 최신).

    이번 실행분만 가지고 렌더하면 같은 날 두 번째 실행이 index.html 을 그 실행분
    (보통 1~2건)으로 잘라먹는다 — cross-day dedup 이 오전에 이미 실은 항목을 '본 것'으로
    걸러내서 clustered 가 거의 비기 때문. DB 를 하루치의 단일 진실로 삼고 매 실행이
    누적 전체를 다시 랭킹한다."""
    pool: dict[str, dict] = {}
    for it in store.items_for_digest(today) + store.dropped_items(today):
        it["_enriched"] = it.get("drop_reason") != "enrich_failed"
        it["is_major"] = bool(it["is_major"])
        it.setdefault("cluster_sources", [])
        pool[it["id"]] = it
    pool.update({it["id"]: it for it in clustered})
    for it in pool.values():
        it["source_name"] = id_to_name.get(it["source_id"], it["source_id"])
    return list(pool.values())


def _drop_reasons(clustered: list[dict], flat: list[dict], settings) -> dict[str, list[dict]]:
    """게재되지 못한 아이템을 사유별로 묶는다. 사유는 파이프라인이 거른 순서대로 판정 —
    LLM 실패 > 저의미 > 카테고리 OFF > 카테고리 상한. 컷 튜닝할 때 근거 데이터가 됨."""
    published_ids = {it["id"] for it in flat}
    buckets: dict[str, list[dict]] = {}
    for it in clustered:
        if it["id"] in published_ids:
            continue
        if not it.get("_enriched", True):
            reason = "enrich_failed"
        elif it["significance"] < settings.min_significance:
            reason = "min_significance"
        elif it["category"] == "community_takes":
            reason = "category_off"  # v1 에서 통째로 제외되는 카테고리
        else:
            reason = "category_cap"
        buckets.setdefault(reason, []).append(it)
    return buckets


def _health_warnings(health: dict[str, tuple[int, int]], sources) -> list[str]:
    """피드 자체가 안 잡히는 소스만 경고(raw==0 — 죽었거나 파싱 실패).

    예전엔 신선도 컷 통과분이 0 이면 경고했는데, 그러면 월간 발행 소스(Ahead of AI 등)가
    이번 주 글이 없다는 이유로 매번 ⚠️ 배지를 달았다. 진짜 이상과 구분이 안 돼서
    배지가 의미를 잃음 → 피드에서 아무것도 못 가져온 경우만 경고."""
    id_to_name = {s.id: s.name for s in sources}
    return [id_to_name.get(sid, sid) for sid, (_fresh, raw) in health.items() if raw == 0]


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

    # 신규 0건도 별도 경로를 타지 않는다. 아래 풀 구성이 DB 에서 오늘자를 읽어오므로
    # 같은 렌더 경로로 "오늘 이미 실린 것"이 그대로 다시 나온다(예전엔 빈 페이지로 덮었음).
    if not clustered:
        print("[3/5] 신규 아이템 없음 — LLM 스킵, DB 의 오늘자로 재렌더")
    elif dry_run:
        print("[3/5] LLM 스킵 (--dry-run): 원문 발췌로 채움")
        for it in clustered:
            it["summary"] = it["summary_raw"]
            it["significance"] = 0.5
            it["is_major"] = False
    else:
        print(f"[3/5] LLM 강화 — model={config.MODEL}")
        clustered = llm.enrich(clustered)
        
        print("      Gemini Grounding (놓친 뉴스 확인)")
        existing_titles = [it["title"] for it in clustered]
        missed = llm.catch_missed_news(existing_titles)
        if missed:
            print(f"      놓친 뉴스 {len(missed)}건 추가 발견, 강화 시작")
            for it in missed:
                it["summary_raw"] = fetch._extract_full_text(it["url"], it.get("summary_raw", ""))
            missed_enriched = llm.enrich(missed)
            clustered.extend(missed_enriched)

    id_to_name = {s.id: s.name for s in cfg.sources}
    pool = _todays_pool(store, clustered, today, id_to_name)
    ranked_pool = [it for it in pool if it["significance"] >= settings.min_significance]
    dropped = len(pool) - len(ranked_pool)

    print(f"[4/5] 랭킹 + 상한{' (dry-run: 저장 스킵)' if dry_run else ' + 저장'}"
          f" — 오늘 후보 {len(pool)}건(신규 {len(clustered)} + DB {len(pool) - len(clustered)})"
          + (f", significance<{settings.min_significance} {dropped}건 드롭(홍보성 필터)" if dropped else ""))
    groups = render.group_by_category(ranked_pool, cap=settings.max_items_per_category)

    flat = [it for _c, items in groups for it in items]
    buckets = _drop_reasons(pool, flat, settings)
    if buckets:
        print("      탈락 " + ", ".join(f"{r} {len(v)}건" for r, v in sorted(buckets.items())))
    if not dry_run:
        store.save_items(flat, today)
        for reason, items in buckets.items():
            store.save_items(items, today, is_published=False, drop_reason=reason)
        # seen 에는 "제대로 판정받고 끝난 것" 만 넣는다.
        #   게재분          — 내일 또 실으면 안 됨
        #   min_significance — LLM 이 보고 낮게 매김. 내일 재스코어해도 결과 같으니 토큰 낭비
        # 나머지는 구조적 이유로 밀린 거라 내일 다시 기회를 준다(=seen 에 안 넣음):
        #   category_cap    — 컷은 넘겼는데 자리가 없었을 뿐. 캡 튜닝 데이터도 여기서 나옴
        #   enrich_failed   — 판정 자체를 못 받음(LLM 배치 실패)
        #   category_off    — community_takes 는 v1 OFF. 지금은 소스가 전부 비활성이라 0건이지만,
        #                     켜지 않은 채 소스만 살리면 매일 재엔리치되니 그때 재검토할 것
        # 추가 대상은 이번 실행분(clustered)으로 한정 — DB 에서 읽어온 항목엔 임베딩(_emb)이 없어서
        # seen 에 넣으면 임베딩 없는 행이 되어 cross-day 유사도 비교가 안 된다.
        seen_ids = {it["id"] for it in flat} | {it["id"] for it in buckets.get("min_significance", [])}
        dedup.commit_seen([it for it in clustered if it["id"] in seen_ids], store)
        # 반대로 빼기도 해야 위 정책이 실제로 지켜진다. 오전에 실렸다가 오후 고득점에 밀린 항목은
        # 이미 seen 에 들어가 있어서, 지워주지 않으면 캡 드롭인데도 내일 재시도를 못 받는다.
        store.unsee([it["id"] for r, items in buckets.items()
                     if r != "min_significance" for it in items])
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
    all_items = store.all_items()
    for it in all_items:
        it["source_name"] = id_to_name.get(it["source_id"], it["source_id"])
    total_records = len(all_items)

    render.render_digest(today, groups, warnings, config.OUTPUT_DIR, total_records=total_records)
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

    n_major = sum(1 for it in flat if it.get("is_major"))
    print(f"완료 → {config.OUTPUT_DIR/'index.html'}  ({len(flat)} items, {n_major} major)")
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
