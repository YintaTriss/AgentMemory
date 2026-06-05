"""
Provider 测试包

测试 v2.0 的 Embedder 和 VectorStore Provider 实现。
"""

import sys
from pathlib import Path

# 添加 agentmemory 路径
AGENTMEMORY_SRC = Path(__file__).parent.parent.parent / "agentmemory"
if str(AGENTMEMORY_SRC) not in sys.path:
    sys.path.insert(0, str(AGENTMEMORY_SRC))
