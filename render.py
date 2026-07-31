"""HTML 렌더링: 오늘 다이제스트 + 카테고리 뷰 + 검색 + 아카이브(주간 리캡) + 아카이브 인덱스.

디자인: Claude Design(claude.ai/design) 프로젝트 "AI-Digest UI Redesign" 캔버스에서 포팅한
"Modernist" 컨셉 (2026-07-27 적용). Archivo 폰트 단일 사용, radius 0(완전히 각짐), 5색 팔레트
라이브 스위처(localStorage 저장). 카테고리별 섹션 대신 유의성 기준 플랫 랭킹(리드 스토리 1건 +
3열 그리드 + 목록 + in-brief) 구조. 이전 SIGNAL 디자인(시그널 미터/히어로 카드)은 폐기.

**2026-07-31 구조 변경(PROJECT_MEMO §13 T3.1)**: 이 파일에 문자열로 박혀 있던 Jinja 템플릿 5개와
CSS 6블록을 `templates/*.html` · `static/digest.css` 로 뺐다(1,069줄 -> 380줄). 이유는 하나뿐이다 —
디자인 개편(T3.3)을 1,000줄짜리 파이썬 파일에 머지하지 않으려고. **렌더 결과는 바뀌지 않았다**
(인라인 `<style>` 이 `<link rel=stylesheet>` 로 바뀐 것만. `tests/test_render_assets.py` 가 고정).

이제 이 파일은 **데이터 가공만** 한다: DB 행 -> 템플릿 변수. 마크업은 templates/, 스타일은 static/.

경로 규칙: 템플릿은 `asset_prefix` 로 CSS 를 찾는다("" = 루트 페이지, "../" = archive/ 안).
기존 `prefix` 변수와 **의미가 다르므로 섞지 말 것** — `prefix` 는 home/category 에서는 "루트까지",
archive_week 에서는 "archive 디렉터리까지"를 뜻한다(스레드 링크가 아카이브 형제를 가리키므로).
"""
from __future__ import annotations

import json
import re
from datetime import date as _date, datetime, timedelta as _timedelta, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from config import CATEGORY_LABELS, CATEGORY_ORDER
from store import is_week_label, label_sort_key


def group_by_category(items: list[dict], settings=None) -> list[tuple[str, list[dict]]]:
    """카테고리별 유의성 내림차순 그룹. community_takes 는 v1 제외.

    settings 를 주면 카테고리별 하한(min_significance) -> 상한(max_items) 순으로 적용한다
    (pipeline: 아직 안 잘린 풀). None 이면 정렬만 — rerender 는 DB 의 게재분을 읽는데
    그건 저장 시점에 이미 잘려 있어서 다시 자르면 이중 적용이 된다.
    하한을 상한보다 먼저 거는 이유: 자리가 남는다고 약한 항목이 올라오면 안 되기 때문
    (tools_products 는 후보가 2건뿐이라 캡만으로는 아무것도 못 거른다)."""
    groups: list[tuple[str, list[dict]]] = []
    for cat in CATEGORY_ORDER:
        if cat == "community_takes":
            continue
        picked = [it for it in items if it["category"] == cat]
        rule = settings.rule_for(cat) if settings is not None else None
        if rule is not None:
            picked = [it for it in picked if it["significance"] >= rule.min_significance]
        picked.sort(key=lambda it: (it["significance"], it.get("published") or ""), reverse=True)
        if rule is not None:
            picked = picked[: rule.max_items]
        groups.append((cat, picked))
    return groups

