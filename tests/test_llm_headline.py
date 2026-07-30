import llm


def test_clean_headline_uses_model_value():
    assert llm._clean_headline("Sonnet 4.6 ships", "Full original title") == "Sonnet 4.6 ships"


def test_clean_headline_falls_back_when_missing():
    assert llm._clean_headline(None, "Full original title") == "Full original title"
    assert llm._clean_headline("   ", "Full original title") == "Full original title"


def test_clean_headline_strips_trailing_period():
    assert llm._clean_headline("Anthropic raises $65B.", "t") == "Anthropic raises $65B"


def test_clean_headline_truncates_on_word_boundary():
    long = "Semalith v1.4 a calibrated safety classifier achieving state of the art detection results"
    out = llm._clean_headline(long, "t", limit=40)
    assert len(out) <= 41          # 40 + the ellipsis character
    assert out.endswith("\u2026")
    assert not out[:-1].endswith(" ")
    assert " ".join(out[:-1].split()) == out[:-1]   # no mid-word cut


def test_merge_row_applies_all_fields():
    it = {"id": "a", "category": "research", "summary_raw": "raw", "title": "Original title"}
    llm._merge_row(it, {
        "id": "a", "category": "model_releases", "summary": "A summary.",
        "significance": 0.9, "is_major": True, "headline": "Short one",
    })
    assert it["category"] == "model_releases"
    assert it["summary"] == "A summary."
    assert it["significance"] == 0.9
    assert it["is_major"] is True
    assert it["headline"] == "Short one"
    assert it["_enriched"] is True


def test_merge_row_ignores_unknown_category():
    it = {"id": "a", "category": "research", "summary_raw": "raw", "title": "T"}
    llm._merge_row(it, {"id": "a", "category": "not_a_category", "summary": "s"})
    assert it["category"] == "research"


def test_merge_row_headline_falls_back_to_title():
    it = {"id": "a", "category": "research", "summary_raw": "raw", "title": "Original title"}
    llm._merge_row(it, {"id": "a", "summary": "s"})
    assert it["headline"] == "Original title"
