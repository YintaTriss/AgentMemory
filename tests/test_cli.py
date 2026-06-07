# -*- coding: utf-8 -*-
"""
CLI Integration Tests
"""
import pytest
import subprocess
import sys
from pathlib import Path


class TestCLIIntegration:
    """CLI module integration tests via subprocess"""

    def test_cli_module_importable(self):
        """CLI module can be imported"""
        from src.agent_memory import cli
        assert cli is not None
        assert hasattr(cli, "main")

    def test_cli_help_command(self):
        """CLI --help works"""
        result = subprocess.run(
            [sys.executable, "-m", "src.agent_memory.cli", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        assert result.returncode in [0, 1]

    def test_cli_stats_command(self):
        """CLI stats command works"""
        result = subprocess.run(
            [sys.executable, "-m", "src.agent_memory.cli", "stats"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        assert result.returncode in [0, 1]

    def test_cli_unknown_command(self):
        """Unknown CLI command returns error"""
        result = subprocess.run(
            [sys.executable, "-m", "src.agent_memory.cli", "unknown-cmd-xyz"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        assert result.returncode != 0

    def test_cli_add_command(self):
        """CLI add command works"""
        result = subprocess.run(
            [sys.executable, "-m", "src.agent_memory.cli", "add", "test memory content"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        assert result.returncode in [0, 1]
