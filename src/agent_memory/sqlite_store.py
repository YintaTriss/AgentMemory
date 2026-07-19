"""
sqlite_store.py — AgentMemory SQLite 索引存储

对标 VCP 的 SQLite WAL + 标签索引 + 共现矩阵 + 参数热加载
基于 Python sqlite3，零外部依赖。
"""
from __future__ import annotations
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class SQLiteStore:
    """SQLite 索引存储 — 替代 flat .vec.json 做元数据/标签管理。"""

    def __init__(self, db_path: str = "data/agentmemory.db"):
        self.db_path = db_path
        if db_path != ":memory:":
            self.db_path = str(Path(db_path).resolve())
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            conn = self._local.conn
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL DEFAULT 'default',
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                importance REAL DEFAULT 0.5,
                created_at TEXT,
                updated_at TEXT,
                vector BLOB,
                meta_json TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_memories_namespace ON memories(namespace);
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                namespace TEXT NOT NULL DEFAULT 'default',
                vector BLOB,
                usage_count INTEGER DEFAULT 0,
                UNIQUE(name, namespace)
            );
            CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);

            CREATE TABLE IF NOT EXISTS memory_tags (
                memory_id TEXT NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY(memory_id, tag_id),
                FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE,
                FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tag_cooccurrence (
                tag1_id INTEGER NOT NULL,
                tag2_id INTEGER NOT NULL,
                weight INTEGER DEFAULT 1,
                PRIMARY KEY(tag1_id, tag2_id),
                FOREIGN KEY(tag1_id) REFERENCES tags(id) ON DELETE CASCADE,
                FOREIGN KEY(tag2_id) REFERENCES tags(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        conn.commit()

    # ========== Tags ==========

    def extract_tags_from_content(self, content: str) -> List[str]:
        """从内容中提取 Tag: 行标记的标签。"""
        import re
        tags = []
        for line in content.split("\n"):
            line = line.strip()
            if line.lower().startswith("tag:") or line.startswith("标签："):
                tag_content = line.split(":", 1)[1].strip() if ":" in line else line[3:].strip()
                for t in re.split(r"[,，、;；|｜]", tag_content):
                    t = t.strip().rstrip("。.")
                    if t and len(t) > 0:
                        tags.append(t)
        return tags

    def _get_or_create_tag(self, name: str, namespace: str = "default",
                          vector: Optional[bytes] = None) -> int:
        conn = self._get_conn()
        cur = conn.execute("SELECT id FROM tags WHERE name=? AND namespace=?", (name, namespace))
        row = cur.fetchone()
        if row:
            tag_id = row[0]
            conn.execute("UPDATE tags SET usage_count=usage_count+1 WHERE id=?", (tag_id,))
            return tag_id
        cur = conn.execute(
            "INSERT INTO tags (name, namespace, vector, usage_count) VALUES (?,?,?,1)",
            (name, namespace, vector or b''),
        )
        return cur.lastrowid

    def add_tags_to_memory(self, memory_id: str, tags: List[str],
                          namespace: str = "default",
                          tag_vectors: Optional[Dict[str, bytes]] = None):
        conn = self._get_conn()
        tag_ids = []
        for t in tags:
            vec = (tag_vectors or {}).get(t)
            tag_id = self._get_or_create_tag(t, namespace, vec)
            tag_ids.append(tag_id)
            # Upsert memory_tags
            conn.execute(
                "INSERT OR IGNORE INTO memory_tags (memory_id, tag_id) VALUES (?,?)",
                (memory_id, tag_id),
            )
        # 更新共现
        for i in range(len(tag_ids)):
            for j in range(i + 1, len(tag_ids)):
                t1, t2 = sorted([tag_ids[i], tag_ids[j]])
                conn.execute(
                    """INSERT INTO tag_cooccurrence (tag1_id, tag2_id, weight)
                       VALUES (?,?,1)
                       ON CONFLICT(tag1_id, tag2_id) DO UPDATE SET weight=weight+1""",
                    (t1, t2),
                )
        conn.commit()

    def search_tags(self, query: str, namespace: str = "default", limit: int = 20) -> List[Dict]:
        conn = self._get_conn()
        cur = conn.execute(
            "SELECT id, name, usage_count FROM tags WHERE name LIKE ? AND namespace=? ORDER BY usage_count DESC LIMIT ?",
            (f"%{query}%", namespace, limit),
        )
        return [dict(row) for row in cur.fetchall()]

    # ========== Co-occurrence Matrix ==========

    def get_cooccurrence(self, tag_name: str, namespace: str = "default",
                        top_k: int = 10) -> List[Tuple[str, int]]:
        conn = self._get_conn()
        cur = conn.execute("SELECT id FROM tags WHERE name=? AND namespace=?", (tag_name, namespace))
        row = cur.fetchone()
        if not row:
            return []
        tag_id = row[0]
        cur = conn.execute(
            """SELECT t.name, tc.weight
               FROM tag_cooccurrence tc
               JOIN tags t ON t.id = CASE WHEN tc.tag1_id=? THEN tc.tag2_id ELSE tc.tag1_id END
               WHERE tc.tag1_id=? OR tc.tag2_id=?
               ORDER BY tc.weight DESC LIMIT ?""",
            (tag_id, tag_id, tag_id, top_k),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]

    def get_cooccurrence_by_tag_ids(self, tag_id_a: int, tag_id_b: int) -> Optional[float]:
        """获取两个标签的共现权重。"""
        conn = self._get_conn()
        t1, t2 = sorted([tag_id_a, tag_id_b])
        cur = conn.execute(
            "SELECT weight FROM tag_cooccurrence WHERE tag1_id=? AND tag2_id=?",
            (t1, t2),
        )
        row = cur.fetchone()
        return float(row[0]) if row else None

    def rebuild_cooccurrence(self):
        """根据 memory_tags 表重建共现矩阵（完全重算）。"""
        conn = self._get_conn()
        conn.execute("DELETE FROM tag_cooccurrence")
        conn.execute("""
            INSERT INTO tag_cooccurrence (tag1_id, tag2_id, weight)
            SELECT mt1.tag_id, mt2.tag_id, COUNT(*)
            FROM memory_tags mt1
            JOIN memory_tags mt2 ON mt1.memory_id = mt2.memory_id AND mt1.tag_id < mt2.tag_id
            GROUP BY mt1.tag_id, mt2.tag_id
        """)
        conn.commit()

    # ========== Memories ==========

    def upsert_memory(self, memory_id: str, content: str, namespace: str = "default",
                     category: str = "general", importance: float = 0.5,
                     vector: Optional[bytes] = None,
                     meta: Optional[Dict] = None):
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
        conn.execute(
            """INSERT INTO memories (id, namespace, content, category, importance, created_at, updated_at, vector, meta_json)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 content=excluded.content,
                 importance=excluded.importance,
                 updated_at=excluded.updated_at,
                 vector=excluded.vector,
                 meta_json=excluded.meta_json""",
            (memory_id, namespace, content, category, importance, now, now, vector or b'', meta_json),
        )
        conn.commit()
        return memory_id

    def get_memory(self, memory_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        cur = conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "namespace": row["namespace"],
            "content": row["content"],
            "category": row["category"],
            "importance": row["importance"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "meta": json.loads(row["meta_json"] or "{}"),
        }

    def list_memories(self, namespace: str = "default", limit: int = 100,
                     offset: int = 0, min_importance: float = 0.0) -> List[Dict]:
        conn = self._get_conn()
        cur = conn.execute(
            """SELECT * FROM memories
               WHERE namespace=? AND importance>=?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (namespace, min_importance, limit, offset),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_memory_tags(self, memory_id: str) -> List[str]:
        conn = self._get_conn()
        cur = conn.execute(
            "SELECT t.name FROM tags t JOIN memory_tags mt ON mt.tag_id=t.id WHERE mt.memory_id=?",
            (memory_id,),
        )
        return [r[0] for r in cur.fetchall()]

    # ========== KV Store ==========

    def kv_get(self, key: str, default: Any = None) -> Any:
        conn = self._get_conn()
        cur = conn.execute("SELECT value FROM kv_store WHERE key=?", (key,))
        row = cur.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return row[0]
        return default

    def kv_set(self, key: str, value: Any):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO kv_store (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        conn.commit()

    # ========== Stats ==========

    def stats(self, namespace: str = "default") -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            mem_count = conn.execute("SELECT COUNT(*) FROM memories WHERE namespace=?", (namespace,)).fetchone()[0]
            tag_count = conn.execute("SELECT COUNT(*) FROM tags WHERE namespace=?", (namespace,)).fetchone()[0]
            cooc_count = conn.execute("SELECT COUNT(*) FROM tag_cooccurrence").fetchone()[0]
            return {"memories": mem_count, "tags": tag_count, "cooccurrences": cooc_count, "namespace": namespace}
        except Exception as e:
            return {"error": str(e)}
