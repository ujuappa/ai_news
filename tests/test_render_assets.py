"""render.py 구조 분리(PROJECT_MEMO §13 T3.1) 회귀 테스트.

2026-07-31 에 템플릿 5개와 CSS 6블록을 render.py 문자열에서 `templates/` · `static/digest.css` 로
뺐다. 검증은 그때 rerender 로 238페이지를 재생성해 **body/title 바이트 동일**을 확인했지만,
그건 일회성이라 여기서 구조 계약을 고정한다.

고정하는 계약:
  1. CSS 는 인라인 `<style>` 이 아니라 `static/digest.css` 링크로 나간다.
  2. 링크 경로는 페이지 깊이에 맞다(루트="", archive/="../") — 틀리면 스타일이 통째로 날아간다.
  3. 배포 CSS = 기본 팔레트 `:root` + 저작 CSS. 저작 파일에 팔레트를 복붙하면 안 된다.
  4. 팔레트 원본은 `render.PALETTES` 하나다(파이썬 ↔ CSS 드리프트 방지).
  5. write_assets 를 부르는 걸 잊어도 되게, 각 render_* 가 스스로 부른다.
"""
import re

import pytest

import images
import render

STYLE_RE = re.compile(r"<style>", re.I)
LINK_RE = re.compile(r'<link rel="stylesheet" href="([^"]*digest\.css)"')

ITEM = {
    "title": "Opus 5 ships with 2x throughput", "headline": "Opus 5 ships",
    "url": "https://www.anthropic.com/news/claude-opus-5", "summary": "A frontier release.",
    "source_id": "anthropic", "source_name": "Anthropic", "category": "model_releases",
    "significance": 0.9, "is_major": True, "digest_date": "2026-07-31",
    "cluster_size": 1, "cluster_sources": [], "thread_parent": None,
}


def _groups(items=None):
    items = [dict(ITEM)] if items is None else items
    return [("model_releases", items), ("research", []),
            ("tools_products", []), ("policy_business", [])]


# ── 계약 3·4: 배포 CSS 조립 ────────────────────────────────────────────────────

def _css_no_comments():
    css = (render.STATIC_DIR / "digest.css").read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def test_every_css_variable_is_defined_by_the_palette():
    """CSS 가 참조하는 `var(--x)` 는 전부 `render.PALETTES` 가 정의하는 키여야 한다.

    이 테스트가 있는 이유(2026-07-31 실제 버그): `.archive-row.latest` 가
    `var(--acclt2, rgba(var(--grgb),.6))` 였는데 **--acclt2 는 팔레트에 없는 변수**였다.
    폴백이 있으니 CSS 는 조용히 동작했지만, 그 폴백이 `rgba(배경색,.6)` 을 같은 배경 위에
    올리는 것이라 **5개 팔레트 전부에서 하이라이트가 계산상 보이지 않았다.**
    폴백은 오타를 감춘다 — 그래서 폴백이 있든 없든 미정의 변수는 실패로 잡는다."""
    keys = {k for p in render.PALETTES for k in p} - {"name"}
    used = set(re.findall(r"var\(\s*--([\w-]+)", _css_no_comments()))
    assert not (used - keys), f"팔레트에 없는 변수: {sorted(used - keys)}"


def test_latest_archive_row_is_visually_distinct_from_the_page_background():
    """하이라이트 색이 배경과 같으면 강조가 아니다 — 위 --acclt2 버그의 직접 회귀 가드."""
    m = re.search(r"\.archive-row\.latest\s*\{[^}]*background:\s*var\(\s*--([\w-]+)",
                  _css_no_comments())
    assert m, ".archive-row.latest 의 background 선언을 찾지 못했다"
    var = m.group(1)
    for palette in render.PALETTES:
        assert palette[var] != palette["g"], \
            f'{palette["name"]}: --{var} 가 배경 --g 와 같다 ({palette[var]})'


