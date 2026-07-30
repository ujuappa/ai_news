import config


def test_thread_settings_load_from_yaml():
    s = config.load().settings
    assert s.thread_min_similarity == 0.75
    assert s.thread_max_similarity == 0.83
    assert s.embedding_retention_days == 180


def test_thread_band_sits_below_the_dedup_line():
    """상한이 dedup 임계값을 넘으면 '중복'을 '앞 이야기'로 링크하게 된다."""
    s = config.load().settings
    assert s.thread_max_similarity <= s.dedup_threshold
    assert s.thread_min_similarity < s.thread_max_similarity


def test_embeddings_outlive_the_seen_window():
    s = config.load().settings
    assert s.embedding_retention_days > s.seen_store_retention_days
