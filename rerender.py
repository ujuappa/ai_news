"""DB 에 이미 저장된 아이템으로 모든 다이제스트 페이지를 다시 렌더링.

render.py 의 템플릿/디자인만 바꿨을 때 API 비용 없이 전체 페이지(오늘자 + 카테고리 뷰 +
아카이브 + 검색)를 갱신하는 용도. recap(헤드라인/한 줄 요약)은 DB 에 이미 있으면 반영되고,
없으면 generate_recaps.py 로 먼저 채워야 함.

    python rerender.py
"""
from __future__ import annotations

import json
import re

import config
import render
from store import Store

_DAILY_LABEL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def run():
    cfg = config.load()
    settings = cfg.settings
    id_to_name = {s.id: s.name for s in cfg.sources}
    store = Store(config.DB_PATH)

    all_items = store.all_items()
    for it in all_items:
        it["source_name"] = id_to_name.get(it["source_id"], it["source_id"])
    total_records = len(all_items)

    digests = store.list_digests()
    # index.html(루트)에는 반드시 '가장 최근 일간' 다이제스트만. 주간 백필 라벨(2026-W31)을
    # 인덱스로 삼으면 홈페이지가 과거 한 주 다이제스트로 덮인다.
    latest_daily = next((d["date"] for d in digests if _DAILY_LABEL_RE.match(d["date"])), None)
    if latest_daily is None:
        print("⚠️ 일간 다이제스트가 없음 — index.html 은 건드리지 않고 아카이브만 재렌더")
    print(f"{len(digests)}개 다이제스트 재렌더 (index={latest_daily}, total_records={total_records})")
    for d in digests:
        label = d["date"]
        items = store.items_for_digest(label)
        for it in items:
            it["source_name"] = id_to_name.get(it["source_id"], it["source_id"])
        parent_info = store.thread_parent_info([it.get("thread_parent_id", "") for it in items])
        for it in items:
            it["thread_parent"] = parent_info.get(it.get("thread_parent_id") or "")
        # cap 없음: DB 의 게재분은 저장 시점에 이미 상한이 적용돼 있음
        groups = render.group_by_category(items)
        recaps = store.recaps_for(label)
        is_today = label == latest_daily

        if is_today:
            # 최신 것만 index.html(루트)에도 반영 — render_digest 가 루트/archive 상대경로를 각각 맞춰 씀
            render.render_digest(label, groups, [], config.OUTPUT_DIR, total_records=total_records)
        else:
            whole = recaps.get("", {})
            stats = json.loads(whole.get("stats_json") or "{}")
            recap = {"headline": whole.get("headline"), "dollar_committed": stats.get("dollar_committed")}
            render.render_archive_digest(label, groups, config.OUTPUT_DIR,
                                          recap=recap, total_records=total_records)

        for cat, cat_items in groups:
            one_liner = recaps.get(cat, {}).get("one_liner", "")
            rule = settings.rule_for(cat)
            render.render_category_page(
                label, cat, groups, config.OUTPUT_DIR, in_archive=not is_today,
                one_liner=one_liner, cap=rule.max_items,
                min_sig=rule.min_significance, total_records=total_records,
            )
        print(f"  {label}: {len(items)} items")

    render.render_archive_index(store.list_digests(), config.OUTPUT_DIR)
    render.render_search_page(all_items, config.OUTPUT_DIR)
    repo = config.github_repo()
    render.render_sources_page(cfg.sources, store.source_stats(), config.OUTPUT_DIR,
                               total_records=total_records, repo=repo)
    render.render_admin_page(config.OUTPUT_DIR, repo=repo)
    render.render_saved_page(config.OUTPUT_DIR, total_records=total_records)
    render.render_feed(store.recent_digest_entries(settings.feed_max_digests),
                       config.OUTPUT_DIR, settings.site_url)

    store.close()
    print("재렌더 완료")


if __name__ == "__main__":
    run()