# ---- 팔레트 (Claude Design 캔버스의 라이브 컬러피커에서 포팅) ----
PALETTES = [
    {"name": "White · Cobalt", "g": "#ffffff", "g2": "#eef1fb", "bar": "#16182b", "ink": "#1e1b16",
     "ink2": "#4a4436", "muted": "#6b6355", "n1": "#9a917c", "n2": "#bdb49d", "acc": "#2438d6",
     "accd": "#1b2aa0", "acclt": "#8f9bf0", "grgb": "255,255,255", "inkrgb": "30,27,22"},
    {"name": "White · Teal", "g": "#ffffff", "g2": "#eef6f3", "bar": "#14201d", "ink": "#1a1d18",
     "ink2": "#3d4438", "muted": "#646b5b", "n1": "#909683", "n2": "#b9bfa9", "acc": "#0e7c6b",
     "accd": "#095e50", "acclt": "#5bbfae", "grgb": "255,255,255", "inkrgb": "26,29,24"},
    {"name": "White · Raspberry", "g": "#ffffff", "g2": "#fbeef2", "bar": "#1f0f16", "ink": "#1f1518",
     "ink2": "#4a3238", "muted": "#6e5157", "n1": "#8f7a80", "n2": "#c7b3ba", "acc": "#c2185b",
     "accd": "#8f0f41", "acclt": "#e8779e", "grgb": "255,255,255", "inkrgb": "31,21,24"},
    {"name": "White · Ember", "g": "#ffffff", "g2": "#fbf1ea", "bar": "#1f1c17", "ink": "#201d16",
     "ink2": "#463f33", "muted": "#6b6255", "n1": "#98907f", "n2": "#c0b8a6", "acc": "#c2410c",
     "accd": "#8f2f08", "acclt": "#f0a273", "grgb": "255,255,255", "inkrgb": "32,29,22"},
    {"name": "Mist · Signal red", "g": "#f3f2f2", "g2": "#eae9e9", "bar": "#201e1d", "ink": "#201e1d",
     "ink2": "#444141", "muted": "#605d5d", "n1": "#7d7979", "n2": "#bab6b6", "acc": "#ec3013",
     "accd": "#ae1800", "acclt": "#ff9783", "grgb": "243,242,242", "inkrgb": "32,30,29"},
]
DEFAULT_THEME = 4  # Mist · Signal red — styles.css 자체 기본값 + 기존 사이트 정체성과 가장 가까움

_PALETTES_JSON = json.dumps(PALETTES, ensure_ascii=False)


def _root_vars_css(palette: dict) -> str:
    decls = "".join(f"--{k}:{v};" for k, v in palette.items() if k != "name")
    return ":root{" + decls + "}"


TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
_env.globals.update(palettes=PALETTES, default_theme=DEFAULT_THEME, labels=CATEGORY_LABELS,
                    palettes_json=_PALETTES_JSON)

_assets_written: set[Path] = set()


def write_assets(output_dir: Path) -> Path:
    """`output/static/digest.css` 를 쓴다. = 기본 팔레트의 :root 블록 + static/digest.css.

    **:root 를 여기서 붙이는 이유**: 팔레트 5색의 원본은 `PALETTES`(파이썬)다. 테마 JS 가 그 값을
    읽어서 --var 를 덮어쓰고, 스위처 버튼도 같은 배열로 그린다. 기본 팔레트만 CSS 파일에 손으로
    복붙해두면 파이썬 쪽을 고칠 때 조용히 갈라진다 -> 배포 시점에 생성해서 원본을 하나로 유지한다.
    (`:root` 자체는 JS 가 꺼진 환경용 폴백. JS 가 살아 있으면 즉시 덮어써진다.)

    호출을 잊을 수 없도록 각 render_* 가 자기 시작에서 부른다 — 프로세스당 output_dir 하나에
    한 번만 실제로 쓴다(238개 페이지를 굽는 rerender 에서 같은 파일을 238번 쓰지 않기 위해)."""
    css_path = output_dir / "static" / "digest.css"
    if css_path in _assets_written and css_path.exists():
        return css_path
    authored = (STATIC_DIR / "digest.css").read_text(encoding="utf-8")
    css_path.parent.mkdir(parents=True, exist_ok=True)
    css_path.write_text(_root_vars_css(PALETTES[DEFAULT_THEME]) + authored, encoding="utf-8")
    _assets_written.add(css_path)
    return css_path

