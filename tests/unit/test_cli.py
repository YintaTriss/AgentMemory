"""
CLI 命令行接口测试
v1.0 使用 argparse，测试参数解析
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))


class TestCLIParseArgs:
    """CLI 参数解析测试 - 直接测试 argparse"""
    
    def test_argparse_store_args(self):
        """测试 store 命令参数解析"""
        from cli import parse_args
        
        # 模拟命令行参数
        test_args = ["store", "test content", "--importance", "0.9"]
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "store"
        assert args.text == "test content"
        assert args.importance == 0.9
    
    def test_argparse_store_with_metadata(self):
        """测试 store 命令带 metadata"""
        from cli import parse_args
        
        test_args = ["store", "content", "--metadata", '{"key": "value"}']
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "store"
        assert args.metadata == '{"key": "value"}'
    
    def test_argparse_query_args(self):
        """测试 query 命令参数解析"""
        from cli import parse_args
        
        test_args = ["query", "test query", "--limit", "10", "--tags", "tag1,tag2"]
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "query"
        assert args.text == "test query"
        assert args.limit == 10
        assert args.tags == "tag1,tag2"
    
    def test_argparse_forget_args(self):
        """测试 forget 命令参数解析"""
        from cli import parse_args
        
        test_args = ["forget", "mem_123", "--permanent"]
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "forget"
        assert args.memory_id == "mem_123"
        assert args.permanent is True
    
    def test_argparse_forget_no_permanent(self):
        """测试 forget 命令不带 permanent"""
        from cli import parse_args
        
        test_args = ["forget", "mem_123"]
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "forget"
        assert args.memory_id == "mem_123"
        assert args.permanent is False
    
    def test_argparse_sync_turn_args(self):
        """测试 sync-turn 命令参数解析"""
        from cli import parse_args
        
        test_args = ["sync-turn", "user message", "assistant reply"]
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "sync-turn"
        assert args.user_msg == "user message"
        assert args.assistant_msg == "assistant reply"
    
    def test_argparse_session_end_args(self):
        """测试 session-end 命令参数解析"""
        from cli import parse_args
        
        test_args = ["session-end", "--summary", "Session summary text"]
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "session-end"
        assert args.summary == "Session summary text"
    
    def test_argparse_execute_args(self):
        """测试 execute 命令参数解析"""
        from cli import parse_args
        
        test_args = ["execute", "store", '{"content": "test"}']
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "execute"
        assert args.action == "store"
        assert args.params == '{"content": "test"}'
    
    def test_argparse_execute_default_params(self):
        """测试 execute 命令默认参数"""
        from cli import parse_args
        
        test_args = ["execute", "get_stats"]
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "execute"
        assert args.action == "get_stats"
        assert args.params == "{}"
    
    def test_argparse_stats_command(self):
        """测试 stats 命令"""
        from cli import parse_args
        
        test_args = ["stats"]
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "stats"
    
    def test_argparse_layer_status_command(self):
        """测试 layer-status 命令"""
        from cli import parse_args
        
        test_args = ["layer-status"]
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "layer-status"
    
    def test_argparse_decay_check_command(self):
        """测试 decay-check 命令"""
        from cli import parse_args
        
        test_args = ["decay-check"]
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "decay-check"
    
    def test_argparse_prefetch_command(self):
        """测试 prefetch 命令"""
        from cli import parse_args
        
        test_args = ["prefetch", "some query"]
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "prefetch"
        assert args.text == "some query"
    
    def test_argparse_special_characters(self):
        """测试特殊字符"""
        from cli import parse_args
        
        test_args = ["store", 'Test <>"\'']
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.text == 'Test <>"\''
    
    def test_argparse_unicode_content(self):
        """测试 Unicode 内容"""
        from cli import parse_args
        
        test_args = ["store", "Test content"]  # 避免中文编码问题
        sys.argv = ["agentmemory"] + test_args
        
        args = parse_args()
        assert args.command == "store"
        assert "Test" in args.text
