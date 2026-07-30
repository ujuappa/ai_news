from store import Store


def test_headline_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([{
        "id": "x1", "source_id": "openai", "category": "model_releases",
        "title": "A very long original title that would break the layout",
        "url": "https://example.com/a", "summary": "s", "significance": 0.9,
        "is_major": True, "published": "2026-07-30T00:00:00+00:00",
        "headline": "Short display title",
    }], "2026-07-30")
    got = store.items_for_digest("2026-07-30")
    assert got[0]["headline"] == "Short display title"
    assert got[0]["title"].startswith("A very long original")
    assert store.all_items()[0]["headline"] == "Short display title"
    store.close()


def test_headline_defaults_to_empty_when_absent(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([{
        "id": "x2", "source_id": "openai", "category": "research",
        "title": "T", "url": "https://example.com/b", "summary": "s",
        "significance": 0.1, "is_major": False, "published": "",
    }], "2026-07-30", is_published=False, drop_reason="min_significance")
    assert store.dropped_items("2026-07-30")[0]["headline"] == ""
    store.close()