_SHORT_LABELS = {
    "model_releases": "Model", "research": "Research", "tools_products": "Tools",
    "policy_business": "Policy", "community_takes": "Community",
}

_DOMAIN_RE = re.compile(r"^https?://(?:www\.)?([^/]+)(/.*)?$")


def _domain_path(url: str, max_len: int = 42) -> str:
    m = _DOMAIN_RE.match(url or "")
    if not m:
        return url or ""
    text = (m.group(1) or "") + (m.group(2) or "")
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


def _tier(sig: float) -> str:
    if sig >= 0.6:
        return "major"
    if sig >= 0.4:
        return "high"
    if sig >= 0.3:
        return "mid"
    return "low"


def _source_line_name(it: dict) -> str:
    """멀티소스 클러스터면 '(+N more)' 를 붙인 표기.

    원본 이름을 `_source_base` 에 따로 보존한다. 같은 dict 이 홈과 카테고리 페이지에서 각각
    _annotate 되는데, 예전엔 접미사가 붙은 source_name 을 다시 입력으로 써서
    'TechCrunch (+1 more) (+2 more)' 처럼 누적됐다(접미사 붙은 이름은 cluster_sources 의
    어떤 값과도 안 맞아서 자기 자신까지 others 에 세어지는 바람에 숫자도 커졌음)."""
    base = it.setdefault("_source_base", it["source_name"])
    others = [s for s in it.get("cluster_sources", []) if s != base]
    return f"{base} (+{len(others)} more)" if others else base


def _annotate(it: dict, rank: int | None = None) -> None:
    it["domain_path"] = _domain_path(it["url"])
    it["tier_label"] = _tier(it.get("significance", 0.0))
    it["source_name"] = _source_line_name(it)
    # 표시용 제목은 headline 우선, 없으면 원제목. 한 군데서만 정하고 템플릿은 이것만 쓴다
    # (아카이브 415건은 headline 이 비어 있어서 그대로 원제목으로 나간다).
    it["display_title"] = (it.get("headline") or "").strip() or it["title"]
    # 앞 이야기. 호출부(pipeline/rerender)가 store.thread_parent_info 로 채워준 것만 쓴다 —
    # 부모는 보통 몇 달 전 다이제스트라 지금 렌더 중인 groups 안에 없다.
    parent = it.get("thread_parent")
    it["thread"] = parent if parent and parent.get("display") else None
    if rank is not None:
        it["rank"] = rank


def _flatten_ranked(groups: list[tuple[str, list[dict]]]) -> list[dict]:
    # 동점(significance 같음)일 때는 최신 발행이 앞. 이 tiebreak 이 없으면 stable sort 때문에
    # CATEGORY_ORDER 열거 순서가 리드 스토리를 결정해버림(model_releases 가 항상 이김).
    flat = [it for _cat, items in groups for it in items]
    flat.sort(key=lambda it: (it["significance"], it.get("published") or ""), reverse=True)
    return flat


def _period_meta(label: str, total: int) -> tuple[str, str]:
    """(메타 텍스트, '주'/'일' 같은 기간 단어) 반환."""
    m = re.match(r"^(\d{4})-W(\d{2})$", label)
    if m:
        year, week = int(m.group(1)), int(m.group(2))
        monday = _date.fromisocalendar(year, week, 1)
        sunday = monday + _timedelta(days=6)
        if monday.month == sunday.month:
            rng = f"{monday.day}–{sunday.day} {sunday.strftime('%B %Y')}"
        else:
            rng = f"{monday.strftime('%d %b')} – {sunday.strftime('%d %b %Y')}"
        return f"Week {week} · {rng} · {total} stories", "week"
    try:
        d = _date.fromisoformat(label)
        return f"{d.strftime('%A')} · {d.day} {d.strftime('%B %Y')} · {total} stories", "day"
    except ValueError:
        return f"{label} · {total} stories", "period"


