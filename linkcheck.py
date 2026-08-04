"""게시된 링크의 사후 점검 (link rot).

수집 시점 게이트(`llm._grounding_reject_reason`)는 **실을 때** 만 본다. 기사는 실린 뒤에도
죽는다 — 삭제 · 이관 · 유료화 · 사이트 개편. 이 스크립트는 DB 의 게재분을 다시 찔러
`items.link_status` 에 결과를 기록하고, 렌더는 그 값을 보고 죽은 링크를 **링크가 아닌
텍스트로** 내보낸다(`store.DEAD_LINK_STATUSES`).

판정은 `fetch.dead_page_reason` 을 그대로 쓴다 — grounding 게이트와 같은 기준이어야
"실을 땐 통과했는데 점검에선 죽었다"가 정말 link rot 을 뜻하게 된다.

    python linkcheck.py                      # 게재분 전체
    python linkcheck.py --since 2026-07-01   # 일간 라벨 하한
    python linkcheck.py --recheck-days 7     # 최근 7일 안에 본 건 건너뜀(재개용)
    python linkcheck.py --dry-run            # DB 미변경, 리포트만
    python linkcheck.py --limit 20 --workers 4

점검 뒤 사이트에 반영하려면 `python rerender.py` (API 비용 0).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor

import config
import fetch
from store import DEAD_LINK_STATUSES, Store

# 사후 점검은 수집보다 훨씬 보수적으로 간다. 수집 땐 하루 3건이라 "애매하면 버림"이 싸지만,
# 여기선 오판 하나가 멀쩡한 아카이브 기사의 링크를 떼는 일이라 손해가 크다.
TIMEOUT = 20

# 2026-08-04 실측으로 얻은 분류. 처음엔 "못 받았으면 죽은 링크"로 뭉갰다가 최근 40건에서
# **멀쩡한 기사 3건**을 죽은 걸로 잡을 뻔했다:
#   wsj.com → 401 (페이월. 구독자는 읽는다)  ·  washingtonpost.com → ConnectionError (봇 차단)
# 그래서 **서버가 '없다'고 명시한 경우에만** 죽은 것으로 본다.
GONE_STATUSES = (404, 410)
BLOCKED_STATUSES = (401, 402, 403, 429)  # 페이월·봇월. 링크는 유효하다


def classify(probe, claimed_title: str) -> str:
    """점검 결과 한 줄 요약. store.DEAD_LINK_STATUSES 에 든 값만 렌더에서 링크가 떨어진다."""
    if probe.status in GONE_STATUSES:
        return "gone"
    if probe.status in BLOCKED_STATUSES:
        return "blocked"
    if not probe.ok:
        # 요청 실패(status 0) 또는 5xx 등. 일시적일 수 있으니 죽은 걸로 단정하지 않는다.
        return "unreachable" if probe.status == 0 else f"http_{probe.status}"
    return fetch.dead_page_reason(probe.title, claimed_title) or "ok"


def check_one(row: dict) -> tuple[str, str, str]:
    """(url, status, 도착 페이지 제목)."""
    probe = fetch.probe_url(row["url"], timeout=TIMEOUT)
    return row["url"], classify(probe, row["title"]), probe.title


def main() -> None:
    ap = argparse.ArgumentParser(description="게시된 링크의 link rot 점검")
    ap.add_argument("--since", default="", help="digest_date 하한 (예: 2026-07-01)")
    ap.add_argument("--recheck-days", type=int, default=None,
                    help="이 일수 안에 이미 점검한 항목은 건너뜀")
    ap.add_argument("--limit", type=int, default=None, help="앞에서 N건만")
    ap.add_argument("--workers", type=int, default=8, help="동시 요청 수 (기본 8)")
    ap.add_argument("--dry-run", action="store_true", help="DB 에 쓰지 않고 리포트만")
    args = ap.parse_args()

    store = Store(config.DB_PATH)
    rows = store.links_to_check(since=args.since, recheck_days=args.recheck_days)
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("점검할 링크가 없다.")
        store.close()
        return

    print(f"[1/2] {len(rows)}개 URL 점검 (workers={args.workers})")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(check_one, rows))

    by_url = {r["url"]: r for r in rows}
    counts: dict[str, int] = {}
    problems: list[tuple[str, dict, str]] = []
    for url, status, page_title in results:
        counts[status] = counts.get(status, 0) + 1
        if status != "ok":
            problems.append((status, by_url[url], page_title))

    print("[2/2] 결과: " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    for status, row, page_title in sorted(problems, key=lambda p: (p[0], p[1]["digest_date"])):
        dead = " (렌더에서 링크 제거)" if status in DEAD_LINK_STATUSES else " (리포트만 — 사람이 판단)"
        print(f"  [{status}]{dead}  {row['digest_date']}  {row['url']}")
        print(f"      실린 제목: {row['title'][:80]}")
        if page_title:
            print(f"      도착 제목: {page_title[:80]}")

    if args.dry_run:
        print("\n(dry-run: DB 미변경)")
    else:
        store.record_link_status([(url, status) for url, status, _t in results])
        print(f"\n{len(results)}건 기록. 전체 분포: {store.link_status_counts()}")
        print("사이트 반영: python rerender.py")
    store.close()


if __name__ == "__main__":
    main()
