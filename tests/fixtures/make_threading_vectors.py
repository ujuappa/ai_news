"""Live DB에서 threading fixture를 한 번 생성한다.

이 스크립트는 재현·출처 확인용이며, 커밋된 threading_vectors.npz가 테스트의 source
of truth다. 보존 기간 때문에 사라질 수 있는 item_emb를 테스트에서 직접 읽지 않는다.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config

PREFIXES = ("d7d47956", "a3d8c6fa", "1ccc22f7", "45f898f6", "7909c613", "06b8d0ad")
OUTPUT = Path(__file__).with_name("threading_vectors.npz")


def main():
    conn = sqlite3.connect(f"file:{config.DB_PATH.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT ie.id, ie.embedding, ie.digest_date,
                  COALESCE(NULLIF(i.headline, ''), i.title) AS display_title
           FROM item_emb ie JOIN items i ON i.id = ie.id"""
    ).fetchall()
    conn.close()
    by_prefix = {r["id"][:8]: r for r in rows if r["id"][:8] in PREFIXES}
    missing = [prefix for prefix in PREFIXES if prefix not in by_prefix]
    if missing:
        raise SystemExit(f"fixture item_emb 없음: {', '.join(missing)}")
    picked = [by_prefix[prefix] for prefix in PREFIXES]
    np.savez_compressed(
        OUTPUT,
        ids=np.array([r["id"] for r in picked]),
        embeddings=np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in picked]),
        digest_dates=np.array([r["digest_date"] for r in picked]),
        display_titles=np.array([r["display_title"] for r in picked]),
    )
    print(f"완료 → {OUTPUT} ({len(picked)} vectors)")


if __name__ == "__main__":
    main()
