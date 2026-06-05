"""
日志捕获工具

用于在测试中捕获日志输出。
"""

import logging
import sys
from io import StringIO
from contextlib import contextmanager
from typing import Generator, Optional


class LogCapture:
    """
    日志捕获器
    
    捕获指定 logger 的日志输出。
    """
    
    def __init__(
        self,
        logger_name: str = "",
        level: int = logging.DEBUG,
        format_string: Optional[str] = None,
    ):
        """
        初始化日志捕获器
        
        Args:
            logger_name: Logger 名称（空字符串表示 root logger）
            level: 捕获的最低日志级别
            format_string: 日志格式字符串
        """
        self.logger_name = logger_name
        self.level = level
        self.format_string = format_string or "%(levelname)s:%(name)s:%(message)s"
        
        self._handler: Optional[logging.Handler] = None
        self._stream: Optional[StringIO] = None
        self._logger: Optional[logging.Logger] = None
        self._original_level: Optional[int] = None
    
    def __enter__(self) -> "LogCapture":
        """开始捕获"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """停止捕获"""
        self.stop()
    
    def start(self) -> None:
        """开始捕获日志"""
        self._logger = logging.getLogger(self.logger_name)
        self._original_level = self._logger.level
        
        # 设置 handler
        self._stream = StringIO()
        self._handler = logging.StreamHandler(self._stream)
        self._handler.setLevel(self.level)
        
        # 设置 formatter
        formatter = logging.Formatter(self.format_string)
        self._handler.setFormatter(formatter)
        
        # 添加 handler
        self._logger.addHandler(self._handler)
        self._logger.setLevel(self.level)
    
    def stop(self) -> None:
        """停止捕获日志"""
        if self._logger and self._handler:
            self._logger.removeHandler(self._handler)
            self._logger.setLevel(self._original_level or logging.NOTSET)
            self._handler.close()
        
        self._handler = None
        self._logger = None
    
    @property
    def output(self) -> str:
        """获取捕获的日志输出"""
        if self._stream:
            return self._stream.getvalue()
        return ""
    
    @property
    def lines(self) -> list[str]:
        """获取捕获的日志行"""
        return self.output.strip().split("\n") if self.output.strip() else []
    
    def contains(self, text: str) -> bool:
        """检查日志是否包含指定文本"""
        return text in self.output
    
    def count_occurrences(self, text: str) -> int:
        """统计文本在日志中出现的次数"""
        return self.output.count(text)
    
    def clear(self) -> None:
        """清空捕获的日志"""
        if self._stream:
            self._stream.truncate(0)
            self._stream.seek(0)


@contextmanager
def capture_logs(
    logger_name: str = "",
    level: int = logging.DEBUG,
) -> Generator[LogCapture, None, None]:
    """
    上下文管理器：捕获日志
    
    用法:
        with capture_logs("my_logger") as capture:
            do_something()
        
        assert capture.contains("expected message")
    
    Args:
        logger_name: Logger 名称
        level: 捕获的最低日志级别
        
    Yields:
        LogCapture 实例
    """
    capture = LogCapture(logger_name=logger_name, level=level)
    capture.start()
    try:
        yield capture
    finally:
        capture.stop()


@contextmanager
def capture_stderr() -> Generator[StringIO, None, None]:
    """
    上下文管理器：捕获 stderr 输出
    
    用法:
        with capture_stderr() as stderr:
            print("error", file=sys.stderr)
        
        assert "error" in stderr.getvalue()
    
    Yields:
        StringIO 实例
    """
    old_stderr = sys.stderr
    stream = StringIO()
    sys.stderr = stream
    try:
        yield stream
    finally:
        sys.stderr = old_stderr


@contextmanager
def capture_stdout() -> Generator[StringIO, None, None]:
    """
    上下文管理器：捕获 stdout 输出
    
    用法:
        with capture_stdout() as stdout:
            print("output")
        
        assert "output" in stdout.getvalue()
    
    Yields:
        StringIO 实例
    """
    old_stdout = sys.stdout
    stream = StringIO()
    sys.stdout = stream
    try:
        yield stream
    finally:
        sys.stdout = old_stdout
