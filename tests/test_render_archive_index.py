"""아카이브 인덱스 도달성 회귀 테스트 (PROJECT_MEMO §13 T3.2).

2026-07-31 이전에는 `render_archive_index` 가 `digests[:6]` 만 `<a>` 로 만들고 나머지는
`+ 41 earlier digests` 라는 **링크 없는 텍스트**로 끝냈다. 6개월 백필로 만든 43주치가
사이트 안에서 도달 불가였다(검색이나 URL 직접 입력 외에는 경로가 없음).

고정하는 계약:
  1. **모든** 다이제스트가 링크된다. 잘라내면 안 된다.
  2. 링크 href 는 아카이브 인덱스와 같은 디렉터리 기준의 `{label}.html` 이다.
  3. 최신 강조는 일간/주간 라벨이 섞여 있어도 진짜 최신 하나만 받는다.
  4. 헤드라인 문구가 주간/일간을 구분한다("47 weeks" 는 틀린 문구였다 — 4건이 일간).
"""
import re

import pytest

import render
from store import is_week_label, label_sort_key

ROW_RE = re.compile(r'class="archive-row([^"]*)" href="([^"]+)"')
YEAR_RE = re.compile(r'class="archive-year"><span>(\d{4})</span><span>(\d+)</span>')


def _digests(labels):
    """store.list_digests() 형태 — label_sort_key 내림차순(그 함수가 그렇게 정렬해서 준다)."""
    rows = [{"date": lb, "item_count": 5 + i, "top_title": f"top {lb}"}
            for i, lb in enumerate(labels)]
    return sorted(rows, key=lambda r: label_sort_key(r["date"]), reverse=True)


def _render(tmp_path, labels):
    render.render_archive_index(_digests(labels), tmp_path)
    return (tmp_path / "archive" / "index.html").read_text(encoding="utf-8")


# 실제 DB 구성(2026-07-31): 일간 4 + 주간 43. 여기선 축약해서 같은 성격만 재현.
MIXED = ["2026-07-31", "2026-07-30", "2026-07-29", "2026-07-28",
         "2026-W31", "2026-W30", "2026-W29", "2025-W40", "2024-W21", "2023-W10"]


def test_every_digest_is_linked(tmp_path):
    """계약 1 — 이게 T3.2 의 본질이다."""
    page = _render(tmp_path, MIXED)
    hrefs = [h for _c, h in ROW_RE.findall(page)]
    assert len(hrefs) == len(MIXED)
    assert set(hrefs) == {f"{lb}.html" for lb in MIXED}


def test_no_dead_more_text(tmp_path):
    page = _render(tmp_path, MIXED)
    assert "earlier digests" not in page
    assert "archive-more" not in page


def test_scales_past_the_old_six_row_cut(tmp_path):
    """6 은 예전 상한이었다. 그 경계에서 조용히 잘리지 않는지 명시적으로 본다."""
    labels = [f"2026-W{i:02d}" for i in range(1, 31)]
    page = _render(tmp_path, labels)
    assert len(ROW_RE.findall(page)) == 30


def test_only_the_newest_row_is_highlighted(tmp_path):
    page = _render(tmp_path, MIXED)
    latest = [h for c, h in ROW_RE.findall(page) if "latest" in c]
    assert latest == ["2026-07-31.html"]


def test_weekly_label_does_not_outrank_daily_for_highlight(tmp_path):
    """'2026-W31' > '2026-07-31' 로 텍스트 정렬되는 함정(store.label_sort_key 주석) 가드.
    주간 라벨만 있는 경우엔 그 주가 최신이어야 한다."""
    page = _render(tmp_path, ["2026-W31", "2026-W30"])
    latest = [h for c, h in ROW_RE.findall(page) if "latest" in c]
    assert latest == ["2026-W31.html"]


def test_rows_are_newest_first(tmp_path):
    page = _render(tmp_path, MIXED)
    hrefs = [h for _c, h in ROW_RE.findall(page)]
    expected = [f"{r['date']}.html" for r in _digests(MIXED)]
    assert hrefs == expected


# ── 연도 그룹 ─────────────────────────────────────────────────────────────────

def test_year_groups_partition_every_row(tmp_path):
    page = _render(tmp_path, MIXED)
    groups = YEAR_RE.findall(page)
    assert [y for y, _n in groups] == ["2026", "2025", "2024", "2023"]
    assert sum(int(n) for _y, n in groups) == len(MIXED)


def test_week_label_is_grouped_by_its_iso_year(tmp_path):
    """'2026-W01' 의 월요일은 2025-12-29 다 — 라벨 앞 4자리가 아니라 실제 날짜로 묶는지."""
    page = _render(tmp_path, ["2026-W01"])
    assert YEAR_RE.findall(page) == [("2025", "1")]


# ── 헤드라인 문구 ─────────────────────────────────────────────────────────────

def test_headline_separates_weekly_from_daily(tmp_path):
    page = _render(tmp_path, MIXED)
    assert "10 digests" in page          # "10 weeks" 가 아니어야 한다
    assert "6 weekly" in page and "4 daily" in page


def test_daily_count_omitted_when_there_are_none(tmp_path):
    page = _render(tmp_path, ["2026-W31", "2026-W30"])
    assert "2 weekly" in page
    assert "daily" not in page


# ── 링크가 실제 페이지로 풀리는지 ─────────────────────────────────────────────

def test_links_resolve_to_files_rendered_beside_the_index(tmp_path):
    """href 는 archive/ 안 상대경로다. 실제로 그 자리에 페이지가 생기는지 함께 확인."""
    groups = [("model_releases", []), ("research", []),
              ("tools_products", []), ("policy_business", [])]
    for label in ["2026-W31", "2026-W30"]:
        render.render_archive_digest(label, groups, tmp_path)
    page = _render(tmp_path, ["2026-W31", "2026-W30"])
    index_dir = tmp_path / "archive"
    for _c, href in ROW_RE.findall(page):
        assert (index_dir / href).exists(), href


# ── store.is_week_label ───────────────────────────────────────────────────────

@pytest.mark.parametrize("label,expected", [
    ("2026-W31", True), ("2026-W01", True),
    ("2026-07-31", False), ("", False), ("2026-W3", False), ("2026-Www", False),
])
def test_is_week_label(label, expected):
    assert is_week_label(label) is expected