def _nav_links(groups: list[tuple[str, list[dict]]], active_key: str, home_href: str,
              category_href_fn) -> list[dict]:
    total = sum(len(items) for _c, items in groups)
    links = [{"key": "home", "label": "Home", "count": total, "href": home_href, "active": active_key == "home"}]
    for cat, items in groups:
        links.append({
            "key": cat, "label": CATEGORY_LABELS[cat], "count": len(items),
            "href": category_href_fn(cat), "active": active_key == cat,
        })
    return links


_BAND_DEFS = [(0.6, "major", "acc"), (0.5, "high", "ink"), (0.4, "high", "muted"), (0.3, "mid", "n2")]


def _signal_bands(flat: list[dict]) -> list[dict]:
    counts = []
    for lo, tier, color_key in _BAND_DEFS:
        n = sum(1 for it in flat if lo <= it["significance"] < lo + 0.1)
        counts.append((lo, tier, color_key, n))
    max_n = max((n for *_r, n in counts), default=1) or 1
    return [
        {"score": f"{lo:.2f}", "tier": tier, "count": n, "pct": max(4, round(n / max_n * 100)),
         "color": f"var(--{color_key})"}
        for lo, tier, color_key, n in counts
    ]


def render_digest(date: str, groups: list[tuple[str, list[dict]]],
                  warnings: list[str], output_dir: Path, total_records: int = 0) -> Path:
    """오늘자 다이제스트: index.html(루트) + archive/{date}.html 동일 내용, 상대경로만 다르게.

    majors 파라미터는 2026-07-29 에 제거 — SIGNAL 디자인의 '상단 major 배너'용이었는데
    07-27 Modernist 개편에서 significance 플랫 랭킹으로 바뀌며 배너가 없어졌고, 이후로는
    받기만 하고 쓰지 않았음. major 표시는 지금도 항목별 `it.is_major` 태그로 나감."""
    flat = _flatten_ranked(groups)
    total = len(flat)
    for i, it in enumerate(flat, start=1):
        _annotate(it, rank=i)
    period_meta_txt, period_word = _period_meta(date, total)
    bands = _signal_bands(flat)

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = output_dir / "archive"
    archive_dir.mkdir(exist_ok=True)
    write_assets(output_dir)

    tmpl = _env.get_template("home.html")
    for in_archive, out_path in ((False, output_dir / "index.html"), (True, archive_dir / f"{date}.html")):
        # 오늘자 카테고리 페이지는 항상 루트에만 생성되므로(render_category_page 호출부 참고),
        # 아카이브 사본에서도 카테고리/홈 링크는 루트를 가리켜야 함(../ 접두).
        prefix = "../" if in_archive else ""
        home_href = f"{prefix}index.html"
        cat_href_fn = lambda c, p=prefix: f"{p}{c}.html"  # noqa: E731
        nav_links = _nav_links(groups, "home", home_href, cat_href_fn)
        archive_link = {
            "href": "index.html" if in_archive else "archive/index.html",
            "home_href": home_href,
            "count": total_records,
        }
        html = tmpl.render(
            period_meta=period_meta_txt, period_word=period_word, total_records=total_records,
            total=total, nav_links=nav_links, archive_link=archive_link,
            prefix=prefix, asset_prefix=("../" if in_archive else ""),
            search_href=("../search.html" if in_archive else "search.html"),
            lead=flat[0] if flat else None, grid3=flat[1:4], worth=flat[4:8], brief=flat[8:],
            short_labels=_SHORT_LABELS, bands=bands, warnings=warnings,
        )
        out_path.write_text(html, encoding="utf-8")
    return archive_dir / f"{date}.html"