def test_first_year_header_margin_rule_actually_matches():
    """`:first-of-type` 은 .archive-body 의 첫 div 가 .archive-top 이라 안 맞는다.
    인접 형제(.archive-table-head + .archive-year)로 잡혀 있어야 한다."""
    css = _css_no_comments()
    assert ".archive-table-head + .archive-year" in css
    assert ".archive-year:first-of-type" not in css


def test_authored_css_has_no_palette_block():
    """저작 파일에 :root 를 넣으면 PALETTES(파이썬)와 갈라진다. 주석 언급은 허용."""
    body = re.sub(r"/\*.*?\*/", "", (render.STATIC_DIR / "digest.css").read_text(encoding="utf-8"),
                  flags=re.S)
    assert ":root{" not in body


def test_write_assets_prepends_default_palette(tmp_path):
    css = render.write_assets(tmp_path).read_text(encoding="utf-8")
    assert css.startswith(render._root_vars_css(render.PALETTES[render.DEFAULT_THEME]))
    # 기본 팔레트(Mist · Signal red)의 실제 값이 들어갔는지 — 인덱스 착오 가드
    assert "--acc:#ec3013;" in css
    # 주석 안의 ':root' 언급은 규칙이 아니므로 세지 않는다(문서 문장 때문에 깨지면 안 된다)
    assert re.sub(r"/\*.*?\*/", "", css, flags=re.S).count(":root{") == 1


def test_deployed_css_contains_every_authored_rule(tmp_path):
    authored = (render.STATIC_DIR / "digest.css").read_text(encoding="utf-8")
    css = render.write_assets(tmp_path).read_text(encoding="utf-8")
    assert authored in css


def test_write_assets_recreates_a_deleted_file(tmp_path):
    """메모이즈 때문에 지워진 파일이 복구 안 되면, output 을 비우고 돌린 날 CSS 가 사라진다."""
    p = render.write_assets(tmp_path)
    p.unlink()
    assert render.write_assets(tmp_path).exists()


# ── 계약 1·2·5: 페이지가 링크를 올바른 깊이로 낸다 ─────────────────────────────

def test_home_links_css_at_both_depths(tmp_path):
    render.render_digest("2026-07-31", _groups(), [], tmp_path, total_records=1)
    root = (tmp_path / "index.html").read_text(encoding="utf-8")
    arch = (tmp_path / "archive" / "2026-07-31.html").read_text(encoding="utf-8")
    assert LINK_RE.search(root).group(1) == "static/digest.css"
    assert LINK_RE.search(arch).group(1) == "../static/digest.css"
    assert not STYLE_RE.search(root) and not STYLE_RE.search(arch)


def test_category_page_links_css_at_both_depths(tmp_path):
    render.render_category_page("2026-07-31", "model_releases", _groups(), tmp_path,
                                in_archive=False, total_records=1)
    render.render_category_page("2026-W31", "model_releases", _groups(), tmp_path,
                                in_archive=True, total_records=1)
    root = (tmp_path / "model_releases.html").read_text(encoding="utf-8")
    arch = (tmp_path / "archive" / "2026-W31-model_releases.html").read_text(encoding="utf-8")
    assert LINK_RE.search(root).group(1) == "static/digest.css"
    assert LINK_RE.search(arch).group(1) == "../static/digest.css"


def test_archive_week_and_index_use_parent_prefix(tmp_path):
    render.render_archive_digest("2026-W31", _groups(), tmp_path, total_records=1)
    render.render_archive_index([{"date": "2026-W31", "item_count": 1, "top_title": "t"}], tmp_path)
    week = (tmp_path / "archive" / "2026-W31.html").read_text(encoding="utf-8")
    idx = (tmp_path / "archive" / "index.html").read_text(encoding="utf-8")
    assert LINK_RE.search(week).group(1) == "../static/digest.css"
    assert LINK_RE.search(idx).group(1) == "../static/digest.css"


def test_search_page_links_css_from_root(tmp_path):
    render.render_search_page([dict(ITEM)], tmp_path)
    page = (tmp_path / "search.html").read_text(encoding="utf-8")
    assert LINK_RE.search(page).group(1) == "static/digest.css"
    assert not STYLE_RE.search(page)


