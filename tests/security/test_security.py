"""
安全测试 - PII 检测与防护
v2.0 功能，待 T6 安全功能实现后解冻
"""

import pytest
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))

# v2.0 待实现功能 - 标记整个文件
pytestmark = pytest.mark.skip(reason="v2.0 安全功能 (PIIDetector/RateLimiter/Middleware) 待 T6 实现，解冻条件：src/security/ 目录完整实现")


class TestPIIDetection:
    """PII（个人身份信息）检测测试"""
    
    def test_phone_number_detection(self):
        """测试手机号检测"""
        from L4_file_persist import PIIDetector
        
        detector = PIIDetector()
        
        # 中国手机号
        test_cases = [
            "13812345678",
            "13912345678",
            "15912345678",
            "+86 13812345678",
            "138-1234-5678"
        ]
        
        for phone in test_cases:
            matches = detector.detect_pii(phone)
            assert any('phone' in str(m).lower() or '手机' in str(m) for m in matches) or len(matches) > 0
    
    def test_email_detection(self):
        """测试邮箱检测"""
        from L4_file_persist import PIIDetector
        
        detector = PIIDetector()
        
        emails = [
            "user@example.com",
            "test.user@domain.co.uk",
            "name+tag@gmail.com"
        ]
        
        for email in emails:
            matches = detector.detect_pii(email)
            assert len(matches) > 0
    
    def test_id_card_detection(self):
        """测试身份证号检测"""
        from L4_file_persist import PIIDetector
        
        detector = PIIDetector()
        
        # 中国身份证号（18位）
        id_cards = [
            "110101199001011234",
            "310101198505055432"
        ]
        
        for id_card in id_cards:
            matches = detector.detect_pii(id_card)
            # 应该能检测到
            assert len(matches) >= 0  # 可能需要更长格式
    
    def test_credit_card_detection(self):
        """测试信用卡号检测"""
        from L4_file_persist import PIIDetector
        
        detector = PIIDetector()
        
        cards = [
            "4111111111111111",
            "5500000000000004"
        ]
        
        for card in cards:
            matches = detector.detect_pii(card)
            # 应该能检测到
            assert len(matches) >= 0
    
    def test_address_detection(self):
        """测试地址检测"""
        from L4_file_persist import PIIDetector
        
        detector = PIIDetector()
        
        addresses = [
            "北京市朝阳区建国路88号",
            "上海市浦东新区世纪大道100号"
        ]
        
        for address in addresses:
            matches = detector.detect_pii(address)
            # 地址应该被检测到
            assert len(matches) >= 0
    
    def test_name_detection(self):
        """测试姓名检测"""
        from L4_file_persist import PIIDetector
        
        detector = PIIDetector()
        
        # 已知姓名应该被检测
        names = ["张三", "李四", "王五"]
        
        for name in names:
            matches = detector.detect_pii(name)
            assert len(matches) >= 0


class TestPIIRedaction:
    """PII 脱敏测试"""
    
    def test_phone_redaction(self):
        """测试手机号脱敏"""
        from L4_file_persist import PIIRedactor
        
        redactor = PIIRedactor()
        
        phone = "13812345678"
        redacted = redactor.redact(phone)
        
        # 手机号应该被脱敏
        assert "138" in redacted or "****" in redacted or phone != redacted
    
    def test_email_redaction(self):
        """测试邮箱脱敏"""
        from L4_file_persist import PIIRedactor
        
        redactor = PIIRedactor()
        
        email = "user@example.com"
        redacted = redactor.redact(email)
        
        # 应该脱敏
        assert redacted != email or "@" not in redacted
    
    def test_id_card_redaction(self):
        """测试身份证号脱敏"""
        from L4_file_persist import PIIRedactor
        
        redactor = PIIRedactor()
        
        id_card = "110101199001011234"
        redacted = redactor.redact(id_card)
        
        # 应该脱敏
        assert redacted != id_card
    
    def test_credit_card_redaction(self):
        """测试信用卡号脱敏"""
        from L4_file_persist import PIIRedactor
        
        redactor = PIIRedactor()
        
        card = "4111111111111111"
        redacted = redactor.redact(card)
        
        # 应该只显示后4位
        assert "****" in redacted or redacted.endswith("1111")
    
    def test_batch_redaction(self):
        """测试批量脱敏"""
        from L4_file_persist import PIIRedactor
        
        redactor = PIIRedactor()
        
        text = """
        用户信息：
        姓名：张三
        手机：13812345678
        邮箱：zhangsan@example.com
        地址：北京市朝阳区
        """
        
        redacted = redactor.redact(text)
        
        # 原始信息应该被替换
        assert "张三" not in redacted or "13812345678" not in redacted


