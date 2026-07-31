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


def test_theme_js_carries_all_five_palettes(tmp_path):
    """테마 스위처가 읽는 JSON 은 autoescape 를 우회해야 한다(|safe). 깨지면 따옴표가 &quot;."""
    render.render_search_page([dict(ITEM)], tmp_path)
    page = (tmp_path / "search.html").read_text(encoding="utf-8")
    assert "&quot;" not in page.split("</script>")[0]
    for palette in render.PALETTES:
        assert palette["name"] in page
    assert f"?stored:{render.DEFAULT_THEME};" in page
