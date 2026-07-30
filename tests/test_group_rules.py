import config
import render


def _items(category, n, sig):
    return [{"id": f"{category}{i}", "category": category, "significance": sig,
             "published": "2026-07-30T00:00:00+00:00"} for i in range(n)]


def test_cap_applied_per_category():
    settings = config.load().settings
    items = _items("research", 50, 0.9) + _items("policy_business", 12, 0.9)
    groups = dict(render.group_by_category(items, settings=settings))
    assert len(groups["research"]) == 6
    assert len(groups["policy_business"]) == 10


def test_floor_drops_weak_items_even_when_slots_free():
    settings = config.load().settings
    # research 하한 0.55 — 0.50 짜리는 캡(6)에 자리가 남아도 안 실린다
    groups = dict(render.group_by_category(_items("research", 3, 0.50), settings=settings))
    assert groups["research"] == []


def test_floor_is_per_category():
    settings = config.load().settings
    # 같은 0.35 라도 tools_products(0.30)는 통과, policy_business(0.40)는 탈락
    items = _items("tools_products", 1, 0.35) + _items("policy_business", 1, 0.35)
    groups = dict(render.group_by_category(items, settings=settings))
    assert len(groups["tools_products"]) == 1
    assert groups["policy_business"] == []


def test_no_settings_means_sort_only():
    groups = dict(render.group_by_category(_items("research", 50, 0.1)))
    assert len(groups["research"]) == 50
