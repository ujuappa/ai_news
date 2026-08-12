"""HTML 렌더링: 오늘 다이제스트 + 카테고리 뷰 + 검색 + 아카이브(주간 리캡) + 아카이브 인덱스.

디자인: Claude Design(claude.ai/design) 프로젝트 "AI-Digest UI Redesign" 캔버스에서 포팅한
"Modernist" 컨셉 (2026-07-27 적용). Archivo 폰트 단일 사용, radius 0(완전히 각짐), 5색 팔레트
라이브 스위처(localStorage 저장). 카테고리별 섹션 대신 유의성 기준 플랫 랭킹(리드 스토리 1건 +
3열 그리드 + 목록 + in-brief) 구조. 이전 SIGNAL 디자인(시그널 미터/히어로 카드)은 폐기.

**2026-07-31 구조 변경(PROJECT_MEMO §13 T3.1)**: 이 파일에 문자열로 박혀 있던 Jinja 템플릿 5개와
CSS 6블록을 `templates/*.html` · `static/digest.css` 로 뺐다(1,069줄 -> 380줄). 이유는 하나뿐이다 —
디자인 개편(T3.3)을 1,000줄짜리 파이썬 파일에 머지하지 않으려고. **렌더 결과는 바뀌지 않았다**
(인라인 `<style>` 이 `<link rel=stylesheet>` 로 바뀐 것만. `tests/test_render_assets.py` 가 고정).

**2026-08-03 디자인 2차 개편(Claude Design "AI Digest - Home" 캔버스)**: 홈이 신문 1면 레이아웃으로
바뀌었다 — 라이트 마스트헤드(큰 워드마크 + 검색 + 탭 네비), 카테고리 필터 pill(클라이언트 사이드),
이미지 슬롯이 있는 리드 스토리, "Also today" 3열 카드, "Worth knowing" 썸네일 행, "In brief" 목록,
사이드바(Signal index + Source alert), 테마 스위처가 푸터로 이동. 사인인/주간/월간은 **미구현이라
의도적으로 뺐다**(사용자 지시 2026-08-03) — 나중에 붙일 자리만 남겨둠.

**이미지**: 캔버스 디자인은 스토리마다 마크를 쓴다. 어떤 마크인지는 `images.resolve()` 가 정하고
(LLM 이 고른 주체 -> 수집 소스 -> 카테고리 제네릭 순), 카탈로그는 `static/img/` 의 파일 목록이다.
맞는 파일이 하나도 없으면 같은 크기의 빈 플레이스홀더가 자리를 지킨다 -> 레이아웃이 안 흔들린다.

이제 이 파일은 **데이터 가공만** 한다: DB 행 -> 템플릿 변수. 마크업은 templates/, 스타일은 static/.

경로 규칙: 템플릿은 `asset_prefix` 로 CSS 를 찾는다("" = 루트 페이지, "../" = archive/ 안).
기존 `prefix` 변수와 **의미가 다르므로 섞지 말 것** — `prefix` 는 home/category 에서는 "루트까지",
archive_week 에서는 "archive 디렉터리까지"를 뜻한다(스레드 링크가 아카이브 형제를 가리키므로).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date as _date, datetime, timedelta as _timedelta, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import config
import images
from config import CATEGORY_LABELS, CATEGORY_ORDER, TOPIC_LABELS, TOPIC_ORDER
from store import DEAD_LINK_STATUSES, is_week_label, label_sort_key


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
    # 2026-08-06, 캔버스 "Home Top Organization" 6a 에서. 6a 의 maroon 은 링크색이라 --accd,
    # 워드마크 옆 빨간 점은 --acc 다(digest.css `.mh-dot` 이 --acc 를 쓴다 → Mist 에서는
    # 시그널 레드로 나온다).
    # 2026-08-07: 처음엔 6a 에서 **색만** 들여왔지만(폰트/radius 는 전역이라), 사용자 결정으로
    # 조판(Mona Sans + Playfair · radius 16/12/999 · 그림자)까지 전면 도입했다. 그 셋은
    # 팔레트가 아니라 전역이므로 여기가 아니라 digest.css 끝의 "Boncom 시스템" 레이어에 있다 —
    # 즉 팔레트를 Mist 로 바꿔도 조판은 Boncom 그대로다(색만 갈린다).
    {"name": "Boncom · Maroon", "g": "#f4f2ec", "g2": "#edeae1", "bar": "#1a1a1a", "ink": "#1a1a1a",
     "ink2": "#575753", "muted": "#6e6d6a", "n1": "#8c8b87", "n2": "#c9c7c0", "acc": "#ff1a22",
     "accd": "#4a0e1f", "acclt": "#ffb3b6", "grgb": "244,242,236", "inkrgb": "26,26,26"},
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
    # 이 사이트의 .js 파일 두 개. 인라인이 아닌 이유가 각각 있다:
    #   admin_rules.js — `config._apply_overlay` 의 사본이라 tests/test_admin.py 가 node 로
    #                    돌려서 파이썬과 같은 픽스처로 대조한다. 인라인이면 자동화 불가.
    #   follow.js      — 지면 5종이 공유한다. 매크로로 인라인하면 같은 코드가 5번 실려서
    #                    브라우저 캐시가 안 먹고, 필터 스크립트가 갈라졌던 사고를 반복한다
    #                    (macros.topic_filter_script 주석: 두 벌로 두면 또 갈라진다).
    #   comments.js    — 댓글 레일. follow 와 같은 이유로 자산 파일이다.
    for asset in ("admin_rules.js", "follow.js", "comments.js"):
        (css_path.parent / asset).write_text(
            (STATIC_DIR / asset).read_text(encoding="utf-8"), encoding="utf-8")
    images.copy_to(css_path.parent)
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


def _domain(url: str) -> str:
    """호스트만. 홈의 'Read at bbc.co.uk →' 용 — 여기에 경로까지 넣으면
    `bbc.co.uk/news/articles/cr7k49xjzzeo?at_m…` 같은 쿼리스트링이 그대로 노출된다."""
    m = _DOMAIN_RE.match(url or "")
    return m.group(1) if m else (url or "")


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


def _digest_ref(label: str) -> datetime:
    """상대시간("4h ago")의 기준 시각. **지금이 아니라 그 다이제스트의 시각이다.**

    오늘자면 now, 과거 다이제스트면 그날 23:59 UTC. 기준을 항상 now 로 잡으면 rerender 할 때마다
    아카이브 사본의 "4h ago" 가 "6d ago" 로 늘어나서 그날의 페이지가 아니게 된다."""
    now = datetime.now(timezone.utc)
    try:
        d = _date.fromisoformat(label)
    except ValueError:
        return now
    return min(now, datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc))


_REL_UNITS = [(60, "m", "minute"), (24, "h", "hour"), (7, "d", "day"), (5, "w", "week")]


def _relative_time(published: str | None, ref: datetime | None, long: bool = False) -> str:
    """'9h ago' / '9 hours ago'. 파싱 불가·미래면 ''(템플릿이 통째로 생략한다)."""
    if not published or ref is None:
        return ""
    try:
        dt = datetime.fromisoformat(published)
    except (TypeError, ValueError):
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    value = (ref - dt).total_seconds() / 60
    if value < 0:
        return ""
    for limit, short, word in _REL_UNITS:
        if value < limit:
            n = max(1, int(value))
            return f"{n} {word}{'s' if n != 1 else ''} ago" if long else f"{n}{short} ago"
        value /= limit
    return "older"


def _annotate(it: dict, rank: int | None = None, ref: datetime | None = None) -> None:
    it["domain_path"] = _domain_path(it["url"])
    it["domain"] = _domain(it["url"])
    # 죽은 링크는 href 를 떼서 못 누르게 한다(templates/macros.html `href`). 판정은 렌더가
    # 하지 않는다 — linkcheck.py 가 미리 찔러 본 결과(items.link_status)를 읽기만 한다.
    # 값이 없으면(미점검/구 DB) 살아있는 것으로 본다.
    it["url_dead"] = (it.get("link_status") or "") in DEAD_LINK_STATUSES
    # 홈 필터용. 어휘에 없는 값은 여기서 떨군다 — 옛 DB 행이나 손으로 넣은 값이 섞이면
    # 어떤 pill 에도 안 걸리는 유령 토픽이 DOM 에만 남는다.
    it["topics"] = [t for t in TOPIC_ORDER if t in set(it.get("topics") or [])]
    it["topic_attr"] = " ".join(it["topics"])
    it["tier_label"] = _tier(it.get("significance", 0.0))
    it["source_name"] = _source_line_name(it)
    # 디자인의 바이라인은 "출처명 · N sources · 9h ago" 라서 접미사 없는 원본 이름과 소스 수가
    # 따로 필요하다. source_name('X (+2 more)')은 카테고리 페이지가 계속 쓰므로 건드리지 않는다.
    it["source_base"] = it["_source_base"]
    it["source_count"] = len({it["_source_base"], *it.get("cluster_sources", [])})
    it["rel_time"] = _relative_time(it.get("published"), ref)
    it["rel_time_long"] = _relative_time(it.get("published"), ref, long=True)
    it["image"] = images.resolve(it.get("image_key", ""), it.get("source_id", ""),
                                 it.get("category", ""))
    # 슬롯 맞춤 방식은 전역 상수 하나지만 **아이템에 실어 보낸다** — Jinja 는 `{% import %}` 한
    # 매크로 모듈을 처음 렌더할 때 만들어 캐시하므로, 환경 전역으로 두면 그 시점 값이 굳는다.
    it["image_fit"] = images.IMAGE_FIT
    # SVG 마크는 인라인해야 팔레트 색을 탄다(images.inline_svg 주석). 래스터 로고는 None.
    it["image_svg"] = images.inline_svg(it["image"])
    # 표시용 제목은 headline 우선, 없으면 원제목. 한 군데서만 정하고 템플릿은 이것만 쓴다
    # (아카이브 415건은 headline 이 비어 있어서 그대로 원제목으로 나간다).
    it["display_title"] = (it.get("headline") or "").strip() or it["title"]
    # 저장(북마크) 키. `items.id` 가 원본이고, 없으면 URL 로 떨어진다.
    # **폴백이 필요한 이유**: 저장은 이 값으로 항목을 구분하는데, 비어 있으면 저장한 기사
    # 전부가 같은 키(`""`)를 공유해서 하나만 남는다 — 조용하고 찾기 어려운 종류의 고장이다.
    # 실제 파이프라인/DB 경로는 언제나 id 를 싣지만(store._row_to_item), 합성 데이터나
    # 옛 행이 섞이는 자리라 여기서 막는다.
    it["save_key"] = str(it.get("id") or it.get("url") or "")
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
              category_href_fn, home_label: str = "Today") -> list[dict]:
    total = sum(len(items) for _c, items in groups)
    links = [{"key": "home", "label": home_label, "count": total, "href": home_href,
              "active": active_key == "home"}]
    for cat, items in groups:
        links.append({
            "key": cat, "label": CATEGORY_LABELS[cat], "count": len(items),
            "href": category_href_fn(cat), "active": active_key == cat,
        })
    return links


def _topic_filters(items: list[dict], total: int, cap: int | None = None) -> list[dict]:
    """필터 목록 — **카테고리가 아니라 토픽**이다(2026-08-04).

    카테고리 pill 은 상단 네비게이션과 같은 4개를 그대로 반복해서 자리값을 못 했다.
    토픽은 "무엇에 관한 이야기인가"라는 다른 축이라 필터로서 실제로 쓸모가 있다.

    **상한이 없어진 이유(2026-08-06, 캔버스 6a)**: 예전엔 top-6 만 냈다 — 하루치에 토픽이
    8~9개 붙는데 pill 을 한 줄에 늘어놓으니 줄이 넘쳐서였다. 6a 는 그 줄을 `Filters` 버튼 +
    서랍으로 바꿨고, 서랍은 몇 개가 들어와도 넘치지 않는다. 그래서 상한의 이유가 없어졌다 —
    이제 그날 붙은 토픽 전부가 서랍에 들어간다(1건짜리 토픽도 고를 수 있다).
    `cap` 은 남겨 뒀지만 기본값은 무제한이다.

    동점은 TOPIC_ORDER 순으로 깬다 — 안 그러면 같은 데이터로 재렌더할 때 pill 순서가 흔들린다.
    빈 토픽은 애초에 counts 에 없으니 "눌러도 아무것도 안 남는 버튼"은 생기지 않는다."""
    counts = Counter(t for it in items for t in (it.get("topics") or []))
    order = {t: i for i, t in enumerate(TOPIC_ORDER)}
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], order.get(kv[0], len(order))))
    pills = [{"key": "all", "label": "All", "count": total}]
    pills += [{"key": key, "label": TOPIC_LABELS.get(key, key), "count": n}
              for key, n in (ranked if cap is None else ranked[:cap]) if key in TOPIC_LABELS]
    return pills


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
    ref = _digest_ref(date)
    for i, it in enumerate(flat, start=1):
        _annotate(it, rank=i, ref=ref)
    period_meta_txt, period_word = _period_meta(date, total)
    # 날짜 칩은 "Tuesday · 4 August 2026" 만 담는다 — 건수·랭크 라벨은 2026-08-12 에 뗐다.
    period_date = period_meta_txt.rsplit(" · ", 1)[0]
    bands = _signal_bands(flat)
    grid3, worth, brief = flat[1:4], flat[4:8], flat[8:]

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
            lead=flat[0] if flat else None, grid3=grid3, worth=worth, brief=brief,
            # Wire 티커(6a, 2026-08-07): 리드와 카드 3장 아래로 떨어진 것 **전부**.
            # 자르지 않는다 — 재생 시간이 항목 수를 따라가므로(macros.wire_ticker) 길어져도
            # 속도가 그대로고, 여기서 top-N 을 자르면 "아래 것들"이 조용히 빠진다.
            wire=flat[4:],
            short_labels=_SHORT_LABELS, bands=bands, warnings=warnings,
            filters=_topic_filters(flat, total), period_date=period_date,
            # 같은 본문을 루트(index.html)와 아카이브 사본에 굽는다. 디스플레이 제목만
            # 갈라 놓는다 — 몇 달 뒤에 아카이브 사본을 열었을 때 "Today's news" 는 거짓말이다.
            head_lead=("Today's news" if not in_archive else "That day's news"),
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
        # 홈과 같은 토픽 pill. 2026-08-04 이전엔 아카이브에 필터 줄이 아예 없었다.
        filters=_topic_filters(flat, total),
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
    ref = _digest_ref(period_label)
    for i, it in enumerate(items):
        _annotate(it, ref=ref)
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
    nav_links = _nav_links(groups, category, home_href, cat_href_fn,
                           home_label="Digest" if in_archive else "Today")
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
            # 죽은 링크만 표시(있을 때만 키를 넣어 인덱스가 불필요하게 커지지 않게).
            # 검색에서는 여전히 찾을 수 있어야 한다 — 글이 없어진 게 아니라 링크가 죽은 것.
            **({"x": 1} if (it.get("link_status") or "") in DEAD_LINK_STATUSES else {}),
        }
        for it in items
    ]
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_assets(output_dir)
    tmpl = _env.get_template("search.html")
    html = tmpl.render(total=len(data), data_json=data_json, asset_prefix="")
    (output_dir / "search.html").write_text(html, encoding="utf-8")


# 소스 페이지에서 "이 소스가 살아 있는가"를 한 단어로 말하는 판정. `status`(사람이 적어둔
# 기대값)와 **다른 축**이라 섞지 말 것 — status 는 "피드가 있다고 믿는다", 아래는 "실제로
# 지면에 올랐다"다. 2026-07-31 에 소스를 손으로 셀 때 실제로 쓴 구분이 이거였다.
def _source_health(src, stat: dict) -> tuple[str, str]:
    """(키, 사람이 읽는 한 줄). 키는 CSS 클래스 접미사로도 쓰인다."""
    if not src.enabled:
        return "off", "Disabled — not fetched"
    published, dropped = stat.get("published", 0), stat.get("dropped", 0)
    if published:
        return "live", f"{published} published"
    if dropped:
        # 피드는 살아 있다. 신호가 하한/상한에 계속 걸리는 것 — 소스를 지울지 판단할 때
        # "죽었다"와 완전히 다른 사례다(arxiv_lg 가 198건 탈락 3건 게재다).
        return "quiet", f"Fetching, but {dropped} items all fell below the cut"
    return "silent", "No items collected yet — feed may be dead"


def render_sources_page(sources: list, stats: dict[str, dict], output_dir: Path,
                        total_records: int = 0, repo: str = "") -> Path:
    """`output/sources.html` — 소스 디렉터리(**읽기 전용**).

    편집은 여기가 아니라 `admin.html` 이 한다. 정적 페이지는 GitHub Pages 에서 서빙되는
    죽은 HTML 이라 `sources.yaml` 을 쓸 방법이 없다 — 쓰기는 브라우저가 GitHub Contents
    API 를 직접 부르는 admin 페이지 몫이고, 이 페이지는 그 결과를 보여주는 곳이다.

    수치는 config(무엇을 수집하기로 했나)와 DB(실제로 뭐가 올랐나)를 합쳐서 낸다. 둘 중
    하나만으로는 소스를 지울지 판단할 수 없다.
    """
    by_cat: dict[str, list[dict]] = {}
    for src in sources:
        stat = stats.get(src.id, {})
        health_key, health_note = _source_health(src, stat)
        by_cat.setdefault(src.category, []).append({
            "id": src.id, "name": src.name, "category": src.category,
            "feed_url": src.feed_url, "feed_display": _domain_path(src.feed_url, 52),
            "parse": src.parse, "status": src.status, "enabled": src.enabled,
            "full_text": src.full_text, "max_entries": src.max_entries,
            "sitemap_paths": src.sitemap_paths, "notes": src.notes,
            "published": stat.get("published", 0), "dropped": stat.get("dropped", 0),
            "last_date": stat.get("last_date", ""),
            "avg_significance": stat.get("avg_significance"),
            "health": health_key, "health_note": health_note,
        })
    groups = [{"key": cat, "label": CATEGORY_LABELS[cat], "sources": by_cat[cat]}
              for cat in CATEGORY_ORDER if by_cat.get(cat)]

    # DB 에는 있지만 설정에 없는 source_id. 지금은 `gemini_grounding`(그라운딩 보조 항목은
    # 소스가 아니라 LLM 검색에서 온다)이 여기 걸린다. 숨기면 소스별 합이 아카이브 총계와
    # 안 맞는 이유를 아무도 설명할 수 없게 되므로 따로 적는다.
    known = {s.id for s in sources}
    orphans = [{"id": sid, **stats[sid]} for sid in sorted(stats)
               if sid not in known and stats[sid].get("published")]

    enabled = [s for s in sources if s.enabled]
    summary = [
        {"num": len(sources), "label": "Configured"},
        {"num": len(enabled), "label": "Enabled"},
        {"num": sum(1 for s in enabled if _source_health(s, stats.get(s.id, {}))[0] == "live"),
         "label": "Producing"},
        {"num": total_records, "label": "In archive"},
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    write_assets(output_dir)
    html = _env.get_template("sources.html").render(
        groups=groups, orphans=orphans, summary=summary, total_records=total_records,
        asset_prefix="", search_href="search.html", repo=repo,
        parse_kinds=_PARSE_KINDS,
    )
    out_path = output_dir / "sources.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


# `fetch.fetch_source_counted` 의 분기와 **같이 유지해야 한다**. admin 의 드롭다운이 이 목록을
# 쓰는데, 여기 없는 값을 고르면 fetch 가 조용히 기본(RSS) 분기로 떨어진다.
_PARSE_KINDS = [
    {"key": "easy", "label": "easy — clean RSS/Atom"},
    {"key": "medium", "label": "medium — RSS that breaks sometimes"},
    {"key": "hard", "label": "hard — scraping/transcripts"},
    {"key": "sitemap", "label": "sitemap — scrape sitemap.xml"},
    {"key": "gnews", "label": "gnews — Google News query"},
    {"key": "hf_papers", "label": "hf_papers — HuggingFace daily papers"},
]

_SOURCE_STATUSES = ["verified", "verify", "no_feed"]


def render_saved_page(output_dir: Path, total_records: int = 0) -> Path:
    """`output/saved.html` — 저장한 기사 · 팔로우한 토픽 · 저장한 필터.

    **서버는 이 페이지의 내용을 모른다.** 저장/팔로우는 브라우저 localStorage 에만 있고
    (계정도 서버도 없다), 여기서 굽는 것은 빈 껍데기 + 토픽 어휘뿐이다. 목록은 follow.js 가
    그린다. 그래서 이 페이지는 렌더 시점 데이터가 없어 rerender 마다 바이트가 같다.

    토픽 어휘를 구워 보내는 이유: 저장한 항목에는 토픽 **키**만 들어 있어서(`chips`),
    사람이 읽는 라벨(`Chips & datacenters`)로 바꿀 표가 필요하다. 프리셋 편집기의 선택
    목록도 같은 표를 쓴다.
    """
    topics, _cap = config.load_topics()
    output_dir.mkdir(parents=True, exist_ok=True)
    write_assets(output_dir)
    html = _env.get_template("saved.html").render(
        asset_prefix="", total_records=total_records,
        topics=[{"key": t.key, "label": t.label} for t in topics],
        topics_json=json.dumps({t.key: t.label for t in topics}, ensure_ascii=False),
    )
    out_path = output_dir / "saved.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _read_json(path: Path, default: dict) -> dict:
    """기계 소유 JSON 읽기. 없거나 깨졌으면 default — admin 지면은 떠야 한다."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    return data if isinstance(data, dict) else default