@pytest.mark.parametrize("renderer", ["digest", "archive_week", "category", "search",
                                      "archive_index"])
def test_every_renderer_writes_the_stylesheet_itself(tmp_path, renderer):
    """계약 5: 호출자가 write_assets 를 잊어도 CSS 없는 사이트가 나오지 않는다."""
    render._assets_written.clear()
    if renderer == "digest":
        render.render_digest("2026-07-31", _groups(), [], tmp_path)
    elif renderer == "archive_week":
        render.render_archive_digest("2026-W31", _groups(), tmp_path)
    elif renderer == "category":
        render.render_category_page("2026-07-31", "model_releases", _groups(), tmp_path,
                                    in_archive=False)
    elif renderer == "search":
        render.render_search_page([dict(ITEM)], tmp_path)
    else:
        render.render_archive_index([{"date": "2026-W31", "item_count": 1, "top_title": "t"}],
                                    tmp_path)
    assert (tmp_path / "static" / "digest.css").exists()


# ── 링크가 실제 파일로 풀리는지(상대경로 계산 실수 방지) ───────────────────────

def test_every_rendered_link_resolves_to_a_real_file(tmp_path):
    render.render_digest("2026-07-31", _groups(), [], tmp_path, total_records=1)
    render.render_category_page("2026-W31", "model_releases", _groups(), tmp_path,
                                in_archive=True, total_records=1)
    render.render_archive_digest("2026-W31", _groups(), tmp_path, total_records=1)
    render.render_archive_index([{"date": "2026-W31", "item_count": 1, "top_title": "t"}], tmp_path)
    render.render_search_page([dict(ITEM)], tmp_path)
    pages = list(tmp_path.rglob("*.html"))
    assert len(pages) >= 5
    for p in pages:
        href = LINK_RE.search(p.read_text(encoding="utf-8")).group(1)
        assert (p.parent / href).resolve().exists(), f"{p.name} -> {href}"


# ── 템플릿 파일이 실제로 파일로 존재하는지(분리가 되돌아가지 않게) ─────────────

def test_templates_live_on_disk_not_in_python():
    expected = {"macros.html", "home.html", "category.html", "search.html",
                "archive_index.html", "archive_week.html"}
    assert expected <= {p.name for p in render.TEMPLATES_DIR.glob("*.html")}
    src = (render.TEMPLATES_DIR.parent / "render.py").read_text(encoding="utf-8")
    assert "<!doctype html" not in src.lower(), "마크업이 render.py 로 되돌아왔다"
    assert "box-sizing" not in src, "CSS 가 render.py 로 되돌아왔다"


# ── 홈 상단 (2026-08-06 캔버스 "Home Top Organization" 6a) ────────────────────

def test_masthead_carries_no_link_that_goes_nowhere(tmp_path):
    """6a 헤더에는 `Following 8` · `Monthly` pill 이 있지만 **일부러 안 넣었다** — 팔로우도
    주간/월간 기간 전환도 구현이 없어서(후자는 spec 문서만 있다) 누르면 아무 일도 안 일어난다.
    죽은 버튼 금지는 이 프로젝트의 규칙이고, 캔버스를 옮길 때 가장 새기 쉬운 구멍이다."""
    render.render_digest("2026-07-31", _groups(), [], tmp_path, total_records=1)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    for dead in ("Following", "Monthly", "Sign in"):
        assert dead not in page, f"구현이 없는 {dead!r} 가 마크업에 들어왔다"


def test_home_top_ships_the_6a_blocks(tmp_path):
    """지면 머리 · 카드 · Also today 구획선이 다 나오는지. 하나라도 빠지면 상단이 조용히
    예전 모양으로 돌아간다. 카드가 실제로 생기도록 아이템 4개를 넣는다(리드 + 02~04)."""
    items = []
    for i in range(4):
        it = dict(ITEM)
        it["title"] = it["headline"] = f"Story {i}"
        it["url"] = f"https://example.com/{i}"
        it["significance"] = 0.9 - i * 0.05
        items.append(it)
    render.render_digest("2026-07-31", _groups(items), [], tmp_path, total_records=496)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    for cls in ("page-head", "ph-date", "ph-title", "ph-stats", "panel", "panel-head", "also-break"):
        assert cls in page, f"{cls} 가 없다"
    assert "496" in page, "stat 쌍의 in-archive 숫자가 안 실렸다"