def render_archive_digest(label: str, groups: list[tuple[str, list[dict]]],
                          output_dir: Path, recap: dict | None = None, total_records: int = 0) -> Path:
    """백필/재렌더용 주간 리캡 페이지: archive/{label}.html (1f 디자인 — 헤드라인+통계밴드)."""
    flat = _flatten_ranked(groups)
    total = len(flat)
    for i, it in enumerate(flat, start=1):
        _annotate(it, rank=i)
    period_meta_txt, period_word = _period_meta(label, total)
    recap = recap or {}
    headline = recap.get("headline") or f"{period_meta_txt.split(' · ')[0]} digest"
    peak_sig = max((it["significance"] for it in flat), default=0.0)
    model_release_count = sum(1 for it in flat if it["category"] == "model_releases")

    archive_dir = output_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    write_assets(output_dir)
    tmpl = _env.get_template("archive_week.html")
    html = tmpl.render(
        label=label, period_meta=period_meta_txt, period_word=period_word, headline=headline,
        total=total, peak_sig=peak_sig, model_release_count=model_release_count,
        dollar_committed=recap.get("dollar_committed"),
        lead=flat[0] if flat else None, second=flat[1] if len(flat) > 1 else None, rest=flat[2:],
        # prefix="" 는 "archive 디렉터리 기준"(스레드 링크가 아카이브 형제를 가리킨다).
        # asset_prefix 는 루트 기준이라 항상 "../" — 이 페이지는 archive/ 안에만 있다.
        prev_label=None, prefix="", asset_prefix="../",
    )
    (archive_dir / f"{label}.html").write_text(html, encoding="utf-8")
    return archive_dir / f"{label}.html"


def render_category_page(period_label: str, category: str, groups: list[tuple[str, list[dict]]],
                         output_dir: Path, in_archive: bool, one_liner: str = "",
                         cap: int = 6, min_sig: float = 0.25, total_records: int = 0) -> Path:
    """카테고리 필터 뷰: 오늘은 {category}.html(루트), 과거 주는 archive/{label}-{category}.html."""
    items = next((its for c, its in groups if c == category), [])
    # 동점 처리는 group_by_category/_flatten_ranked 와 같은 키로 — 안 맞추면 홈과 카테고리
    # 페이지의 같은 점수 항목 순서가 갈린다.
    items = sorted(items, key=lambda it: (it["significance"], it.get("published") or ""), reverse=True)
    row_sizes = [34, 28, 22, 17, 15, 15]
    for i, it in enumerate(items):
        _annotate(it)
        it["row_size"] = row_sizes[i] if i < len(row_sizes) else row_sizes[-1]
        it["show_dek"] = i < 2

    total = sum(len(its) for _c, its in groups)
    period_meta_txt, period_word = _period_meta(period_label, total)
    major_count = sum(1 for it in items if it["is_major"])
    source_counts: dict[str, int] = {}
    for it in items:
        source_counts[it["source_name"]] = source_counts.get(it["source_name"], 0) + 1
    top_source = None
    if source_counts:
        name, cnt = max(source_counts.items(), key=lambda kv: kv[1])
        top_source = {"name": name, "count": cnt}

    home_href = (f"{period_label}.html" if in_archive else "index.html")
    cat_href_fn = (lambda c: f"{period_label}-{c}.html") if in_archive else (lambda c: f"{c}.html")
    nav_links = _nav_links(groups, category, home_href, cat_href_fn)
    archive_link = {
        "href": ("index.html" if in_archive else "archive/index.html"),
        "home_href": ("../index.html" if in_archive else "index.html"),
        "count": total_records,
    }

    if in_archive:
        out_path = output_dir / "archive" / f"{period_label}-{category}.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        search_href = "../search.html"
        archive_link["href"] = "index.html"
    else:
        out_path = output_dir / f"{category}.html"
        output_dir.mkdir(parents=True, exist_ok=True)
        search_href = "search.html"
    write_assets(output_dir)

    tmpl = _env.get_template("category.html")
    html = tmpl.render(
        category=category, one_liner=one_liner or f"{CATEGORY_LABELS[category]} this {period_word}.",
        items=items, major_count=major_count, top_source=top_source, cap=cap, min_sig=min_sig,
        period_meta=period_meta_txt, period_word=period_word, total_records=total_records,
        nav_links=nav_links, archive_link=archive_link, prefix=("../" if in_archive else ""),
        search_href=search_href, asset_prefix=("../" if in_archive else ""),
    )
    out_path.write_text(html, encoding="utf-8")
    return out_path


