import config
import pipeline


def _it(id_, cat, sig, enriched=True):
    return {"id": id_, "category": cat, "significance": sig, "_enriched": enriched,
            "published": "2026-07-30T00:00:00+00:00"}


def test_category_floor_is_distinct_from_global_min():
    settings = config.load().settings
    # 0.30 은 전역 0.25 는 넘지만 research 하한 0.55 에는 못 미친다
    pool = [_it("a", "research", 0.30)]
    buckets = pipeline._drop_reasons(pool, [], settings)
    assert "category_floor" in buckets
    assert buckets["category_floor"][0]["id"] == "a"


def test_global_min_still_reported():
    settings = config.load().settings
    buckets = pipeline._drop_reasons([_it("b", "research", 0.10)], [], settings)
    assert buckets["min_significance"][0]["id"] == "b"


def test_cap_drop_when_above_floor():
    settings = config.load().settings
    buckets = pipeline._drop_reasons([_it("c", "research", 0.95)], [], settings)
    assert buckets["category_cap"][0]["id"] == "c"


def test_enrich_failure_wins():
    settings = config.load().settings
    buckets = pipeline._drop_reasons([_it("d", "research", 0.95, enriched=False)], [], settings)
    assert buckets["enrich_failed"][0]["id"] == "d"
