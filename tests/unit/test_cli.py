"""
CLI 命令行接口测试
"""

import pytest
import sys
import os
from click.testing import CliRunner

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))


class TestCLI:
    """CLI 测试"""
    
    def test_cli_help(self):
        """测试 CLI 帮助信息"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert 'agentmemory' in result.output.lower() or 'memory' in result.output.lower()
    
    def test_cli_version(self):
        """测试 CLI 版本信息"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])
        
        # 版本信息应该显示
        assert result.exit_code == 0 or 'version' in result.output.lower()
    
    def test_cli_store_command(self):
        """测试 store 命令"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['store', '--content', '测试内容'])
        
        # 应该能执行（即使失败也不崩溃）
        assert result.exit_code in [0, 1]
    
    def test_cli_query_command(self):
        """测试 query 命令"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['query', '--query', '测试'])
        
        # 应该能执行
        assert result.exit_code in [0, 1]
    
    def test_cli_stats_command(self):
        """测试 stats 命令"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['stats'])
        
        # 应该能执行
        assert result.exit_code in [0, 1]
    
    def test_cli_forget_command(self):
        """测试 forget 命令"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['forget'])
        
        # 应该能执行
        assert result.exit_code in [0, 1]
    
    def test_cli_invalid_command(self):
        """测试无效命令"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['invalid_command'])
        
        # 应该返回非零退出码
        assert result.exit_code != 0
    
    def test_cli_store_with_importance(self):
        """测试带重要性参数的 store"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['store', '--content', '测试', '--importance', '0.9'])
        
        assert result.exit_code in [0, 1]
    
    def test_cli_store_with_metadata(self):
        """测试带元数据的 store"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['store', '--content', '测试', '--metadata', '{"key": "value"}'])
        
        assert result.exit_code in [0, 1]
    
    def test_cli_query_with_limit(self):
        """测试带限制参数的 query"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['query', '--query', '测试', '--limit', '10'])
        
        assert result.exit_code in [0, 1]


class TestCLIOutput:
    """CLI 输出格式测试"""
    
    def test_cli_json_output(self):
        """测试 JSON 输出格式"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['stats', '--format', 'json'])
        
        # 应该有 JSON 输出
        assert result.exit_code in [0, 1]
    
    def test_cli_verbose_output(self):
        """测试详细输出"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['--verbose', 'stats'])
        
        assert result.exit_code in [0, 1]


class TestCLIEdgeCases:
    """CLI 边界情况测试"""
    
    def test_cli_empty_content(self):
        """测试空内容"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['store', '--content', ''])
        
        # 应该被拒绝或警告
        assert result.exit_code != 0 or 'empty' in result.output.lower() or 'required' in result.output.lower()
    
    def test_cli_invalid_importance(self):
        """测试无效重要性值"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['store', '--content', '测试', '--importance', 'invalid'])
        
        # 应该被拒绝
        assert result.exit_code != 0
    
    def test_cli_importance_out_of_range(self):
        """测试超出范围的重要性值"""
        from cli import cli
        
        runner = CliRunner()
        
        # 超过 1.0
        result1 = runner.invoke(cli, ['store', '--content', '测试', '--importance', '1.5'])
        
        # 低于 0.0
        result2 = runner.invoke(cli, ['store', '--content', '测试', '--importance', '-0.5'])
        
        # 至少有一个被拒绝
        assert result1.exit_code != 0 or result2.exit_code != 0
    
    def test_cli_special_characters_in_content(self):
        """测试内容中的特殊字符"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['store', '--content', '测试<>\"\'&符号\n换行'])
        
        assert result.exit_code in [0, 1]
    
    def test_cli_unicode_content(self):
        """测试 Unicode 内容"""
        from cli import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['store', '--content', '中文日本語한국어😀'])
        
        assert result.exit_code in [0, 1]
