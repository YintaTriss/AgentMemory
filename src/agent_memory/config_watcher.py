"""
config_watcher.py — AgentMemory 参数热加载（对标 VCP 的 rag_params.json chokidar watch）

通过 watchdog 监听配置文件变更，实时重载。
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional


HOT_CONFIG_KEY = "HOT_RAG_PARAMS"


class ConfigWatcher:
    """热加载配置监听器"""

    def __init__(self, config_path: str = "rag_params.json",
                 callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.config_path = str(Path(config_path).resolve())
        self.callback = callback
        self._watcher = None
        self._last_mtime = 0
        self._running = False

    def load(self) -> Dict[str, Any]:
        """加载配置文件。"""
        try:
            if not os.path.exists(self.config_path):
                return {}
            mtime = os.path.getmtime(self.config_path)
            with open(self.config_path, encoding='utf-8') as f:
                data = json.load(f)
            self._last_mtime = mtime
            return data
        except (json.JSONDecodeError, IOError) as e:
            print(f"[ConfigWatcher] Error loading {self.config_path}: {e}")
            return {}

    def start(self):
        """启动后台监听（使用 polling 方式，零外部依赖）。"""
        if self._running:
            return
        self._running = True
        self._last_mtime = os.path.getmtime(self.config_path) if os.path.exists(self.config_path) else 0

        import threading
        def _poll():
            while self._running:
                try:
                    if os.path.exists(self.config_path):
                        mtime = os.path.getmtime(self.config_path)
                        if mtime > self._last_mtime:
                            self._last_mtime = mtime
                            data = self.load()
                            if data and self.callback:
                                print(f"[ConfigWatcher] Config changed, reloading...")
                                self.callback(data)
                except Exception:
                    pass
                time.sleep(2)
        t = threading.Thread(target=_poll, daemon=True)
        t.start()

    def stop(self):
        self._running = False
