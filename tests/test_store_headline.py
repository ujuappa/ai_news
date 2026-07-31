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


# ── recent_digest_entries — RSS 피드용 (2026-07-31, §13 T3.4) ─────────────────

def test_recent_digest_entries_newest_first_and_limited(tmp_path):
    store = Store(tmp_path / "t.db")
    for label in ["2026-07-29", "2026-07-30", "2026-07-31", "2026-W20"]:
        _publish(store, label, f"t {label}", f"H {label}", 0.5)
    got = store.recent_digest_entries(limit=3)
    assert [e["label"] for e in got] == ["2026-07-31", "2026-07-30", "2026-07-29"]
    store.close()


def test_recent_digest_entries_sorts_items_by_significance(tmp_path):
    """피드 본문 순서가 사이트 랭킹과 같아야 한다."""
    store = Store(tmp_path / "t.db")
    _publish(store, "2026-07-31", "low", "Low", 0.3)
    _publish(store, "2026-07-31", "high", "High", 0.95)
    _publish(store, "2026-07-31", "mid", "Mid", 0.6)
    entry = store.recent_digest_entries()[0]
    assert [it["headline"] for it in entry["items"]] == ["High", "Mid", "Low"]
    store.close()


def test_recent_digest_entries_tolerates_a_missing_recap(tmp_path):
    """리캡 생성이 실패한 날도 있다(2026-07-31 크래시) — headline 은 빈 문자열이어야 한다."""
    store = Store(tmp_path / "t.db")
    _publish(store, "2026-07-31", "t", "H", 0.5)
    assert store.recent_digest_entries()[0]["headline"] == ""
    store.close()
