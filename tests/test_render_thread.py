import render


def _item(**over):
    it = {"id": "a", "title": "Anthropic raises $65B in Series H", "headline": "",
          "url": "https://example.com/h", "significance": 0.9, "is_major": False,
          "summary": "s", "published": "2026-07-30T00:00:00+00:00", "source_id": "anthropic",
          "source_name": "Anthropic", "category": "policy_business"}
    it.update(over)
    return it


_PARENT = {"display": "Anthropic raises $30B Series G", "date": "2026-W07"}


def test_annotate_exposes_thread_when_parent_present():
    it = _item(thread_parent=_PARENT)
    render._annotate(it)
    assert it["thread"]["display"] == "Anthropic raises $30B Series G"
    assert it["thread"]["date"] == "2026-W07"


def test_annotate_thread_is_none_without_parent():
    it = _item()
    render._annotate(it)
    assert it["thread"] is None
    it2 = _item(thread_parent=None)
    render._annotate(it2)
    assert it2["thread"] is None


def test_home_lead_links_to_parent_archive_page(tmp_path):
    groups = [("policy_business", [_item(thread_parent=_PARENT)])]
    render.render_digest("2026-07-30", groups, [], tmp_path, total_records=1)

    root = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Earlier: Anthropic raises $30B Series G (2026-W07)" in root
    assert 'href="archive/2026-W07.html"' in root

    # 아카이브 사본은 output/archive/ 안에 있으므로 상대경로에 ../ 가 붙어야 한다.
    arch = (tmp_path / "archive" / "2026-07-30.html").read_text(encoding="utf-8")
    assert 'href="../archive/2026-W07.html"' in arch


def test_category_row_shows_thread_without_nesting_an_anchor(tmp_path):
    groups = [("policy_business", [_item(thread_parent=_PARENT)])]
    render.render_category_page("2026-07-30", "policy_business", groups, tmp_path,
                                in_archive=False, total_records=1)
    html = (tmp_path / "policy_business.html").read_text(encoding="utf-8")
    assert "Earlier: Anthropic raises $30B Series G (2026-W07)" in html
    assert '<span class="thread-line">' in html


def test_archive_digest_links_to_parent_inside_archive(tmp_path):
    groups = [("policy_business", [_item(thread_parent=_PARENT)])]
    render.render_archive_digest("2026-W22", groups, tmp_path, total_records=1)
    html = (tmp_path / "archive" / "2026-W22.html").read_text(encoding="utf-8")
    assert "Earlier: Anthropic raises $30B Series G (2026-W07)" in html
    assert 'href="2026-W07.html"' in html
    assert 'href="../archive/2026-W07.html"' not in html


def test_no_thread_line_when_absent(tmp_path):
    groups = [("policy_business", [_item()])]
    render.render_digest("2026-07-30", groups, [], tmp_path, total_records=1)
    assert "Earlier:" not in (tmp_path / "index.html").read_text(encoding="utf-8")
