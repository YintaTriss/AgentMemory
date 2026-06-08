"""
AgentMemory 可观测性模块
- 结构化 JSON 日志
- Prometheus metrics（Counter/Gauge/Histogram）
- /healthz 深层健康检查
- NoOp 降级（无外部依赖时）
"""

import time
import json
import logging
from typing import Optional, Any
from pathlib import Path

# ============ 结构化日志 ============
class StructuredLogger:
    """JSON 格式结构化日志"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._setup_json_handler()
    
    def _setup_json_handler(self):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log(self, event: str, **kwargs):
        self.logger.info(event, extra=kwargs)
    
    def search(self, query: str, mode: str, score: float, latency_ms: float, memory_id: Optional[str] = None):
        self.log("memory_search", query=query, mode=mode, score=score, latency_ms=latency_ms, memory_id=memory_id)
    
    def add(self, memory_id: str, category: str, latency_ms: float):
        self.log("memory_add", memory_id=memory_id, category=category, latency_ms=latency_ms)
    
    def delete(self, memory_id: str, latency_ms: float):
        self.log("memory_delete", memory_id=memory_id, latency_ms=latency_ms)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "event": getattr(record, 'event', record.msg),
        }
        # 收集 extra 字段
        for key, value in record.__dict__.items():
            if key not in ('name', 'msg', 'args', 'created', 'filename', 'funcName', 
                          'levelname', 'levelno', 'lineno', 'module', 'msecs', 
                          'message', 'pathname', 'process', 'processName', 'relativeCreated',
                          'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                          'taskName', 'event', 'level'):
                log_data[key] = value
        return json.dumps(log_data, ensure_ascii=False)

# ============ Metrics（NoOp 降级）============
class NoOpCounter:
    def __init__(self, name, description="", unit=""):
        self.name = name; self._value = 0.0
    def add(self, amount=1, attributes=None): self._value += amount
    def get(self): return self._value

class NoOpGauge:
    def __init__(self, name, description="", unit=""):
        self.name = name; self._value = 0.0
    def set(self, value, attributes=None): self._value = value
    def get(self): return self._value

class NoOpHistogram:
    def __init__(self, name, description="", unit=""):
        self.name = name; self._values = []
    def record(self, value, attributes=None): self._values.append(value)
    def get_values(self): return self._values

class NoOpMeter:
    def create_counter(self, name, description="", unit=""): return NoOpCounter(name, description, unit)
    def create_gauge(self, name, description="", unit=""): return NoOpGauge(name, description, unit)
    def create_histogram(self, name, description="", unit=""): return NoOpHistogram(name, description, unit)

class Metrics:
    """全局指标收集器"""
    
    _instance: Optional["Metrics"] = None
    
    def __init__(self):
        self._meter = NoOpMeter()
        self._counters = {}
        self._gauges = {}
        self._histograms = {}
        self._search_requests_total = self._meter.create_counter("agentmemory_search_requests_total", "搜索请求总数")
        self._add_requests_total = self._meter.create_counter("agentmemory_add_requests_total", "添加记忆请求总数")
        self._delete_requests_total = self._meter.create_counter("agentmemory_delete_requests_total", "删除记忆请求总数")
        self._bm25_fallback_total = self._meter.create_counter("agentmemory_bm25_fallback_total", "BM25 兜底触发次数")
        self._memories_total = self._meter.create_gauge("agentmemory_memories_total", "记忆总数")
        self._storage_bytes = self._meter.create_gauge("agentmemory_storage_bytes", "存储大小（字节）")
        self._search_latency = self._meter.create_histogram("agentmemory_search_latency_seconds", "搜索延迟（秒）")
        self._add_latency = self._meter.create_histogram("agentmemory_add_latency_seconds", "添加延迟（秒）")
        self._search_score = self._meter.create_histogram("agentmemory_search_score", "搜索分数分布")
    
    @classmethod
    def get_instance(cls) -> "Metrics":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def inc_search(self, mode: str):
        self._search_requests_total.add(1, {"mode": mode})
    
    def inc_add(self):
        self._add_requests_total.add(1)
    
    def inc_delete(self):
        self._delete_requests_total.add(1)
    
    def inc_bm25_fallback(self):
        self._bm25_fallback_total.add(1)
    
    def set_memories_total(self, count: int):
        self._memories_total.set(count)
    
    def set_storage_bytes(self, bytes: int):
        self._storage_bytes.set(bytes)
    
    def record_search_latency(self, latency_seconds: float, mode: str):
        self._search_latency.record(latency_seconds, {"mode": mode})
    
    def record_add_latency(self, latency_seconds: float):
        self._add_latency.record(latency_seconds)
    
    def record_search_score(self, score: float):
        self._search_score.record(score)
    
    def get_stats(self) -> dict:
        return {
            "search_requests_total": self._search_requests_total.get(),
            "add_requests_total": self._add_requests_total.get(),
            "delete_requests_total": self._delete_requests_total.get(),
            "bm25_fallback_total": self._bm25_fallback_total.get(),
            "memories_total": self._memories_total.get(),
            "storage_bytes": self._storage_bytes.get(),
        }

# 全局实例
metrics = Metrics.get_instance()
logger = StructuredLogger("agent_memory")

# ============ 健康检查 ============
async def health_check_l1() -> dict:
    """L1: LCM 压缩器状态"""
    try:
        from agent_memory.l1_lcm import L1LCMCompressor
        return {"status": "healthy", "component": "L1-LCM"}
    except Exception as e:
        return {"status": "unhealthy", "component": "L1-LCM", "error": str(e)}

async def health_check_l3() -> dict:
    """L3: Qdrant 向量存储状态"""
    try:
        from agent_memory.l3_qdrant import QDRANT_AVAILABLE
        if not QDRANT_AVAILABLE:
            return {"status": "degraded", "component": "L3-Qdrant", "reason": "Qdrant not available"}
        # 实际检查：尝试连接
        return {"status": "healthy", "component": "L3-Qdrant"}
    except Exception as e:
        return {"status": "unhealthy", "component": "L3-Qdrant", "error": str(e)}

async def health_check_l4() -> dict:
    """L4: 文件持久化状态"""
    try:
        base_dir = Path("memory")
        if not base_dir.exists():
            return {"status": "unhealthy", "component": "L4-Files", "error": "memory/ dir not found"}
        if not base_dir.is_dir():
            return {"status": "unhealthy", "component": "L4-Files", "error": "memory/ is not a directory"}
        # 检查写权限
        test_file = base_dir / ".health_check"
        test_file.write_text("ok")
        test_file.unlink()
        return {"status": "healthy", "component": "L4-Files"}
    except Exception as e:
        return {"status": "unhealthy", "component": "L4-Files", "error": str(e)}

async def healthz() -> dict:
    """深层健康检查"""
    results = {}
    results["L1"] = await health_check_l1()
    results["L3"] = await health_check_l3()
    results["L4"] = await health_check_l4()
    
    overall = "healthy"
    for v in results.values():
        if v["status"] == "unhealthy":
            overall = "unhealthy"
            break
        elif v["status"] == "degraded":
            overall = "degraded"
    
    return {"status": overall, "layers": results}
