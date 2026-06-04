# AgentMemory 测试体系

> 完整的测试套件，覆盖功能、性能、安全与框架兼容性

## 测试结构

```
tests/
├── unit/                    # 单元测试
│   ├── test_config.py       # 配置管理
│   ├── test_decay_engine.py # 遗忘引擎
│   ├── test_L2_graph_store.py  # 图谱存储
│   ├── test_L3_vector_store.py  # 向量存储
│   ├── test_L4_file_persist.py  # 文件持久化
│   ├── test_memory_manager.py   # 核心管理器
│   └── test_cli.py          # CLI
├── integration/              # 集成测试
├── security/                # 安全测试
│   └── test_security.py     # PII、脱敏、注入防护
├── performance/              # 性能测试
│   └── test_performance.py  # 延迟、吞吐量、内存
├── compatibility/            # 框架兼容性测试
│   └── test_framework_adapters.py
├── fixtures/                 # 测试数据
├── conftest.py             # pytest 配置和共享 fixtures
└── __init__.py
```

## 快速开始

### 安装测试依赖

```bash
cd AgentMemory-upgrade
pip install pytest pytest-asyncio pytest-cov pytest-html
```

### 运行所有测试

```bash
python run_tests.py
```

### 运行特定测试

```bash
# 单元测试
python run_tests.py unit

# 安全测试
python run_tests.py security

# 性能测试
python run_tests.py performance

# 兼容性测试
python run_tests.py compatibility
```

### 生成覆盖率报告

```bash
python run_tests.py --coverage
```

## 测试类型

### 1. 单元测试 (unit/)

每个模块的独立测试：

| 模块 | 测试内容 |
|------|---------|
| `test_config.py` | 配置加载、嵌套获取、默认值 |
| `test_decay_engine.py` | 衰减因子、遗忘评分、归档逻辑 |
| `test_L2_graph_store.py` | 实体/关系 CRUD、邻居查询、最短路径 |
| `test_L3_vector_store.py` | 向量操作、BM25、混合检索 |
| `test_L4_file_persist.py` | 文件存储、日记、会话总结 |
| `test_memory_manager.py` | 核心 API、存储、查询、遗忘 |
| `test_cli.py` | 命令行接口、参数验证 |

### 2. 安全测试 (security/)

| 测试类 | 覆盖内容 |
|--------|---------|
| `TestPIIDetection` | 手机号、邮箱、身份证、信用卡检测 |
| `TestPIIRedaction` | PII 脱敏、批量处理 |
| `TestInputValidation` | SQL注入、XSS、命令注入防护 |
| `TestAccessControl` | 租户隔离、命名空间隔离 |
| `TestEncryption` | 记忆加密、文件加密 |
| `TestRateLimiting` | 速率限制、限流重置 |

### 3. 性能测试 (performance/)

| 测试类 | 指标 |
|--------|------|
| `TestBenchmark` | 存储/查询延迟、吞吐量、内存使用 |
| `TestScalability` | 小/中/大数据集、并发写入 |
| `TestDecayPerformance` | 遗忘检查性能 |
| `TestGraphPerformance` | 图谱操作性能 |
| `TestVectorPerformance` | 向量操作性能 |

**性能目标**：
- 存储延迟: < 100ms 平均
- 查询延迟: < 200ms 平均
- 吞吐量: > 5 TPS
- 遗忘检查: < 5s (100条)
- 内存使用: < 500MB (1000条)

### 4. 兼容性测试 (compatibility/)

| 适配器 | 状态 |
|--------|------|
| Claude Code | ✅ |
| OpenClaw | ✅ |
| LangChain | 计划中 |
| OpenAI Agents | 计划中 |
| CrewAI | 计划中 |

## pytest 标记

```bash
# 运行非慢速测试
pytest -m "not slow"

# 只运行安全测试
pytest -m security

# 只运行性能测试
pytest -m performance

# 跳过 API 测试
pytest -m "not api"
```

## CI/CD 集成

### GitHub Actions

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: pip install -e ".[dev]"
      - run: python run_tests.py --coverage
      - uses: codecov/codecov-action@v3
```

## 测试覆盖率目标

| 指标 | 目标 |
|------|------|
| 总体覆盖率 | ≥ 80% |
| 核心模块 | 100% |
| 关键路径 | 100% |
| 公共 API | 100% |

## 报告

测试报告会自动生成到：
- HTML 报告: `test_report.html`
- 覆盖率报告: `htmlcov/index.html`

## 贡献测试

编写新测试时请遵循：

1. **命名规范**: `test_<模块>_<功能>.py`
2. **测试类**: `Test<ClassName>`
3. **测试函数**: `test_<行为>_<预期结果>`
4. **文档字符串**: 描述测试目的
5. **断言消息**: 提供有意义的错误信息

示例：

```python
class TestMemoryHermesQuery:
    """查询功能测试"""
    
    @pytest.mark.asyncio
    async def test_query_returns_results(self, temp_dir):
        """应该返回匹配的查询结果"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        await mh.execute("store", {
            "content": "测试内容",
            "importance": 0.8
        })
        
        result = await mh.execute("query", {"query": "测试"})
        
        assert "results" in result, "结果应包含 results 字段"
        assert len(result["results"]) > 0, "应该返回至少一个结果"
```
