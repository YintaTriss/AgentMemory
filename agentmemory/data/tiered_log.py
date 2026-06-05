"""
TieredLog - 分层日志模块
Version: v2.0
"""

import asyncio
import gzip
import json
import shutil
from pathlib import Path
from typing import Optional, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from enum import Enum
import aiofiles


LOGS_DIR = "_logs"
RECENT_DIR = "recent"
ARCHIVE_DIR = "archive"
MANIFEST_FILE = "_manifest.json"
HOT_DAYS = 7


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class LogEntry:
    timestamp: str
    level: str
    action: str
    memory_id: Optional[str] = None
    category_path: Optional[str] = None
    message: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp, "level": self.level, "action": self.action,
            "memory_id": self.memory_id, "category_path": self.category_path,
            "message": self.message, "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "LogEntry":
        return cls(
            timestamp=data["timestamp"], level=data["level"], action=data["action"],
            memory_id=data.get("memory_id"), category_path=data.get("category_path"),
            message=data.get("message"), metadata=data.get("metadata", {}),
        )


@dataclass
class Manifest:
    recent_files: dict = field(default_factory=dict)
    archive_files: dict = field(default_factory=dict)
    total_entries: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "recent_files": self.recent_files, "archive_files": self.archive_files,
            "total_entries": self.total_entries, "last_updated": self.last_updated,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        return cls(
            recent_files=data.get("recent_files", {}), archive_files=data.get("archive_files", {}),
            total_entries=data.get("total_entries", 0), last_updated=data.get("last_updated", datetime.now().isoformat()),
        )


class TieredLogError(Exception): pass


