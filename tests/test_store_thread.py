from store import Store


def _item(**over):
    it = {"id": "t1", "source_id": "anthropic", "category": "policy_business",
          "title": "Anthropic raises $30 billion in Series G funding", "headline": "",
          "url": "https://example.com/g", "summary": "s", "significance": 0.9,
          "is_major": True, "published": "2026-02-10T00:00:00+00:00"}
    it.update(over)
    return it


def test_thread_parent_id_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(id="parent")], "2026-W07")
    store.save_items([_item(id="child", thread_parent_id="parent")], "2026-W22")
    assert store.items_for_digest("2026-W22")[0]["thread_parent_id"] == "parent"
    assert store.items_for_digest("2026-W07")[0]["thread_parent_id"] == ""
    store.close()


def test_dropped_item_preserves_thread_parent_id(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(id="parent")], "2026-W07")
    store.save_items([_item(id="child", thread_parent_id="parent")], "2026-W22",
                     is_published=False, drop_reason="category_cap")
    assert store.dropped_items("2026-W22")[0]["thread_parent_id"] == "parent"
    store.close()


def test_thread_parent_info_prefers_headline(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(id="p1", headline="Anthropic raises $30B Series G")], "2026-W07")
    info = store.thread_parent_info(["p1"])
    assert info["p1"]["display"] == "Anthropic raises $30B Series G"
    assert info["p1"]["date"] == "2026-W07"
    store.close()


def test_thread_parent_info_falls_back_to_title(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(id="p2", headline="")], "2026-W07")
    assert store.thread_parent_info(["p2"])["p2"]["display"].startswith("Anthropic raises $30")
    store.close()


def test_thread_parent_info_ignores_blanks_and_unknowns(tmp_path):
    store = Store(tmp_path / "t.db")
    assert store.thread_parent_info([]) == {}
    assert store.thread_parent_info(["", None]) == {}
    assert store.thread_parent_info(["nope"]) == {}
    store.close()
