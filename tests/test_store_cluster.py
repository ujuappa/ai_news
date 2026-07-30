from store import Store


def _item(**over):
    it = {"id": "c1", "source_id": "techcrunch_ai", "category": "model_releases",
          "title": "T", "headline": "", "url": "https://example.com/a", "summary": "s",
          "significance": 0.9, "is_major": True, "published": "2026-07-30T00:00:00+00:00"}
    it.update(over)
    return it


def test_cluster_sources_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(cluster_sources=["OpenAI", "TechCrunch"], cluster_size=2)],
                     "2026-07-30")
    got = store.items_for_digest("2026-07-30")[0]
    assert got["cluster_sources"] == ["OpenAI", "TechCrunch"]
    assert got["cluster_size"] == 2
    store.close()


def test_cluster_defaults_when_absent(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(id="c2")], "2026-07-30")
    got = store.items_for_digest("2026-07-30")[0]
    assert got["cluster_sources"] == []
    assert got["cluster_size"] == 1
    store.close()


def test_cluster_survives_all_items_and_dropped_items(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(id="c3", cluster_sources=["A", "B", "C"], cluster_size=3)],
                     "2026-07-30")
    store.save_items([_item(id="c4", cluster_sources=["D"], cluster_size=1)],
                     "2026-07-30", is_published=False, drop_reason="category_cap")
    assert store.all_items()[0]["cluster_sources"] == ["A", "B", "C"]
    assert store.dropped_items("2026-07-30")[0]["cluster_sources"] == ["D"]
    store.close()
