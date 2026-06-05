"""
pytest fixtures for data layer tests
"""

import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path
from agentmemory.data import (
    DataLake,
    Library,
    TagIndex,
    EmbeddingStateMachine,
    EmbeddingState,
    TieredLog,
    LogLevel,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
async def datalake(temp_dir):
    """Create a DataLake instance for testing"""
    lake = DataLake(root_dir=temp_dir)
    await lake.init()
    return lake


@pytest.fixture
async def datalake_with_category(temp_dir):
    """Create a DataLake instance with a test category"""
    lake = DataLake(root_dir=temp_dir)
    await lake.init()
    category_path = "A.项目/测试"
    await lake.create_category(category_path)
    return lake, category_path


@pytest.fixture
async def library(temp_dir):
    """Create a Library instance for testing"""
    lib = Library(root_dir=temp_dir)
    await lib.init()
    return lib


@pytest.fixture
async def library_with_categories(temp_dir):
    """Create a Library instance with test categories"""
    lib = Library(root_dir=temp_dir)
    await lib.init()
    
    # Create test categories
    await lib.create_category("A.项目/石榴籽")
    await lib.create_category("A.项目/石榴籽/语料")
    await lib.create_category("A.项目/石榴籽/模型")
    await lib.create_category("B.个人/日记")
    await lib.create_category("C.临时")
    
    return lib


@pytest.fixture
async def tag_index(temp_dir):
    """Create a TagIndex instance for testing"""
    idx = TagIndex(root_dir=temp_dir)
    await idx.init()
    return idx


@pytest.fixture
async def tag_index_with_tags(temp_dir):
    """Create a TagIndex instance with test tags"""
    idx = TagIndex(root_dir=temp_dir)
    await idx.init()
    
    # Add test tags
    await idx.add_tag("重要", "mem_001", "A.项目/石榴籽")
    await idx.add_tag("重要", "mem_002", "A.项目/石榴籽")
    await idx.add_tag("AI", "mem_001", "A.项目/石榴籽")
    await idx.add_tag("测试", "mem_001", "A.项目/石榴籽")
    
    return idx


@pytest.fixture
async def embedding_state(temp_dir):
    """Create an EmbeddingStateMachine instance for testing"""
    sm = EmbeddingStateMachine(root_dir=temp_dir)
    await sm.init()
    return sm


@pytest.fixture
async def embedding_state_machine(temp_dir):
    """Create an EmbeddingStateMachine instance for testing (alias)"""
    sm = EmbeddingStateMachine(root_dir=temp_dir)
    await sm.init()
    return sm


@pytest.fixture
async def embedding_state_machine_with_states(temp_dir):
    """Create an EmbeddingStateMachine instance with test states"""
    sm = EmbeddingStateMachine(root_dir=temp_dir)
    await sm.init()
    
    # Add test states
    await sm.set_state("mem_001", EmbeddingState.PENDING)
    await sm.set_state("mem_002", EmbeddingState.GENERATING)
    await sm.set_state("mem_003", EmbeddingState.COMPLETED, model="bge-large", dimensions=1024)
    
    # Add failed states for testing
    await sm.set_state("mem_004", EmbeddingState.PENDING)
    await sm.set_state("mem_004", EmbeddingState.GENERATING)
    await sm.set_state("mem_004", EmbeddingState.FAILED, error_message="API Error")
    
    await sm.set_state("mem_005", EmbeddingState.PENDING)
    await sm.set_state("mem_005", EmbeddingState.GENERATING)
    await sm.set_state("mem_005", EmbeddingState.FAILED, error_message="Timeout")
    
    return sm


@pytest.fixture
async def tiered_log(temp_dir):
    """Create a TieredLog instance for testing"""
    log = TieredLog(root_dir=temp_dir)
    await log.init()
    return log


@pytest.fixture
async def tiered_log_with_entries(temp_dir):
    """Create a TieredLog instance with test entries"""
    log = TieredLog(root_dir=temp_dir)
    await log.init()
    
    # Add test entries
    await log.append("store", memory_id="mem_001", category_path="A.项目", message="记忆已存储")
    await log.append("store", memory_id="mem_002", category_path="A.项目/石榴籽", message="记忆已存储")
    await log.append("update", memory_id="mem_001", message="记忆已更新")
    await log.append("query", memory_id="mem_003", message="查询成功")
    
    await log.flush()
    
    return log
