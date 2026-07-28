"""1회성: recap(헤드라인/$ 집계/카테고리 한 줄 요약) 기능 추가 전에 만들어진 다이제스트에
recap 데이터를 소급 생성. 이미 recap 이 있는 다이제스트는 건너뜀(재실행해도 안전).

    python generate_recaps.py
"""
from __future__ import annotations

import json

import config
import llm
from backfill import BACKFILL_MODEL
from store import Store


def run():
    cfg = config.load()
    id_to_name = {s.id: s.name for s in cfg.sources}
    store = Store(config.DB_PATH)

    digests = store.list_digests()
    todo = [d for d in digests if not store.recaps_for(d["date"]).get("")]
    print(f"{len(digests)}개 다이제스트 중 recap 없는 것 {len(todo)}개")

    for d in todo:
        label = d["date"]
        items = store.items_for_digest(label)
        for it in items:
            it["source_name"] = id_to_name.get(it["source_id"], it["source_id"])
        if not items:
            print(f"  {label}: 항목 없음 — 스킵")
            continue
        recap = llm.generate_recap(items, model=BACKFILL_MODEL)
        store.save_recap(label, "", headline=recap["headline"],
                         stats_json=json.dumps({"dollar_committed": recap["dollar_committed"]}))
        for cat, one_liner in recap["category_one_liners"].items():
            store.save_recap(label, cat, one_liner=one_liner)
        print(f"  {label}: \"{recap['headline']}\" (${recap['dollar_committed']})")

    store.close()
    print("완료 — rerender.py 로 페이지에 반영하세요")


if __name__ == "__main__":
    run()