def render_search_page(items: list[dict], output_dir: Path):
    """전체 히스토리 검색 페이지(search.html). fetch() 는 file:// 로컬 실행 시 CORS 로 막히므로
    전체 인덱스를 <script type="application/json"> 로 인라인 임베드 — 로컬/호스팅 둘 다 동작."""
    data = [
        {
            "t": it["title"],
            "u": it["url"],
            "s": it.get("source_name", it.get("source_id", "")),
            "d": it.get("digest_date", ""),
            "sig": round(it.get("significance", 0.0), 2),
            "sm": (it.get("summary") or "")[:200],
        }
        for it in items
    ]
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_assets(output_dir)
    tmpl = _env.get_template("search.html")
    html = tmpl.render(total=len(data), data_json=data_json, asset_prefix="")
    (output_dir / "search.html").write_text(html, encoding="utf-8")


def _feed_pub_date(label: str) -> str:
    """다이제스트 라벨 -> RSS 의 RFC 822 pubDate. 파싱 못 하면 ''(그러면 템플릿이 생략한다).

    주간 라벨('2026-W31')은 `label_sort_key` 가 그 주 월요일 ISO 날짜를 주므로 그걸 쓴다 —
    일간/주간이 한 피드에 섞여도 리더에서 시간순이 맞는다."""
    iso = label_sort_key(label)
    try:
        d = _date.fromisoformat(iso)
    except ValueError:
        return ""
    return format_datetime(datetime(d.year, d.month, d.day, tzinfo=timezone.utc))


def _feed_body_html(entry: dict) -> str:
    """피드 본문: 그날 항목을 랭킹 순서대로 <ol>. 리더 안에서 다이제스트를 그대로 읽게 한다.

    템플릿의 autoescape 가 이 문자열을 이스케이프해서 description 에 넣는다(RSS 규약).
    그래서 여기서는 **평범한 HTML 을 만들면 되고, 직접 이스케이프하지 않는다** — 단
    항목 제목/요약은 원문이라 여기서 escape() 를 걸어야 한다(이중 이스케이프가 아니다:
    이 함수의 출력 전체가 description 안에서 한 번 더 이스케이프되는 구조).
    """
    parts: list[str] = []
    if entry.get("headline"):
        parts.append(f"<p><strong>{escape(entry['headline'])}</strong></p>")
    parts.append("<ol>")
    for it in entry.get("items", []):
        title = escape((it.get("headline") or "").strip() or it.get("title") or "")
        url = escape(it.get("url") or "", quote=True)
        summary = escape(it.get("summary") or "")
        label = escape(CATEGORY_LABELS.get(it.get("category", ""), ""))
        major = " <em>(major)</em>" if it.get("is_major") else ""
        parts.append(
            f'<li><a href="{url}">{title}</a>{major}<br>'
            f"<small>{label}</small>"
            f"{'<br>' + summary if summary else ''}</li>"
        )
    parts.append("</ol>")
    return "".join(parts)


