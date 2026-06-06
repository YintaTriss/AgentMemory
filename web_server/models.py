"""
AgentMemory Web API - 数据模型
定义请求/响应的JSON Schema
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ImportanceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StoreRequest(BaseModel):
    """存储记忆请求"""
    content: str = Field(..., description="记忆内容")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="重要性评分 0-1")
    metadata: Optional[dict] = Field(default=None, description="元数据")
    fact_type: Optional[str] = Field(default="general", description="事实类型")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")


class QueryRequest(BaseModel):
    """查询记忆请求"""
    query: str = Field(..., description="查询文本")
    limit: int = Field(default=5, ge=1, le=100, description="返回结果数量")
    mode: Optional[str] = Field(default="hybrid", description="检索模式: hybrid/vector/category")
    tags: Optional[list[str]] = Field(default=None, description="标签过滤")


class StoreResponse(BaseModel):
    """存储记忆响应"""
    success: bool
    memory_id: str
    content: str
    importance: float
    created_at: str


class MemoryResult(BaseModel):
    """记忆查询结果项"""
    id: str
    content: str
    score: float
    importance: float
    fact_type: str
    tags: list[str]
    created_at: str
    entities: Optional[list[dict]] = None


class QueryResponse(BaseModel):
    """查询记忆响应"""
    success: bool
    query: str
    results: list[MemoryResult]
    total: int
    mode: str


class StatsResponse(BaseModel):
    """统计信息响应"""
    success: bool
    layers: dict
    vector: Optional[dict] = None
    graph: Optional[dict] = None
    file: Optional[dict] = None


class PrefetchResponse(BaseModel):
    """预取响应"""
    success: bool
    query: str
    prefetched_count: int


class ForgetRequest(BaseModel):
    """遗忘记忆请求"""
    memory_id: str
    permanent: bool = Field(default=False, description="是否永久删除")


class ForgetResponse(BaseModel):
    """遗忘响应"""
    success: bool
    memory_id: str
    message: str


class SyncTurnRequest(BaseModel):
    """对话轮次同步请求"""
    user_msg: str = Field(..., description="用户消息")
    assistant_msg: str = Field(..., description="助手消息")


class SyncTurnResponse(BaseModel):
    """对话轮次同步响应"""
    success: bool
    facts_extracted: int
    facts: list[dict]


class DecayCheckResponse(BaseModel):
    """遗忘检查响应"""
    success: bool
    forgotten: int
    archived: int
    retained: int
    message: str


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None
    code: str


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    layers_enabled: dict
