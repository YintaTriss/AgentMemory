"""
Dream Phase Selector — 2026-07-15 方向 5

梦境节奏自适应:不再硬编码 phase,而是根据当前系统状态自动决定该跑哪种梦境。

决策信号:
1. 内存压力 (memory_count) — 越多越需要 light 清理
2. 关联密度 (tag_count / memory_count) — 越密越需要 deep 信号分解
3. 时间间隔 (last_run_*) — 距上次 REM 越长越需要 rem
4. 涌现张力 (emergent_tension) — 越高越需要 deep 重新分解
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List


# 阈值(可被 __init__ 覆盖)
DEFAULT_LIGHT_MEMORY_THRESHOLD = 500  # 超过这个数需要 light 清理
DEFAULT_DEEP_TAG_DENSITY = 0.5        # tags/memories 比例超过这个需要 deep
DEFAULT_REM_DAYS_INTERVAL = 7         # 距上次 REM 超过这么多天需要 rem
DEFAULT_HIGH_TENSION_THRESHOLD = 0.7  # 涌现张力超过这个需要 deep


@dataclass
class DreamPhaseDecision:
    """梦境阶段决策结果"""
    phase: str  # "light" | "deep" | "rem" | "skip"
    reason: str  # 决策理由(可追溯)
    priority: int  # 1=最优先, 3=最低
    signals: Dict[str, Any]  # 原始信号值(供 audit)


class DreamPhaseSelector:
    """根据系统状态选择梦境阶段

    用法:
        selector = DreamPhaseSelector(store=sqlite_store)
        decision = selector.select(namespace="default")
        if decision.phase != "skip":
            engine.dream_cycle(phase=decision.phase, ...)
    """

    def __init__(
        self,
        store=None,
        namespace: str = "default",
        light_memory_threshold: int = DEFAULT_LIGHT_MEMORY_THRESHOLD,
        deep_tag_density: float = DEFAULT_DEEP_TAG_DENSITY,
        rem_days_interval: int = DEFAULT_REM_DAYS_INTERVAL,
        high_tension_threshold: float = DEFAULT_HIGH_TENSION_THRESHOLD,
    ):
        self.store = store
        self.namespace = namespace
        self.light_memory_threshold = light_memory_threshold
        self.deep_tag_density = deep_tag_density
        self.rem_days_interval = rem_days_interval
        self.high_tension_threshold = high_tension_threshold

    def select(self, force: Optional[str] = None) -> DreamPhaseDecision:
        """选择下一个梦境阶段

        Args:
            force: 强制指定阶段("light"/"deep"/"rem"),跳过自动选择

        Returns:
            DreamPhaseDecision
        """
        if force in ("light", "deep", "rem"):
            return DreamPhaseDecision(
                phase=force,
                reason=f"forced by caller",
                priority=0,
                signals={"forced": force},
            )

        # 收集信号
        signals = self._collect_signals()

        # 无 store 时直接 skip(没数据不自动跑)
        if signals.get("_warning") == "no store, returning defaults":
            return DreamPhaseDecision(
                phase="skip",
                reason="未连接 store,跳过自动梦境调度",
                priority=4,
                signals=signals,
            )

        # 决策优先级:rem > deep > light > skip
        # 1. REM 检查 — 距离上次 REM 太久了
        last_rem = signals.get("last_rem_iso")
        if last_rem is None:
            decision = DreamPhaseDecision(
                phase="rem",
                reason="从未执行过 REM 阶段,先建立跨簇虫洞",
                priority=1,
                signals=signals,
            )
        else:
            try:
                last_rem_dt = datetime.fromisoformat(last_rem)
                now = datetime.now(last_rem_dt.tzinfo)
                days_since = (now - last_rem_dt).total_seconds() / 86400.0
                if days_since >= self.rem_days_interval:
                    decision = DreamPhaseDecision(
                        phase="rem",
                        reason=f"距上次 REM 已 {days_since:.1f} 天 (阈值 {self.rem_days_interval})",
                        priority=1,
                        signals=signals,
                    )
                else:
                    decision = None
            except Exception:
                decision = DreamPhaseDecision(
                    phase="rem",
                    reason="无法解析上次 REM 时间,默认执行",
                    priority=1,
                    signals=signals,
                )

        if decision:
            return decision

        # 2. Deep 检查 — 涌现张力高 OR 标签密度高
        tension = signals.get("emergent_tension", 0.0)
        tag_density = signals.get("tag_density", 0.0)
        if tension >= self.high_tension_threshold:
            return DreamPhaseDecision(
                phase="deep",
                reason=f"涌现张力 {tension:.2f} ≥ {self.high_tension_threshold},触发深度信号分解",
                priority=2,
                signals=signals,
            )
        if tag_density >= self.deep_tag_density:
            return DreamPhaseDecision(
                phase="deep",
                reason=f"标签密度 {tag_density:.2f} ≥ {self.deep_tag_density},需要信号分解降维",
                priority=2,
                signals=signals,
            )

        # 3. Light 检查 — 记忆数量超过清理阈值
        mem_count = signals.get("memory_count", 0)
        if mem_count >= self.light_memory_threshold:
            return DreamPhaseDecision(
                phase="light",
                reason=f"记忆数 {mem_count} ≥ {self.light_memory_threshold},触发轻量清理",
                priority=3,
                signals=signals,
            )

        # 4. 默认 skip — 系统健康,无需梦境
        return DreamPhaseDecision(
            phase="skip",
            reason=f"系统健康(记忆 {mem_count} / 张力 {tension:.2f} / 密度 {tag_density:.2f}),无需梦境",
            priority=4,
            signals=signals,
        )

    def _collect_signals(self) -> Dict[str, Any]:
        """收集决策信号"""
        signals: Dict[str, Any] = {"memory_count": 0, "tag_count": 0, "tag_density": 0.0}

        if not self.store:
            signals["_warning"] = "no store, returning defaults"
            return signals

        try:
            # 记忆数量
            memories = self.store.list_memories(namespace=self.namespace, limit=10000)
            signals["memory_count"] = len(memories)

            # 标签数量 + 密度
            tag_count = 0
            try:
                tags = self.store.list_tags(namespace=self.namespace, limit=10000)
                tag_count = len(tags)
            except Exception:
                pass
            signals["tag_count"] = tag_count
            signals["tag_density"] = tag_count / max(1, len(memories))

            # 上次 REM 时间
            try:
                last_rem = self.store.kv_get(f"dream_last_run_rem:{self.namespace}")
                signals["last_rem_iso"] = last_rem
            except Exception:
                pass

            # 涌现张力 (如果有 emergent 表)
            try:
                tension = self.store.kv_get(f"emergent_tension:{self.namespace}")
                signals["emergent_tension"] = float(tension) if tension else 0.0
            except Exception:
                signals["emergent_tension"] = 0.0

        except Exception as e:
            signals["_error"] = str(e)

        return signals

    def explain(self, decision: DreamPhaseDecision) -> str:
        """人类可读的决策解释(供 audit / debug)"""
        lines = [
            f"梦境阶段决策: {decision.phase}",
            f"理由: {decision.reason}",
            f"优先级: {decision.priority}",
            "信号:",
        ]
        for k, v in decision.signals.items():
            lines.append(f"  - {k} = {v}")
        return "\n".join(lines)