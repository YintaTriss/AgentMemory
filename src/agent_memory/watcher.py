"""
AgentMemory File Watcher — watch memory/ for file changes, auto re-index.

Uses watchdog (Python) for cross-platform file monitoring.
Triggers on: created / modified / deleted memory files (.md / .json).

Events:
  on_created   → add to vector store
  on_modified  → re-embed + update vector
  on_deleted   → remove from vector store

Usage:
  from agent_memory.watcher import MemoryWatcher
  watcher = MemoryWatcher("./memory", callback=my_reindex_fn)
  watcher.start()  # background observer
  watcher.stop()
"""
from __future__ import annotations

import os
import time
import threading
from pathlib import Path
from typing import Callable, Optional, Set

import watchdog.events
import watchdog.observers


class MemoryFileHandler(watchdog.events.PatternMatchingEventHandler):
    """Watches .md / .json files in the memory directory."""

    PATTERNS = ["*.md", "*.json", "*.txt"]

    def __init__(
        self,
        callback: Optional[Callable] = None,
        debounce_ms: int = 2000,
        **kwargs,
    ):
        super().__init__(patterns=self.PATTERNS, **kwargs)
        self.callback = callback
        self.debounce_ms = debounce_ms
        self._pending: Set[str] = set()
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def _debounce(self):
        with self._lock:
            paths = list(self._pending)
            self._pending.clear()
        if self.callback and paths:
            self.callback(paths)

    def _schedule(self, path: str):
        with self._lock:
            self._pending.add(path)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_ms / 1000, self._debounce)
            self._timer.start()

    def on_created(self, event):
        self._schedule(event.src_path)

    def on_modified(self, event):
        self._schedule(event.src_path)

    def on_deleted(self, event):
        self._schedule(event.src_path)

    def on_moved(self, event):
        self._schedule(event.dest_path)


class MemoryWatcher:
    """File system watcher for AgentMemory.

    Example:
        def reindex(paths):
            for path in paths:
                print(f"Re-indexing: {path}")

        watcher = MemoryWatcher("./memory", callback=reindex)
        watcher.start()
        # ... do work ...
        watcher.stop()
    """

    def __init__(
        self,
        memory_root: str = "./memory",
        callback: Optional[Callable] = None,
        recursive: bool = True,
        debounce_ms: int = 2000,
    ):
        self.memory_root = os.path.abspath(memory_root)
        self.callback = callback
        self.recursive = recursive
        self.debounce_ms = debounce_ms
        self._observer: Optional[watchdog.observers.Observer] = None

    def start(self):
        if not os.path.isdir(self.memory_root):
            os.makedirs(self.memory_root, exist_ok=True)
            print(f"[MemoryWatcher] Created root: {self.memory_root}")

        event_handler = MemoryFileHandler(
            callback=self.callback,
            debounce_ms=self.debounce_ms,
        )
        self._observer = watchdog.observers.Observer()
        self._observer.schedule(event_handler, self.memory_root, recursive=self.recursive)
        self._observer.start()
        print(f"[MemoryWatcher] Watching: {self.memory_root}")

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()
            print("[MemoryWatcher] Stopped")

    @property
    def is_alive(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
