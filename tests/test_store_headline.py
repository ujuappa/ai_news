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


# ── list_digests().top_title — 아카이브 인덱스 표시용 (2026-07-31, §13 T3.3) ──

def _publish(store, label, title, headline, sig):
    store.save_items([{
        "id": f"{label}-{sig}", "source_id": "openai", "category": "model_releases",
        "title": title, "url": f"https://example.com/{label}{sig}", "summary": "s",
        "significance": sig, "is_major": False, "published": "",
        "headline": headline,
    }], label)
    store.record_digest(label, 1, f"archive/{label}.html")


def test_top_title_prefers_headline(tmp_path):
    """아카이브 인덱스는 렌더의 display_title 과 같은 규칙을 써야 한다 — 안 맞추면 같은
    항목이 홈에선 짧게, 아카이브 목록에선 길게 나온다."""
    store = Store(tmp_path / "t.db")
    _publish(store, "2026-07-31", "A very long original title " * 4, "Short headline", 0.9)
    top = {d["date"]: d["top_title"] for d in store.list_digests()}
    assert top["2026-07-31"] == "Short headline"
    store.close()


def test_top_title_falls_back_to_title_for_legacy_rows(tmp_path):
    """백필 414건은 headline 컬럼이 생기기 전 데이터라 빈 문자열이다 — 폴백이 살아야 한다."""
    store = Store(tmp_path / "t.db")
    _publish(store, "2026-W20", "Legacy backfill title", "", 0.8)
    top = {d["date"]: d["top_title"] for d in store.list_digests()}
    assert top["2026-W20"] == "Legacy backfill title"
    store.close()


def test_top_title_picks_the_highest_significance_item(tmp_path):
    store = Store(tmp_path / "t.db")
    _publish(store, "2026-07-31", "low", "Low headline", 0.3)
    _publish(store, "2026-07-31", "high", "High headline", 0.95)
    top = {d["date"]: d["top_title"] for d in store.list_digests()}
    assert top["2026-07-31"] == "High headline"
    store.close()