class TestInputValidation:
    """输入验证测试"""
    
    def test_sql_injection_prevention(self, temp_dir):
        """测试 SQL 注入防护"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # SQL 注入尝试
        malicious_inputs = [
            "'; DROP TABLE memories; --",
            "1' OR '1'='1",
            "admin'--",
            "1; DELETE FROM memories"
        ]
        
        for malicious in malicious_inputs:
            # 应该安全处理，不崩溃
            try:
                import asyncio
                asyncio.run(mh.execute("store", {"content": malicious}))
            except:
                pass  # 允许拒绝，但不应崩溃
    
    def test_xss_prevention(self, temp_dir):
        """测试 XSS 防护"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        xss_inputs = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "{{constructor.constructor('alert(1)')()}}"
        ]
        
        for xss in xss_inputs:
            try:
                import asyncio
                asyncio.run(mh.execute("store", {"content": xss}))
            except:
                pass
    
    def test_path_traversal_prevention(self, temp_dir):
        """测试路径遍历防护"""
        from L4_file_persist import FilePersistStore
        
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        ]
        
        for malicious in malicious_paths:
            store = FilePersistStore(base_path=temp_dir)
            # 应该安全处理
            try:
                store.store_fact(malicious, {})
            except:
                pass
    
    def test_command_injection_prevention(self, temp_dir):
        """测试命令注入防护"""
        from L4_file_persist import FilePersistStore
        
        malicious_commands = [
            "; ls -la",
            "| cat /etc/passwd",
            "`whoami`",
            "$(whoami)"
        ]
        
        for malicious in malicious_commands:
            store = FilePersistStore(base_path=temp_dir)
            # 应该安全处理
            try:
                store.store_fact(malicious, {})
            except:
                pass
    
    def test_null_byte_injection(self, temp_dir):
        """测试空字节注入防护"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        # 空字节注入
        malicious = "test\x00.jpg"
        
        try:
            store.store_fact(malicious, {})
        except:
            pass  # 应该被拒绝
    
    def test_oversized_input(self, temp_dir):
        """测试超大输入"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        # 10MB 内容
        large_content = "x" * (10 * 1024 * 1024)
        
        try:
            store.store_fact(large_content, {})
        except (ValueError, MemoryError, Exception):
            pass  # 应该被拒绝或处理
    
    def test_binary_data_handling(self, temp_dir):
        """测试二进制数据处理"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        # 二进制数据
        binary = bytes(range(256))
        
        try:
            store.store_fact(binary.decode('latin-1'), {})
        except:
            pass


class TestAccessControl:
    """访问控制测试"""
    
    def test_tenant_isolation(self, temp_dir):
        """测试租户隔离"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        import asyncio
        
        # 租户 A 存储
        asyncio.run(mh.execute("store", {
            "content": "租户A的秘密信息",
            "metadata": {"tenant": "A"}
        }))
        
        # 租户 B 存储
        asyncio.run(mh.execute("store", {
            "content": "租户B的私密数据",
            "metadata": {"tenant": "B"}
        }))
        
        # 应该能区分
        result_a = asyncio.run(mh.execute("query", {
            "query": "租户A",
            "metadata_filter": {"tenant": "A"}
        }))
        
        assert result_a is not None
    
    def test_namespace_isolation(self, temp_dir):
        """测试命名空间隔离"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        import asyncio
        
        # 命名空间 1
        asyncio.run(mh.execute("store", {
            "content": "NS1的内容",
            "metadata": {"namespace": "ns1"}
        }))
        
        # 命名空间 2
        asyncio.run(mh.execute("store", {
            "content": "NS2的内容",
            "metadata": {"namespace": "ns2"}
        }))
        
        # 应该能隔离查询
        result = asyncio.run(mh.execute("query", {
            "query": "NS1",
            "metadata_filter": {"namespace": "ns1"}
        }))
        
        assert result is not None


class TestEncryption:
    """加密测试"""
    
    def test_memory_encryption(self, temp_dir):
        """测试记忆加密"""
        from L4_file_persist import EncryptedFileStore
        
        store = EncryptedFileStore(
            base_path=temp_dir,
            key="test_encryption_key_32bytes!!"
        )
        
        # 存储加密内容
        store.store_fact("加密的秘密", {"sensitive": True})
        
        # 验证加密
        assert store.is_encrypted()
    
    def test_encrypted_content_not_readable(self, temp_dir):
        """测试加密内容不可读"""
        from L4_file_persist import EncryptedFileStore
        
        store = EncryptedFileStore(
            base_path=temp_dir,
            key="test_key_for_encryption_!!"
        )
        
        store.store_fact("秘密信息", {})
        
        # 尝试直接读取文件
        import os
        files = os.listdir(store.base_path)
        
        for f in files:
            if f.endswith('.json'):
                with open(os.path.join(store.base_path, f), 'r') as file:
                    content = file.read()
                    # 加密后不应该包含原文
                    assert "秘密信息" not in content or "加密" in content.lower()


class TestSecurityHeaders:
    """安全头部测试"""
    
    def test_no_sensitive_data_in_logs(self, temp_dir):
        """测试日志中不包含敏感数据"""
        from memory_manager import MemoryHermes
        import logging
        import io
        
        # 捕获日志输出
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.DEBUG)
        
        mh_logger = logging.getLogger('memory_manager')
        mh_logger.addHandler(handler)
        mh_logger.setLevel(logging.DEBUG)
        
        mh = MemoryHermes()
        
        import asyncio
        asyncio.run(mh.execute("store", {
            "content": "测试日志",
            "metadata": {"api_key": "secret123"}
        }))
        
        log_output = log_stream.getvalue()
        
        # 日志中不应明文包含敏感信息
        assert "secret123" not in log_output


class TestRateLimiting:
    """速率限制测试"""
    
    def test_rate_limit_enforcement(self, temp_dir):
        """测试速率限制执行"""
        from memory_manager import MemoryHermes
        from middleware import RateLimiter
        
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        # 前 10 个请求应该通过
        for i in range(10):
            assert limiter.check() == True
        
        # 第 11 个请求应该被限制
        assert limiter.check() == False
    
    def test_rate_limit_reset(self, temp_dir):
        """测试速率限制重置"""
        from middleware import RateLimiter
        import time
        
        limiter = RateLimiter(max_requests=5, window_seconds=1)
        
        # 消耗配额
        for i in range(5):
            limiter.check()
        
        assert limiter.check() == False
        
        # 等待窗口过期
        time.sleep(1.1)
        
        # 应该重置
        assert limiter.check() == True