def test_archived_copy_does_not_claim_to_be_today(tmp_path):
    """같은 본문을 index.html 과 archive/{date}.html 에 굽는다. 디스플레이 제목만 갈라 놓는데,
    안 갈라 놓으면 몇 달 뒤에 아카이브 사본이 "Today's news" 라고 우긴다."""
    render.render_digest("2026-07-31", _groups(), [], tmp_path, total_records=1)
    root = (tmp_path / "index.html").read_text(encoding="utf-8")
    arch = (tmp_path / "archive" / "2026-07-31.html").read_text(encoding="utf-8")
    assert "Today&#39;s news" in root or "Today's news" in root
    assert "Today&#39;s news" not in arch and "Today's news" not in arch
    assert "That day&#39;s news" in arch or "That day's news" in arch


def test_theme_script_survives_blocked_localstorage(tmp_path):
    """저장소가 막힌 맥락(sandboxed iframe · 사이트 데이터 차단 · 일부 웹뷰)에서는
    `localStorage` 를 **읽기만 해도** SecurityError 가 난다. 테마 스크립트는 IIFE 하나라
    그 순간 통째로 죽고, 실측(jsdom) 결과 `__aiDigestSetTheme` 이 undefined 로 남아
    푸터 스위치 6개가 전부 ReferenceError 를 던지는 죽은 버튼이 됐다.

    배포 CSS 에 기본 팔레트 :root 가 있어서 지면은 멀쩡해 보이고 스위처만 조용히 죽는다 —
    눈으로 안 잡히는 종류라 테스트로 못박는다."""
    render.render_digest("2026-07-31", _groups(), [], tmp_path, total_records=1)
    head = (tmp_path / "index.html").read_text(encoding="utf-8").split("</script>")[0]
    assert "localStorage" in head, "테마 스크립트를 못 찾았다"
    for call in re.findall(r"localStorage\.\w+\([^)]*\)", head):
        # 각 접근이 try 블록 안에 있는지 — 감싸는 함수(read/write)를 거치는 형태여야 한다
        assert "try{" in head, f"{call} 이 try/catch 밖에 있다"
    assert re.search(r"function read\(\)\{try\{", head), "읽기 가드(read)가 없다"
    assert re.search(r"function write\(v\)\{try\{", head), "쓰기 가드(write)가 없다"
    assert "localStorage.setItem" not in head.split("function write")[0], \
        "write() 가드를 우회하는 직접 setItem 이 남아 있다"


def test_the_new_palette_is_a_complete_one(tmp_path):
    """팔레트를 하나 추가할 때 키를 빠뜨리면 그 테마에서만 `var(--x)` 가 빈 값이 된다 —
    테마를 눌러 보지 않으면 안 걸린다(2026-08-06 에 Boncom 팔레트를 넣으며 추가)."""
    keys = set(render.PALETTES[render.DEFAULT_THEME])
    for palette in render.PALETTES:
        assert set(palette) == keys, f'{palette["name"]}: 키가 다르다'


# ── 이미지 슬롯의 맞춤 방식이 한 곳에서만 정해지는지 ───────────────────────────

def test_both_fit_treatments_exist_in_css():
    """`images.IMAGE_FIT` 를 뒤집는 게 정말 한 줄이려면 CSS 에 두 벌이 다 있어야 한다."""
    css = _css_no_comments()
    assert ".fit-contain img" in css and "object-fit:contain" in css
    assert ".fit-cover img" in css and "object-fit:cover" in css


