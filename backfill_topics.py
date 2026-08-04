"""아카이브 아이템에 토픽을 소급으로 붙인다 (1회성).

홈 필터가 2026-08-04 부터 카테고리 대신 **토픽** pill 을 쓴다(`config.TOPIC_ORDER`).
새로 수집되는 항목은 `llm.enrich` 가 알아서 토픽을 달지만, 이미 쌓인 아카이브는 비어 있어서
과거 날짜 페이지의 필터 줄이 텅 빈다. 이 스크립트가 그걸 채운다.

**분류만 한다.** 요약·significance·headline 은 건드리지 않는다 — 이미 있는 값이고,
다시 생성하면 과거 다이제스트의 내용 자체가 바뀐다(재렌더는 원본과 같아야 한다).

토픽이 `'[]'` 인 항목만 고르므로 **중단해도 그냥 다시 돌리면 이어서 한다.**

    python backfill_topics.py --dry-run --limit 20   # 호출 없이 대상만 확인
    python backfill_topics.py --limit 60             # 조금만 실제로
    python backfill_topics.py                        # 전체
    python rerender.py                               # 사이트 반영 (API 비용 0)
"""
from __future__ import annotations

import argparse
from collections import Counter

import config
import llm
from store import Store


def _to_payload(row: dict) -> dict:
    """DB 행 -> `llm._payload` 가 기대하는 모양. 요약이 없으면 제목만으로 판단한다."""
    return {
        "id": row["id"],
        "source_name": "",
        "category": row.get("category") or "",
        "cluster_sources": [],
        "title": (row.get("headline") or "").strip() or row.get("title") or "",
        "summary_raw": (row.get("summary") or "")[:600],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="아카이브에 토픽 소급 부여")
    ap.add_argument("--limit", type=int, default=None, help="앞에서 N건만")
    ap.add_argument("--batch-size", type=int, default=60)
    ap.add_argument("--model", default=None, help="기본은 config.MODEL")
    ap.add_argument("--dry-run", action="store_true", help="LLM 호출 없이 대상만 표시")
    args = ap.parse_args()

    store = Store(config.DB_PATH)
    rows = store.items_missing_topics(limit=args.limit)
    if not rows:
        print("토픽이 빠진 게재 아이템이 없다. (이미 전부 분류됨)")
        store.close()
        return

    print(f"대상 {len(rows)}건")
    if args.dry_run:
        for r in rows[:10]:
            print(f"  {r['id'][:12]}  [{r['category']}]  "
                  f"{((r.get('headline') or '').strip() or r['title'])[:70]}")
        if len(rows) > 10:
            print(f"  … 외 {len(rows) - 10}건")
        print("\n(dry-run: LLM 호출도 DB 변경도 없음)")
        store.close()
        return

    assigned = llm.classify_topics([_to_payload(r) for r in rows],
                                   batch_size=args.batch_size, model=args.model)
    if not assigned:
        print("아무것도 분류되지 않았다 — 전 배치 실패. DB 는 그대로 둔다.")
        store.close()
        return

    store.record_topics(list(assigned.items()))
    spread = Counter(t for topics in assigned.values() for t in topics)
    tagged = sum(1 for t in assigned.values() if t)
    print(f"\n{len(assigned)}건 기록 (토픽이 붙은 건 {tagged}건, "
          f"어디에도 안 걸린 건 {len(assigned) - tagged}건)")
    for topic, n in spread.most_common():
        print(f"  {topic:12} {n}")
    missing = len(rows) - len(assigned)
    if missing:
        print(f"\n{missing}건은 응답에 없어 미분류로 남았다 — 다시 실행하면 이어서 시도한다.")
    print("사이트 반영: python rerender.py")
    store.close()


if __name__ == "__main__":
    main()