def render_admin_page(output_dir: Path, repo: str = "") -> Path:
    """`output/admin.html` — 소스·토픽 편집기. **브라우저가 GitHub API 로 직접 커밋한다.**

    이 페이지에 비밀값은 **하나도 들어가지 않는다.** 쓰기에 필요한 PAT 은 사용자가 런타임에
    입력하고 그 브라우저의 localStorage 에만 머문다 → 배포 산출물과 레포에는 토큰이 없고,
    이 URL 을 남이 열어도 토큰이 없으니 읽기 폼만 보인다. (사용자 결정 2026-08-11: 로컬
    admin 서버가 아니라 GitHub API 경로. 유일하게 안전한 형태가 이거다 — 산출물에 토큰을
    구우면 공개 레포에서 그대로 유출된다. PROJECT_MEMO §10.5 의 키 노출 3회 참고.)

    편집 대상은 기계 소유 JSON 두 개다(`sources.custom.json` · `topics.json`).
    `sources.yaml` 은 건드리지 않는다 — 주석 240줄을 클라이언트가 날려먹지 않게.

    **베이스 상태를 페이지에 구워 넣는 이유**: 토큰 없이 열었을 때도 지금 설정을 볼 수 있어야
    하고, 오버레이 미리보기를 서버(파이썬)의 병합 규칙과 같은 입력으로 계산해야 한다.
    실제 편집은 연결 직후 GitHub 에서 **라이브 파일을 다시 읽어** 시작한다 — 구운 값으로
    저장하면 지난 편집을 조용히 되돌린다(push 트리거는 렌더를 다시 하지 않으므로 이 페이지의
    구운 값은 얼마든지 낡을 수 있다).
    """
    base = config.load(overlay=None)
    topics, max_per_item = config.load_topics()
    overlay = _read_json(config.CUSTOM_SOURCES_FILE, {"sources": []})
    topics_doc = _read_json(config.TOPICS_FILE, {})

    baked = {
        "repo": repo,
        "baseSources": [config._row_of(s) for s in base.sources],
        "overlay": overlay,
        "topics": [{"key": t.key, "label": t.label, "gloss": t.gloss} for t in topics],
        # 두 파일의 `_comment` 는 손으로 쓴 설명이다. admin 이 파일을 통째로 재생성하므로
        # 되쓸 원문을 같이 구워 보낸다 — 안 그러면 첫 저장에서 설명이 사라진다.
        "topicsComment": topics_doc.get("_comment"),
        "maxPerItem": max_per_item,
        "categories": [{"key": c, "label": CATEGORY_LABELS[c]} for c in CATEGORY_ORDER],
        "parseKinds": _PARSE_KINDS,
        "statuses": _SOURCE_STATUSES,
        "paths": {"sources": config.CUSTOM_SOURCES_FILE.name,
                  "topics": config.TOPICS_FILE.name},
        "workflow": "daily.yml",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_assets(output_dir)
    html = _env.get_template("admin.html").render(
        asset_prefix="", repo=repo,
        baked_json=json.dumps(baked, ensure_ascii=False).replace("</", "<\\/"),
    )
    out_path = output_dir / "admin.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


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
        # 죽은 링크는 리더에서도 앵커를 만들지 않는다 — RSS 리더는 href 를 그대로 열기 때문에
        # 사이트에서만 떼면 피드 구독자는 계속 404 를 맞는다(linkcheck.py 참고).
        dead = (it.get("link_status") or "") in DEAD_LINK_STATUSES
        head = title if dead else f'<a href="{url}">{title}</a>'
        parts.append(
            f"<li>{head}{major}<br>"
            f"<small>{label}{' · link no longer available' if dead else ''}</small>"
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