class TieredLog:
    def __init__(self, root_dir):
        self.root_dir = Path(root_dir).resolve()
        self.logs_dir = self.root_dir / LOGS_DIR
        self.recent_dir = self.logs_dir / RECENT_DIR
        self.archive_dir = self.logs_dir / ARCHIVE_DIR
        self.manifest_file = self.logs_dir / MANIFEST_FILE
        self._lock = asyncio.Lock()
        self._manifest: Optional[Manifest] = None
        self._today_file: Optional[Path] = None
        self._write_buffer: deque = deque()
        self._buffer_size = 10

    async def init(self):
        await asyncio.to_thread(lambda: [d.mkdir(parents=True, exist_ok=True) for d in [self.logs_dir, self.recent_dir, self.archive_dir]])
        
        if self.manifest_file.exists():
            async with aiofiles.open(self.manifest_file, "r", encoding="utf-8") as f:
                self._manifest = Manifest.from_dict(json.loads(await f.read()))
        else:
            self._manifest = Manifest()
            await self._save_manifest()
        
        today = datetime.now().strftime("%Y-%m-%d")
        self._today_file = self.recent_dir / (today + ".jsonl")

    async def _save_manifest(self):
        async with self._lock:
            self._manifest.last_updated = datetime.now().isoformat()
            tmp = self.manifest_file.with_suffix('.tmp')
            async with aiofiles.open(tmp, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self._manifest.to_dict(), ensure_ascii=False, indent=2))
            tmp.replace(self.manifest_file)

    def _get_date_prefix(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _get_log_file(self, date: Optional[str] = None) -> Path:
        if date is None:
            date = self._get_date_prefix()
        return self.recent_dir / (date + ".jsonl")

    async def append(self, action: str, level: str = LogLevel.INFO.value, memory_id: Optional[str] = None,
                   category_path: Optional[str] = None, message: Optional[str] = None, metadata: Optional[dict] = None) -> LogEntry:
        entry = LogEntry(
            timestamp=datetime.now().isoformat(), level=level, action=action,
            memory_id=memory_id, category_path=category_path, message=message, metadata=metadata or {},
        )
        self._write_buffer.append(entry)
        if len(self._write_buffer) >= self._buffer_size:
            await self._flush_buffer()
        return entry

    async def _flush_buffer(self):
        if not self._write_buffer:
            return
        async with self._lock:
            log_file = self._today_file or self._get_log_file()
            async with aiofiles.open(log_file, 'a', encoding='utf-8') as f:
                while self._write_buffer:
                    entry = self._write_buffer.popleft()
                    line = json.dumps(entry.to_dict(), ensure_ascii=False) + chr(10)
                    await f.write(line)
            
            if self._manifest:
                date = log_file.stem
                size = log_file.stat().st_size if log_file.exists() else 0
                self._manifest.recent_files[date] = {"size": size, "entries": self._manifest.recent_files.get(date, {}).get("entries", 0) + 1}
                self._manifest.total_entries += 1
                await self._save_manifest()

    async def flush(self):
        await self._flush_buffer()

    async def read_today(self) -> AsyncIterator[LogEntry]:
        today = datetime.now().strftime("%Y-%m-%d")
        async for entry in self.read_by_date(today):
            yield entry

    async def read_by_date(self, date: str) -> AsyncIterator[LogEntry]:
        log_file = self._get_log_file(date)
        if log_file.exists():
            async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
                async for line in f:
                    if line.strip():
                        yield LogEntry.from_dict(json.loads(line))

    async def read_by_memory_id(self, memory_id: str) -> list:
        entries = []
        async for entry in self.read_today():
            if entry.memory_id == memory_id:
                entries.append(entry)
        return entries

    async def iterate_logs(self, limit: Optional[int] = None) -> AsyncIterator[LogEntry]:
        count = 0
        async for entry in self.read_today():
            yield entry
            count += 1
            if limit and count >= limit:
                break

    async def archive_old_files(self):
        cutoff = datetime.now() - timedelta(days=HOT_DAYS)
        async with self._lock:
            for date in list(self._manifest.recent_files.keys()):
                try:
                    file_date = datetime.strptime(date, "%Y-%m-%d")
                    if file_date < cutoff:
                        recent_file = self.recent_dir / (date + ".jsonl")
                        archive_file = self.archive_dir / (date + ".jsonl.gz")

                        if recent_file.exists():
                            with gzip.open(archive_file, 'wt', encoding='utf-8') as gz:
                                with open(recent_file, 'r', encoding='utf-8') as f:
                                    gz.write(f.read())

                            recent_file.unlink()

                            self._manifest.archive_files[date] = self._manifest.recent_files.pop(date)
                            await self._save_manifest()
                except ValueError:
                    continue

    # ============================================================================
    # §5.5 TieredLog 接口契约实现
    # ============================================================================

    async def read_range(
        self,
        since: datetime,
        until: datetime,
    ) -> list[LogEntry]:
        """§5.5 read_range — 按时间范围读取热层日志"""
        results: list[LogEntry] = []
        delta = until - since
        for days_diff in range(delta.days + 1):
            current_date = since + timedelta(days=days_diff)
            date_str = current_date.strftime("%Y-%m-%d")
            log_file = self.recent_dir / (date_str + ".jsonl")
            if log_file.exists():
                async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                for line in content.split('\n'):
                    if line.strip():
                        entry = LogEntry.from_dict(json.loads(line))
                        entry_ts = datetime.fromisoformat(entry.timestamp)
                        if since <= entry_ts <= until:
                            results.append(entry)
        return results

    async def read_tail(self, n: int = 100) -> list[LogEntry]:
        """§5.5 read_tail — 读取最近 n 条"""
        results: list[LogEntry] = []
        # 读取最近的日志文件（从新到旧）
        if not self.recent_dir.exists():
            return results
        files = sorted(
            self.recent_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for log_file in files:
            async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
                lines = (await f.read()).split('\n')
            for line in reversed(lines):
                if line.strip():
                    results.append(LogEntry.from_dict(json.loads(line)))
                    if len(results) >= n:
                        return results
        return results[:n]

    async def rotate(self) -> None:
        """§5.5 rotate — 触发日志轮转（→ archive_old_files）"""
        await self.archive_old_files()

    def get_manifest(self) -> dict:
        """§5.5 get_manifest — 返回归档文件清单"""
        if self._manifest is None:
            return {"archive_files": [], "total_entries": 0}
        return {
            "archive_files": list(self._manifest.archive_files.keys()),
            "total_entries": self._manifest.total_entries,
            "recent_files_count": len(self._manifest.recent_files),
            "archive_files_count": len(self._manifest.archive_files),
        }
