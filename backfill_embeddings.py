"""기존 아카이브 아이템의 임베딩을 item_emb 에 채우는 1회성 스크립트.

threading 은 몇 달 전 기사와 비교해야 하는데 seen-store 는 14일치뿐이고, 그마저도
매일 purge 된다. 로컬 sentence-transformers 만 쓰므로 **API 비용 0**.
여러 번 돌려도 안전 — 이미 채워진 id 는 건너뛴다.

주의: 새 아이템은 `title. summary_raw`(원문 발췌)로 임베딩되는데 여기서는 원문이 남아 있지
않아 `title. summary`(LLM 요약)를 쓴다. 둘 다 제목이 지배적이라 실무상 차이는 작지만,
threading 구간을 튜닝할 땐 이 비대칭을 감안할 것(측정값은 PROJECT_MEMO 참고).

    python backfill_embeddings.py
"""
from __future__ import annotations

import config
import dedup
from store import Store


def run():
    store = Store(config.DB_PATH)
    have = {r["id"] for r in store.conn.execute("SELECT id FROM item_emb")}
    todo = [it for it in store.all_items() if it["id"] not in have]
    if not todo:
        print(f"이미 전부 채워짐 — item_emb {len(have)}건")
        store.close()
        return

    print(f"{len(todo)}건 임베딩 생성 (기존 {len(have)}건 건너뜀) — 로컬 모델, API 비용 없음")
    embs = dedup.embed([f"{it['title']}. {it.get('summary') or ''}" for it in todo])
    for it, e in zip(todo, embs):
        it["_emb"] = e

    by_date: dict[str, list[dict]] = {}
    for it in todo:
        by_date.setdefault(it["digest_date"], []).append(it)
    for digest_date, items in by_date.items():
        store.save_embeddings(items, digest_date)

    print(f"완료 — item_emb {store.counts()['item_emb']}건 "
          f"({len(by_date)}개 다이제스트)")
    store.close()


if __name__ == "__main__":
    run()