def test_slot_reserves_space_before_the_image_loads():
    """aspect-ratio 가 빠지면 로고가 늦게 뜰 때 지면이 밀린다."""
    css = _css_no_comments()
    for cls in (".imgslot-lead", ".imgslot-card", ".imgslot-thumb"):
        m = re.search(re.escape(cls) + r"\s*\{([^}]*)\}", css)
        assert m and "aspect-ratio:" in m.group(1), f"{cls} 에 aspect-ratio 가 없다"


def test_also_grid_does_not_stretch_a_lone_filtered_card():
    """토픽 필터가 also-card 를 숨기면 `auto-fit` 이 빈 트랙을 접어 남은 카드가 전폭이 된다.

    슬롯(aspect-ratio 16/10 · width 100%)이 따라 커져 chips/robotics 처럼 1~2건만 남는
    필터에서 이미지가 거대해진다. All / Government & law(카드 2~3장) 크기를 기준으로,
    그리드는 auto-fit 을 쓰지 않고 카드에 전폭 방지 상한을 둔다."""
    css = _css_no_comments()
    grid = re.search(r"\.also-grid\s*\{([^}]*)\}", css)
    assert grid, ".also-grid 규칙을 찾지 못했다"
    assert "auto-fit" not in grid.group(1), \
        "auto-fit 은 필터로 숨은 카드의 트랙을 접어 Lone 카드를 전폭으로 키운다"
    card = re.search(r"\.also-card\s*\{([^}]*)\}", css)
    assert card and "max-width:" in card.group(1), \
        "Lone also-card 가 전폭으로 커지지 않도록 max-width 가 필요하다"


def test_filled_slot_carries_the_configured_fit_class(tmp_path, monkeypatch):
    """마크업이 `images.IMAGE_FIT` 을 그대로 따라가는지 — 상수 한 줄로 전체가 바뀐다는 계약.

    **Jinja 환경 전역이 아니라 아이템 필드여야 하는 이유가 이 테스트다**: `{% import %}` 한
    매크로 모듈은 첫 렌더 때 만들어져 캐시되므로, 전역으로 두면 그 시점 값이 굳어서
    이 테스트가 앞선 테스트의 렌더 여부에 따라 붙었다 떨어졌다 한다(실제로 겪음)."""
    monkeypatch.setattr(images, "resolve", lambda *a, **k: "static/img/openai.svg")
    monkeypatch.setattr(images, "IMAGE_FIT", "cover")
    render.render_digest("2026-07-31", _groups(), [], tmp_path, total_records=1)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'class="imgslot imgslot-lead has-img fit-cover"' in page
    assert 'src="static/img/openai.svg"' in page


def test_empty_slot_falls_back_to_the_text_placeholder(tmp_path, monkeypatch):
    """맞는 파일이 하나도 없으면 fit-* 없이 소스명 상자를 그린다(기존 동작 유지)."""
    monkeypatch.setattr(images, "resolve", lambda *a, **k: None)
    render.render_digest("2026-07-31", _groups(), [], tmp_path, total_records=1)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    # 슬롯 마크업만 본다 — 페이지 전체에서 'fit-' 을 찾으면 CSS 셀렉터를 언급하는 스크립트
    # 같은 것에도 걸린다.
    slot = re.search(r'<div class="imgslot imgslot-lead.*?</div>', page, re.S).group(0)
    assert slot.startswith('<div class="imgslot imgslot-lead" ')
    assert "fit-contain" not in slot and "fit-cover" not in slot
    assert '<span class="imgslot-label">Anthropic</span>' in slot


def test_theme_js_carries_all_five_palettes(tmp_path):
    """테마 스위처가 읽는 JSON 은 autoescape 를 우회해야 한다(|safe). 깨지면 따옴표가 &quot;."""
    render.render_search_page([dict(ITEM)], tmp_path)
    page = (tmp_path / "search.html").read_text(encoding="utf-8")
    assert "&quot;" not in page.split("</script>")[0]
    for palette in render.PALETTES:
        assert palette["name"] in page
    assert f"?stored:{render.DEFAULT_THEME};" in page
