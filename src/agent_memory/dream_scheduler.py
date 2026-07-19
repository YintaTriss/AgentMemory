"""
Dream Scheduler — 2026-07-15 方向 7

把梦境调度从手动 `auto_dream()` API 升级为可定时触发的调度器。

设计:
- DreamScheduler 封装 schedule + 调度策略
- 不依赖具体 cron 库(避免引入新依赖);纯 datetime 比较
- 用 SQLiteStore.kv_get/kv_set 做持久化,记录上次运行时间
- 支持 schedule 表达式: "every:6h" / "daily:03:00" / "weekly:sun:03:00"

调度表(默认):
- light: 每 6 小时
- deep: 每天 03:00
- rem: 每周日 03:00

集成:
- DreamScheduler(store, namespace).tick() — 单次检查并按需触发
- DreamScheduler(store, namespace).run_forever(interval=60) — 阻塞循环
- MemoryManager.scheduler 属性 — 便捷访问
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Callable

# Schedule 表达式正则
_RE_EVERY = re.compile(r"^every:(\d+)([smhd])$")          # every:6h
_RE_DAILY = re.compile(r"^daily:(\d{1,2}):(\d{2})$")       # daily:03:00
_RE_WEEKLY = re.compile(r"^weekly:(\w{3}):(\d{1,2}):(\d{2})$")  # weekly:sun:03:00


@dataclass
class ScheduleRule:
    """调度规则"""
    phase: str
    schedule: str
    last_run_iso: Optional[str] = None

    def is_due(self, now: Optional[datetime] = None) -> bool:
        """判断现在是否到了该跑的时候"""
        now = now or datetime.now()
        m = _RE_EVERY.match(self.schedule)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            delta = {
                "s": timedelta(seconds=n),
                "m": timedelta(minutes=n),
                "h": timedelta(hours=n),
                "d": timedelta(days=n),
            }[unit]
            if not self.last_run_iso:
                return True
            try:
                last = datetime.fromisoformat(self.last_run_iso)
                return (now - last) >= delta
            except Exception:
                return True
        m = _RE_DAILY.match(self.schedule)
        if m:
            hour, minute = int(m.group(1)), int(m.group(2))
            if now.hour != hour or now.minute != minute:
                return False
            if not self.last_run_iso:
                return True
            try:
                last = datetime.fromisoformat(self.last_run_iso)
                # 同一天已跑过就不跑
                return last.date() != now.date()
            except Exception:
                return True
        m = _RE_WEEKLY.match(self.schedule)
        if m:
            day_str, hour, minute = m.group(1), int(m.group(2)), int(m.group(3))
            day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3,
                       "fri": 4, "sat": 5, "sun": 6}
            if day_str not in day_map:
                return False
            if now.weekday() != day_map[day_str]:
                return False
            if now.hour != hour or now.minute != minute:
                return False
            if not self.last_run_iso:
                return True
            try:
                last = datetime.fromisoformat(self.last_run_iso)
                return last.date() != now.date()
            except Exception:
                return True
        return False


# 默认调度表
DEFAULT_SCHEDULE: Dict[str, str] = {
    "light": "every:6h",
    "deep": "daily:03:00",
    "rem": "weekly:sun:03:00",
}


class DreamScheduler:
    """梦境调度器

    用法:
        scheduler = DreamScheduler(store=sqlite_store, namespace="default")
        while True:
            scheduler.tick()  # 检查并按需触发
            time.sleep(60)
    """

    def __init__(self, store=None, namespace: str = "default",
                 schedule: Optional[Dict[str, str]] = None,
                 callback: Optional[Callable[[str, Dict[str, Any]], None]] = None):
        self.store = store
        self.namespace = namespace
        self.schedule = dict(schedule or DEFAULT_SCHEDULE)
        self.callback = callback  # 触发后回调(phase, result)

    def _load_rules(self) -> Dict[str, ScheduleRule]:
        """从 store 加载调度规则(含上次运行时间)"""
        rules: Dict[str, ScheduleRule] = {}
        for phase, sched_str in self.schedule.items():
            last_run = None
            if self.store:
                try:
                    last_run = self.store.kv_get(f"dream_schedule_{phase}:{self.namespace}")
                except Exception:
                    last_run = None
            rules[phase] = ScheduleRule(
                phase=phase,
                schedule=sched_str,
                last_run_iso=last_run,
            )
        return rules

    def _save_last_run(self, phase: str, dt: datetime) -> None:
        """保存某阶段上次运行时间"""
        if not self.store:
            return
        try:
            self.store.kv_set(
                f"dream_schedule_{phase}:{self.namespace}",
                dt.isoformat(),
            )
        except Exception:
            pass

    def tick(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """单次 tick:检查所有阶段是否到期,按需触发

        Returns:
            {
                "checked_at": ISO 时间,
                "triggered": [{"phase": str, "decision": str, "result": dict}],
                "skipped": [{"phase": str, "reason": str}],
            }
        """
        now = now or datetime.now()
        rules = self._load_rules()
        triggered: list = []
        skipped: list = []

        for phase, rule in rules.items():
            if not rule.is_due(now):
                skipped.append({
                    "phase": phase,
                    "reason": f"未到 {rule.schedule} 时间窗",
                })
                continue
            # 调用 DreamPhaseSelector 二次确认 + DreamEngine 执行
            out = self._run_phase(phase, now)
            triggered.append(out)
            self._save_last_run(phase, now)

        result = {
            "checked_at": now.isoformat(),
            "triggered": triggered,
            "skipped": skipped,
        }
        if self.callback:
            try:
                self.callback("tick", result)
            except Exception:
                pass
        return result

    def _run_phase(self, phase: str, now: datetime) -> Dict[str, Any]:
        """执行一个梦境阶段"""
        out: Dict[str, Any] = {"phase": phase}
        try:
            from .dream_engine import DreamEngine
            if not self.store:
                return {**out, "skipped": "no store"}
            # 【Bug Fix 2026-07-15 调7】DreamEngine 接受 sqlite_store 不是 store
            engine = DreamEngine(sqlite_store=self.store)
            result = engine.dream_cycle(phase=phase, dry_run=False)
            return {**out, "result": result, "decision": "ran"}
        except Exception as e:
            return {**out, "error": str(e), "decision": "failed"}

    def run_forever(self, interval_seconds: int = 60) -> None:
        """阻塞循环(测试/开发用)"""
        while True:
            self.tick()
            time.sleep(interval_seconds)

    def explain_schedule(self) -> str:
        """人类可读的调度表"""
        lines = [f"DreamScheduler (namespace={self.namespace})"]
        for phase, sched_str in self.schedule.items():
            lines.append(f"  - {phase}: {sched_str}")
        return "\n".join(lines)