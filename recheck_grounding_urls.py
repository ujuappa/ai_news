"""이미 게재된 grounding 아이템의 URL 을 **현재 게이트 기준으로** 다시 검사한다.

왜 필요한가: `llm.catch_missed_news` 의 품질 게이트(2026-07-31, PROJECT_MEMO §13 T2.1)는
**앞으로 들어올 것만** 막는다. 그 전에 저장된 아이템은 사이트와 RSS 피드에 그대로 남는다 —
실제로 라운드업/홈페이지 URL 5건이 게재된 상태였고, 피드를 만들자 첫 항목부터 드러났다.
`sources.yaml` 의 `blocked_domains` 에 새 도메인을 추가할 때도 같은 상황이 생기므로
일회성 스크립트가 아니라 다시 쓸 수 있게 남겨둔다.

⚠️ **`gemini_grounding` 소스만 검사한다.** 게이트의 "맨 도메인" 규칙은 grounding 전용이다 —
`hn_ai`/`hn_show` 는 Show HN 처럼 제품 홈페이지를 링크하는 게 정상이고(실측: `learnvector.ai/`),
전역으로 적용하면 정상 아이템을 지운다. 이 스코프를 넓히지 말 것.

    python recheck_grounding_urls.py            # 보고만 (기본값, DB 미변경)
    python recheck_grounding_urls.py --apply    # 실제로 내림 -> 이후 rerender.py 필요
"""
from __future__ import annotations

import argparse

import config
import llm
from store import Store

DROP_REASON = "source_quality"


def find_bad(store: Store) -> list[dict]:
    """게재된 grounding 아이템 중 현재 게이트가 거부할 것들. 이유(`_why`)를 붙여 반환."""
    cfg = config.load().settings
    doms = (llm.GROUNDING_BLOCKED_DOMAINS if cfg.grounding_blocked_domains is None
            else cfg.grounding_blocked_domains)
    pats = (llm.GROUNDING_BLOCKED_URL_PATTERNS if cfg.grounding_blocked_url_patterns is None
            else cfg.grounding_blocked_url_patterns)
    rows = store.conn.execute(
        """SELECT id, digest_date, headline, title, url FROM items
           WHERE is_published=1 AND source_id='gemini_grounding'"""
    ).fetchall()
    out = []
    for r in rows:
        why = llm._grounding_reject_reason(r["url"], doms, pats)
        if why:
            d = dict(r)
            d["_why"] = why
            out.append(d)
    return out


def run(apply: bool = False):
    store = Store(config.DB_PATH)
    bad = find_bad(store)
    if not bad:
        print("게재된 grounding 아이템 중 거부 대상 없음.")
        store.close()
        return

    print(f"거부 대상 {len(bad)}건:")
    for r in bad:
        print(f"  [{r['_why']}] {r['digest_date']}  {(r['headline'] or r['title'])[:52]}")
        print(f"      {r['url'][:78]}")

    if not apply:
        print("\n보고만 함 (DB 미변경). 실제로 내리려면 --apply.")
        store.close()
        return

    n = store.unpublish([r["id"] for r in bad], DROP_REASON)
    print(f"\n{n}건 내림 (is_published=0, drop_reason='{DROP_REASON}').")
    for label in sorted({r["digest_date"] for r in bad}):
        print(f"  {label}: item_count -> {store.recount_digest(label)}")
    store.close()
    print("\n⚠️ `python rerender.py` 로 페이지·피드를 다시 만들어야 반영된다.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="실제로 내린다 (기본은 보고만)")
    run(**vars(ap.parse_args()))
