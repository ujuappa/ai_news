import numpy as np

import config
import pipeline
from store import Store


def test_reset_clears_derived_embeddings_but_preserves_archive(tmp_path, monkeypatch):
    db_path = tmp_path / "digest.db"
    store = Store(db_path)
    item = {
        "id": "item", "source_id": "test", "category": "research", "title": "Title",
        "url": "https://example.com", "summary": "Summary", "significance": 0.8,
        "is_major": False, "published": "2026-07-30",
    }
    store.save_items([item], "2026-07-30")
    store.record_digest("2026-07-30", 1, "archive/2026-07-30.html")
    store.save_embeddings([{"id": "item", "_emb": np.array([1.0, 0.0], dtype=np.float32)}],
                          "2026-07-30")
    store.add_seen("item", "Title", "https://example.com", np.array([1.0, 0.0], dtype=np.float32))
    store.close()
    monkeypatch.setattr(config, "DB_PATH", db_path)

    pipeline.reset_db()

    store = Store(db_path)
    assert store.counts()["seen"] == 0
    assert store.counts()["item_emb"] == 0
    assert store.counts()["items"] == 1
    assert store.counts()["digests"] == 1
    store.close()
