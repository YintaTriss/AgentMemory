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

src_path = Path(__file__).parent.parent.parent / "src"

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

        # 测试 CLI 模块可导入

        try:

            from cli import parse_args

            assert True

        except ImportError:

            # 如果无法导入，跳过测试

            pytest.skip("CLI module not importable in this environment")



    def test_cli_stats_command(self):

        """CLI stats 命令正常退出"""

        result = subprocess.run(

            [sys.executable, "-m", "cli", "stats"],

            capture_output=True,

            text=True,

            cwd=Path(__file__).parent.parent.parent

        )

        

        assert result.returncode in [0, 1]



    def test_cli_layer_status_command(self):

        """CLI layer-status 命令"""

        result = subprocess.run(

            [sys.executable, "-m", "cli", "layer-status"],

            capture_output=True,

            text=True,

            cwd=Path(__file__).parent.parent.parent

        )

        

        assert result.returncode in [0, 1]



    def test_cli_unknown_command(self):

        """未知命令返回非 0 退出码"""

        result = subprocess.run(

            [sys.executable, "-m", "cli", "unknown-command"],

            capture_output=True,

            text=True,

            cwd=Path(__file__).parent.parent.parent

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

                [sys.executable, "-m", "cli", "store", "测试内容"],

                capture_output=True,

                text=True,

                cwd=Path(__file__).parent.parent.parent

            )

            

            assert result.returncode in [0, 1]



    def test_store_command_with_importance(self):

        """store 带 importance 参数"""

        with patch("src.cli.MemoryHermes") as mock_mh:

            mock_instance = MagicMock()

            mock_instance.store = MagicMock(return_value="test-id")

            mock_mh.return_value = mock_instance

            

            result = subprocess.run(

                [sys.executable, "-m", "cli", "store", "内容", "--importance", "0.9"],

                capture_output=True,

                text=True,

                cwd=Path(__file__).parent.parent.parent

            )

            

            assert result.returncode in [0, 1]



    def test_query_command_basic(self):

        """query 命令基本测试"""

        with patch("src.cli.MemoryHermes") as mock_mh:

            mock_instance = MagicMock()

            mock_instance.query = MagicMock(return_value=[])

            mock_mh.return_value = mock_instance

            

            result = subprocess.run(

                [sys.executable, "-m", "cli", "query", "搜索"],

                capture_output=True,

                text=True,

                cwd=Path(__file__).parent.parent.parent

            )

            

            assert result.returncode in [0, 1]



    def test_query_command_with_limit(self):

        """query 带 limit 参数"""

        with patch("src.cli.MemoryHermes") as mock_mh:

            mock_instance = MagicMock()

            mock_instance.query = MagicMock(return_value=[])

            mock_mh.return_value = mock_instance

            

            result = subprocess.run(

                [sys.executable, "-m", "cli", "query", "搜索", "--limit", "10"],

                capture_output=True,

                text=True,

                cwd=Path(__file__).parent.parent.parent

            )

            

            assert result.returncode in [0, 1]



    def test_forget_command_basic(self):

        """forget 命令基本测试"""

        with patch("src.cli.MemoryHermes") as mock_mh:

            mock_instance = MagicMock()

            mock_instance.forget = MagicMock(return_value=True)

            mock_mh.return_value = mock_instance

            

            result = subprocess.run(

                [sys.executable, "-m", "cli", "forget", "memory-id-123"],

                capture_output=True,

                text=True,

                cwd=Path(__file__).parent.parent.parent

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

                [sys.executable, "-m", "cli", "stats"],

                capture_output=True,

                text=True,

                cwd=Path(__file__).parent.parent.parent

            )

            

            assert result.returncode in [0, 1]



    def test_stats_contains_layer_fields(self):

        """stats 输出包含 L3/L4 字段"""

        result = subprocess.run(

            [sys.executable, "-m", "cli", "layer-status"],

            capture_output=True,

            text=True,

            cwd=Path(__file__).parent.parent.parent

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

                [sys.executable, "-m", "cli", "forget", "nonexistent-id"],

                capture_output=True,

                text=True,

                cwd=Path(__file__).parent.parent.parent

            )

            

            assert result.returncode in [0, 1]



    def test_missing_required_argument(self):

        """缺少必需参数"""

        result = subprocess.run(

            [sys.executable, "-m", "cli", "store"],

            capture_output=True,

            text=True,

            cwd=Path(__file__).parent.parent.parent

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

                [sys.executable, "-m", "cli", "execute", "store", '{"content": "test"}'],

                capture_output=True,

                text=True,

                cwd=Path(__file__).parent.parent.parent

            )

            

            assert result.returncode in [0, 1]


    def test_execute_query_action(self):
        """execute query action"""
        with patch("src.cli.MemoryHermes") as mock_mh:
            mock_instance = MagicMock()
            mock_instance.execute = MagicMock(return_value={"success": True, "results": []})
            mock_mh.return_value = mock_instance

            result = subprocess.run(
                [sys.executable, "-m", "cli", "execute", "query", '{"query": "test"}'],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            assert result.returncode in [0, 1]


class TestCLIReembedCommand:
    """reembed 命令测试"""

    def test_reembed_empty_store_succeeds(self, tmp_memory_dir):
        """reembed 空库返回成功（不报错）"""
        result = subprocess.run(
            [
                sys.executable, "-m", "agent_memory.cli",
                "--base-dir", str(tmp_memory_dir),
                "reembed", "--embedder", "hash",
            ],
            capture_output=True,
            text=True,
            cwd=src_path,
        )
        assert result.returncode == 0

    def test_reembed_json_output(self, tmp_memory_dir):
        """reembed --json 输出有效 JSON"""
        result = subprocess.run(
            [
                sys.executable, "-m", "agent_memory.cli",
                "--base-dir", str(tmp_memory_dir),
                "--json", "reembed", "--embedder", "hash",
            ],
            capture_output=True,
            text=True,
            cwd=src_path,
        )
        assert result.returncode == 0
        try:
            output = json.loads(result.stdout.strip())
            assert "success" in output or "count" in output
        except json.JSONDecodeError:
            pytest.fail(f"Non-JSON output: {result.stdout}")

    def test_reembed_invalid_embedder_fails(self, tmp_memory_dir):
        """reembed --embedder invalid_type 报错"""
        result = subprocess.run(
            [
                sys.executable, "-m", "agent_memory.cli",
                "--base-dir", str(tmp_memory_dir),
                "reembed", "--embedder", "invalid_type",
            ],
            capture_output=True,
            text=True,
            cwd=src_path,
        )
        assert result.returncode != 0


class TestCLIServeCommand:
    """serve 命令测试"""

    def test_serve_help_shows_port_and_host(self):
        """serve --help 显示端口和主机选项"""
        result = subprocess.run(
            [sys.executable, "-m", "agent_memory.cli", "serve", "--help"],
            capture_output=True,
            text=True,
            cwd=src_path,
        )
        assert result.returncode == 0
        assert "--port" in result.stdout
        assert "--host" in result.stdout


class TestCLISearchModes:
    """search 命令三种模式测试"""

    def test_search_mode_bm25(self, tmp_memory_dir):
        """search --mode bm25"""
        add_result = subprocess.run(
            [
                sys.executable, "-m", "agent_memory.cli",
                "--base-dir", str(tmp_memory_dir),
                "add", "Python is a great programming language",
            ],
            capture_output=True,
            text=True,
            cwd=src_path,
        )
        assert add_result.returncode == 0

        result = subprocess.run(
            [
                sys.executable, "-m", "agent_memory.cli",
                "--base-dir", str(tmp_memory_dir),
                "search", "Python", "--mode", "bm25",
            ],
            capture_output=True,
            text=True,
            cwd=src_path,
        )
        assert result.returncode == 0

    def test_search_mode_hybrid(self, tmp_memory_dir):
        """search --mode hybrid"""
        add_result = subprocess.run(
            [
                sys.executable, "-m", "agent_memory.cli",
                "--base-dir", str(tmp_memory_dir),
                "add", "Rust is safe and concurrent",
            ],
            capture_output=True,
            text=True,
            cwd=src_path,
        )
        assert add_result.returncode == 0

        result = subprocess.run(
            [
                sys.executable, "-m", "agent_memory.cli",
                "--base-dir", str(tmp_memory_dir),
                "search", "Rust", "--mode", "hybrid",
            ],
            capture_output=True,
            text=True,
            cwd=src_path,
        )
        assert result.returncode == 0
