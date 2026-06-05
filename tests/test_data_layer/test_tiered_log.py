"""
TieredLog 单元测试

测试 TieredLog 模块的核心功能：
- 分层日志管理
- 热冷分层
- 自动归档
- 持久化
"""

import pytest
import json
import gzip
from pathlib import Path
from datetime import datetime

from agentmemory.data import TieredLog, LogLevel


class TestTieredLogInit:
    """TieredLog 初始化测试"""
    
    def test_init_creates_directories(self, tiered_log: TieredLog):
        """测试初始化创建目录结构"""
        assert tiered_log.logs_dir.exists()
        assert tiered_log.recent_dir.exists()
        assert tiered_log.archive_dir.exists()
    
    def test_init_creates_manifest(self, tiered_log: TieredLog):
        """测试初始化创建清单文件"""
        assert tiered_log.manifest_file.exists()


class TestTieredLogAppend:
    """日志追加测试"""
    
    @pytest.mark.asyncio
    async def test_append_basic(self, tiered_log: TieredLog):
        """测试基本追加"""
        entry = await tiered_log.append("store", memory_id="mem_001")
        
        assert entry is not None
        assert entry.action == "store"
        assert entry.memory_id == "mem_001"
    
    @pytest.mark.asyncio
    async def test_append_with_metadata(self, tiered_log: TieredLog):
        """测试带元数据追加"""
        entry = await tiered_log.append(
            "error",
            level=LogLevel.ERROR.value,
            memory_id="mem_001",
            message="Operation failed",
            metadata={"error": "timeout"}
        )
        
        assert entry.level == LogLevel.ERROR.value
        assert entry.message == "Operation failed"
        assert entry.metadata == {"error": "timeout"}
    
    @pytest.mark.asyncio
    async def test_append_creates_log_file(self, tiered_log: TieredLog):
        """测试追加创建日志文件"""
        await tiered_log.append("store", memory_id="mem_001")
        await tiered_log.flush()
        
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = tiered_log.recent_dir / f"{today}.jsonl"
        
        assert log_file.exists()


class TestTieredLogRead:
    """日志读取测试"""
    
    @pytest.mark.asyncio
    async def test_read_today(self, tiered_log_with_entries: TieredLog):
        """测试读取今天的日志"""
        log = tiered_log_with_entries
        
        entries = []
        async for entry in log.read_today():
            entries.append(entry)
        
        assert len(entries) >= 4
    
    @pytest.mark.asyncio
    async def test_read_by_date(self, tiered_log_with_entries: TieredLog):
        """测试按日期读取"""
        log = tiered_log_with_entries
        
        today = datetime.now().strftime("%Y-%m-%d")
        entries = []
        async for entry in log.read_by_date(today):
            entries.append(entry)
        
        assert len(entries) >= 4
    
    @pytest.mark.asyncio
    async def test_read_by_memory_id(self, tiered_log_with_entries: TieredLog):
        """测试按记忆 ID 读取"""
        log = tiered_log_with_entries
        
        entries = await log.read_by_memory_id("mem_001")
        
        assert len(entries) >= 2
        for entry in entries:
            assert entry.memory_id == "mem_001"


class TestTieredLogFlush:
    """日志刷新测试"""
    
    @pytest.mark.asyncio
    async def test_flush_buffer(self, tiered_log: TieredLog):
        """测试刷新缓冲区"""
        # 添加多条日志
        for i in range(15):  # 超过 buffer_size (10)
            await tiered_log.append(f"action_{i}", memory_id=f"mem_{i}")
        
        # 应该已经刷新到磁盘
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = tiered_log.recent_dir / f"{today}.jsonl"
        
        assert log_file.exists()
        
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        assert len(lines) >= 15


class TestTieredLogArchive:
    """日志归档测试"""
    
    @pytest.mark.asyncio
    async def test_archive_old_files(self, tiered_log: TieredLog):
        """测试归档旧文件"""
        log = tiered_log
        
        # 创建一个旧的日志文件
        old_date = "2020-01-01"
        old_file = log.recent_dir / f"{old_date}.jsonl"
        
        with open(old_file, "w", encoding="utf-8") as f:
            f.write('{"timestamp": "2020-01-01T00:00:00", "action": "test"}\n')
        
        # 手动更新清单
        log._manifest.recent_files[old_date] = {"size": 50, "entries": 1}
        await log._save_manifest()
        
        # 执行归档
        await log.archive_old_files()
        
        # 验证归档
        archive_file = log.archive_dir / f"{old_date}.jsonl.gz"
        assert archive_file.exists()
        
        # 验证旧文件已删除
        assert not old_file.exists()


class TestTieredLogManifest:
    """清单管理测试"""
    
    @pytest.mark.asyncio
    async def test_manifest_update(self, tiered_log_with_entries: TieredLog):
        """测试清单更新"""
        log = tiered_log_with_entries
        
        manifest = log._manifest
        assert manifest is not None
        assert manifest.total_entries >= 4


class TestTieredLogIterator:
    """日志迭代器测试"""
    
    @pytest.mark.asyncio
    async def test_iterate_logs(self, tiered_log_with_entries: TieredLog):
        """测试迭代日志"""
        log = tiered_log_with_entries
        
        count = 0
        async for entry in log.iterate_logs(limit=10):
            count += 1
        
        assert count >= 4
