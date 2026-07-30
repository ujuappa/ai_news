import config


def test_rule_for_configured_category():
    cfg = config.load()
    rule = cfg.settings.rule_for("research")
    assert rule.max_items == 6
    assert rule.min_significance == 0.55


def test_rule_for_policy_has_headroom():
    cfg = config.load()
    assert cfg.settings.rule_for("policy_business").max_items == 10


def test_rule_for_unknown_category_falls_back_to_globals():
    cfg = config.load()
    rule = cfg.settings.rule_for("community_takes")
    assert rule.max_items == cfg.settings.max_items_per_category
    assert rule.min_significance == cfg.settings.min_significance