def render_feed(entries: list[dict], output_dir: Path, site_url: str,
                build_date: str | None = None) -> Path | None:
    """`output/feed.xml` (RSS 2.0). **다이제스트 1개 = item 1개.**

    `site_url` 이 비어 있으면 **만들지 않고 None 을 반환한다** — RSS 는 상대경로를 허용하지
    않아서, 기준 URL 없이 쓰면 리더에서 전 링크가 깨진 피드가 배포된다. 조용히 깨진 걸
    내보내는 것보다 없는 게 낫다(sources.yaml settings.site_url 참고).

    `build_date` 는 테스트에서 고정하기 위한 것 — 안 주면 지금 시각."""
    if not site_url:
        print("      [!] settings.site_url 이 비어 있어 RSS 피드를 건너뜀 "
              "(RSS 는 상대경로 불가 — sources.yaml 에 배포 주소를 넣을 것)")
        return None
    base = site_url.rstrip("/")
    payload = [
        {
            "label": e["label"],
            "title": e.get("headline") or f"AI Digest — {e['label']}",
            "pub_date": _feed_pub_date(e["label"]),
            "body_html": _feed_body_html(e),
        }
        for e in entries
    ]
    tmpl = _env.get_template("feed.xml")
    xml = tmpl.render(site_url=base, entries=payload,
                      build_date=build_date or format_datetime(datetime.now(timezone.utc)))
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "feed.xml"
    out.write_text(xml, encoding="utf-8")
    return out


def render_archive_index(digests: list[dict], output_dir: Path):
    # 볼륨 미니바는 시간순이어야 하는데 date 를 텍스트 정렬하면 주간 라벨('2026-W31')이
    # 'W'(0x57) > '0'(0x30) 때문에 모든 일간 날짜보다 뒤로 가서, 막대 순서도 틀리고
    # 마지막 원소를 '최신'으로 강조하는 것도 엉뚱한 걸 집는다. store 와 같은 키를 쓴다.
    ordered_asc = sorted(digests, key=lambda d: label_sort_key(d["date"]))
    max_count = max((d["item_count"] for d in digests), default=1) or 1
    bars = []
    for i, d in enumerate(ordered_asc):
        pct = max(6, round(d["item_count"] / max_count * 100))
        is_latest = i == len(ordered_asc) - 1
        color = "var(--acc)" if is_latest else ("var(--ink)" if pct >= 70 else
                ("var(--muted)" if pct >= 40 else "var(--n1)"))
        bars.append({"pct": pct, "color": color})

    # 2026-07-31(§13 T3.2): 예전엔 `digests[:6]` 만 링크하고 나머지는 "+41 earlier digests"
    # 라는 **죽은 텍스트**로 끝났다. 6개월 백필로 만든 43주치가 사이트 안에서 도달 불가였고
    # (검색이나 URL 직접 입력 말고는 길이 없었다) 그건 아카이브가 있다고 할 수 없다.
    # 47행은 페이지네이션이 필요한 양이 아니므로 전부 싣고, 연도로만 묶어 스캔을 돕는다.
    for i, d in enumerate(digests):
        d["bar_px"] = max(6, round(d["item_count"] / max_count * 68))
        d["bar_color"] = "var(--acc)" if i == 0 else "var(--muted)"
        d["is_latest"] = i == 0   # 강조 대상은 파이썬에서 표시한다(중첩 루프에서 판정하지 않기)

    years: list[dict] = []
    for d in digests:      # digests 는 store.list_digests() 가 label_sort_key 로 내림차순 정렬
        year = label_sort_key(d["date"])[:4] or d["date"][:4]
        if not years or years[-1]["year"] != year:
            years.append({"year": year, "digests": []})
        years[-1]["digests"].append(d)

    # "47 weeks of signal" 은 틀린 문구였다 — 일간 4건이 섞여 있다(주간은 백필, 일간은 라이브).
    weekly = sum(1 for d in digests if is_week_label(d["date"]))
    daily = len(digests) - weekly

    (output_dir / "archive").mkdir(parents=True, exist_ok=True)
    write_assets(output_dir)
    tmpl = _env.get_template("archive_index.html")
    html = tmpl.render(digests=digests, bars=bars, years=years,
                       weekly_count=weekly, daily_count=daily, asset_prefix="../")
    (output_dir / "archive" / "index.html").write_text(html, encoding="utf-8")
