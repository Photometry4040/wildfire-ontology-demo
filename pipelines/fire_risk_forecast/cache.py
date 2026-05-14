# SQLite 기반 24h TTL 캐시
# 키: "forecast:YYYY-MM-DD"
import json
import sqlite3
import time
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "dol_ontology"
CACHE_DB = CACHE_DIR / "fire_risk.db"
TTL_SECONDS = 86_400  # 24h


class ForecastCache:
    def __init__(self, db_path: Path = CACHE_DB):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._init()

    def _init(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key        TEXT    PRIMARY KEY,
                value      TEXT    NOT NULL,
                created_at REAL    NOT NULL
            )
        """)
        self._conn.commit()

    def get(self, key: str) -> list[dict] | None:
        row = self._conn.execute(
            "SELECT value, created_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, created_at = row
        if time.time() - created_at > TTL_SECONDS:
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            self._conn.commit()
            return None
        return json.loads(value)

    def set(self, key: str, value: list[dict]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, created_at) VALUES (?, ?, ?)",
            (key, json.dumps(value, ensure_ascii=False), time.time()),
        )
        self._conn.commit()

    def clear_expired(self) -> int:
        cutoff = time.time() - TTL_SECONDS
        cur = self._conn.execute("DELETE FROM cache WHERE created_at < ?", (cutoff,))
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self._conn.close()
