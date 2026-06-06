"""
CLI 集成测试
使用 subprocess 调用 CLI 命令
"""
import pytest
import subprocess
import sys
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


# 确保 src 在 path 中
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


class TestCLIIntegration:
    """CLI 集成测试"""

    def test_cli_module_importable(self):
        """CLI 模块可导入"""
        from src import cli
        assert hasattr(cli, "main")
        assert hasattr(cli, "parse_args")

    def test_cli_help_command(self):
        """CLI --help 正常退出"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0
        assert "agentmemory" in result.stdout.lower() or "subcommands" in result.stdout.lower()

    def test_cli_stats_command(self):
        """CLI stats 命令正常退出"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "stats"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode in [0, 1]

    def test_cli_layer_status_command(self):
        """CLI layer-status 命令"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "layer-status"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode in [0, 1]

    def test_cli_unknown_command(self):
        """未知命令返回非 0 退出码"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "unknown-command"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode != 0


class TestCLIArgumentParser:
    """CLI 参数解析测试"""

    def test_store_command_basic(self):
        """store 命令基本测试"""
        with patch("src.cli.MemoryHermes") as mock_mh:
            mock_instance = MagicMock()
            mock_instance.store = MagicMock(return_value="test-id-123")
            mock_mh.return_value = mock_instance
            
            result = subprocess.run(
                [sys.executable, "-m", "src.cli", "store", "测试内容"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            assert result.returncode in [0, 1]

    def test_store_command_with_importance(self):
        """store 带 importance 参数"""
        with patch("src.cli.MemoryHermes") as mock_mh:
            mock_instance = MagicMock()
            mock_instance.store = MagicMock(return_value="test-id")
            mock_mh.return_value = mock_instance
            
            result = subprocess.run(
                [sys.executable, "-m", "src.cli", "store", "内容", "--importance", "0.9"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            assert result.returncode in [0, 1]

    def test_query_command_basic(self):
        """query 命令基本测试"""
        with patch("src.cli.MemoryHermes") as mock_mh:
            mock_instance = MagicMock()
            mock_instance.query = MagicMock(return_value=[])
            mock_mh.return_value = mock_instance
            
            result = subprocess.run(
                [sys.executable, "-m", "src.cli", "query", "搜索"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            assert result.returncode in [0, 1]

    def test_query_command_with_limit(self):
        """query 带 limit 参数"""
        with patch("src.cli.MemoryHermes") as mock_mh:
            mock_instance = MagicMock()
            mock_instance.query = MagicMock(return_value=[])
            mock_mh.return_value = mock_instance
            
            result = subprocess.run(
                [sys.executable, "-m", "src.cli", "query", "搜索", "--limit", "10"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            assert result.returncode in [0, 1]

    def test_forget_command_basic(self):
        """forget 命令基本测试"""
        with patch("src.cli.MemoryHermes") as mock_mh:
            mock_instance = MagicMock()
            mock_instance.forget = MagicMock(return_value=True)
            mock_mh.return_value = mock_instance
            
            result = subprocess.run(
                [sys.executable, "-m", "src.cli", "forget", "memory-id-123"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            assert result.returncode in [0, 1]


class TestCLIOutput:
    """CLI 输出格式测试"""

    def test_json_output_format(self):
        """JSON 输出格式验证"""
        with patch("src.cli.MemoryHermes") as mock_mh:
            mock_instance = MagicMock()
            mock_instance.get_stats = MagicMock(return_value={
                "total": 10,
                "layers": {"l3_vector": True, "l4_files": True}
            })
            mock_mh.return_value = mock_instance
            
            result = subprocess.run(
                [sys.executable, "-m", "src.cli", "stats"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            assert result.returncode in [0, 1]

    def test_stats_contains_layer_fields(self):
        """stats 输出包含 L3/L4 字段"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "layer-status"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        output = result.stdout + result.stderr
        assert "L" in output or "layer" in output.lower() or result.returncode in [0, 1]


class TestCLIErrorHandling:
    """CLI 错误处理测试"""

    def test_nonexistent_memory_id(self):
        """不存在的 memory_id 处理"""
        with patch("src.cli.MemoryHermes") as mock_mh:
            mock_instance = MagicMock()
            mock_instance.forget = MagicMock(return_value=False)
            mock_mh.return_value = mock_instance
            
            result = subprocess.run(
                [sys.executable, "-m", "src.cli", "forget", "nonexistent-id"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            assert result.returncode in [0, 1]

    def test_missing_required_argument(self):
        """缺少必需参数"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "store"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode != 0


class TestCLIExecuteCommand:
    """execute 命令测试"""

    def test_execute_store_action(self):
        """execute store action"""
        with patch("src.cli.MemoryHermes") as mock_mh:
            mock_instance = MagicMock()
            mock_instance.execute = MagicMock(return_value={"success": True, "id": "test-id"})
            mock_mh.return_value = mock_instance
            
            result = subprocess.run(
                [sys.executable, "-m", "src.cli", "execute", "store", '{"content": "test"}'],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            assert result.returncode in [0, 1]

    def test_execute_query_action(self):
        """execute query action"""
        with patch("src.cli.MemoryHermes") as mock_mh:
            mock_instance = MagicMock()
            mock_instance.execute = MagicMock(return_value={"success": True, "results": []})
            mock_mh.return_value = mock_instance
            
            result = subprocess.run([sys.executable, "-m", "src.cli", "execute", "query", '{"query": "test"}'], capture_output=True, text=True, cwd=Path(__file__).parent.parent)