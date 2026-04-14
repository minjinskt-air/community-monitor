"""
core/db_handler.py
──────────────────────────────────────
JSON 파일 기반 중복 방지 핸들러
(GitHub Actions 환경: SQLite는 실행마다 초기화되므로 JSON 파일 사용)

sent_posts.json 구조:
{
  "ppomppu":  {"post_id_1": "2026-04-14T10:30:00", ...},
  "fmkorea":  {...},
  "dcinside": {...}
}
──────────────────────────────────────
"""

import json
import os
from datetime import datetime, timedelta
from config import DB_PATH  # DB_PATH = "sent_posts.json"


class DBHandler:
    def __init__(self):
        self.path = DB_PATH
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def is_sent(self, post_id: str, source: str) -> bool:
        return post_id in self._data.get(source, {})

    def mark_sent(self, post: dict):
        source   = post["source"]
        post_id  = post["post_id"]
        if source not in self._data:
            self._data[source] = {}
        self._data[source][post_id] = datetime.now().isoformat()
        self._save()

    def filter_new(self, posts: list) -> list:
        return [p for p in posts if not self.is_sent(p["post_id"], p["source"])]

    def cleanup_old(self, days: int = 30):
        """N일 지난 항목 제거 (JSON 파일 용량 관리)"""
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0
        for source in list(self._data.keys()):
            old_keys = [
                pid for pid, ts in self._data[source].items()
                if datetime.fromisoformat(ts) < cutoff
            ]
            for k in old_keys:
                del self._data[source][k]
                removed += 1
        if removed:
            self._save()
            print(f"[DB] 오래된 항목 {removed}개 제거 ({days}일 초과)")

    def stats(self) -> dict:
        by_source = {src: len(ids) for src, ids in self._data.items()}
        return {
            "total":     sum(by_source.values()),
            "by_source": by_source,
        }
