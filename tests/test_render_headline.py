import render


def _item(**over):
    it = {"id": "a", "title": "A very long original title", "headline": "Short one",
          "url": "https://example.com/x", "significance": 0.9, "is_major": False,
          "summary": "s", "published": "2026-07-30T00:00:00+00:00",
          "source_id": "openai", "source_name": "OpenAI", "category": "model_releases"}
    it.update(over)
    return it


def test_annotate_prefers_headline():
    it = _item()
    render._annotate(it)
    assert it["display_title"] == "Short one"


def test_annotate_falls_back_to_title_when_headline_empty():
    it = _item(headline="")
    render._annotate(it)
    assert it["display_title"] == "A very long original title"


def test_annotate_falls_back_when_headline_missing():
    it = _item()
    del it["headline"]
    render._annotate(it)
    assert it["display_title"] == "A very long original title"


def test_home_page_shows_headline_and_keeps_full_title(tmp_path):
    groups = [("model_releases", [_item()])]
    render.render_digest("2026-07-30", groups, [], tmp_path, total_records=1)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Short one" in html
    assert 'title="A very long original title"' in html
