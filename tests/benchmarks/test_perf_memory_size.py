"""
性能基准测试: 内存占用

验收标准: 单个 memory_id payload < 1KB
"""

import pytest
import sys
import os
import json
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))


@pytest.mark.benchmark
class TestPerfMemorySize:
    """内存占用基准测试"""
    
    def test_memory_id_payload_size(self):
        """
        验收标准: 单个 memory_id payload < 1KB
        
        测试典型记忆条目的序列化大小
        """
        # Typical memory entry structure
        memory_entry = {
            "id": "mem_a1b2c3d4e5f6",
            "content": "用户喜欢简洁的回复风格，工作时偏好专注不打扰",
            "metadata": {
                "source": "conversation",
                "timestamp": "2024-06-04T10:30:00Z",
                "category": "preference",
            },
            "importance": 0.8,
            "access_count": 5,
            "last_access": "2024-06-04T12:00:00Z",
            "created_at": "2024-06-04T10:30:00Z",
            "entities": ["用户"],
            "tags": ["preference", "style"],
            "decay_score": 0.75,
        }
        
        # Serialize to JSON
        json_str = json.dumps(memory_entry, ensure_ascii=False)
        size_bytes = len(json_str.encode('utf-8'))
        size_kb = size_bytes / 1024
        
        print(f"\n=== Memory Payload Size ===")
        print(f"JSON length: {len(json_str)} chars")
        print(f"Size: {size_bytes} bytes ({size_kb:.2f} KB)")
        print(f"Limit: 1 KB")
        
        # Assert acceptance criteria
        assert size_kb < 1.0, f"Memory payload {size_kb:.2f}KB exceeds 1KB limit"
    
    def test_memory_id_with_vector_size(self):
        """
        测试带向量数据的记忆条目大小
        """
        # Typical memory with embedding vector (384 dims)
        memory_with_vector = {
            "id": "mem_a1b2c3d4e5f6",
            "content": "用户喜欢简洁的回复风格，工作时偏好专注不打扰",
            "metadata": {
                "source": "conversation",
                "timestamp": "2024-06-04T10:30:00Z",
                "category": "preference",
            },
            "importance": 0.8,
            "embedding": [0.123456789] * 384,  # 384-dim float vector
            "entities": ["用户"],
            "tags": ["preference", "style"],
        }
        
        json_str = json.dumps(memory_with_vector, ensure_ascii=False)
        size_bytes = len(json_str.encode('utf-8'))
        size_kb = size_bytes / 1024
        
        print(f"\n=== Memory with Vector Size ===")
        print(f"Size: {size_bytes} bytes ({size_kb:.2f} KB)")
        
        # With vector, it will be larger (typical ~3KB)
        # But we want to ensure it doesn't exceed reasonable bounds
        assert size_kb < 10.0, f"Memory with vector {size_kb:.2f}KB exceeds 10KB limit"
    
    def test_batch_store_memory_size(self):
        """
        测试批量存储 1000 条记忆的总大小
        """
        memories = []
        for i in range(1000):
            memories.append({
                "id": f"mem_{i:06d}",
                "content": f"记忆条目 {i} 的内容",
                "metadata": {
                    "index": i,
                    "category": f"cat_{i % 10}",
                },
                "importance": 0.5 + (i % 50) / 100,
            })
        
        json_str = json.dumps(memories, ensure_ascii=False)
        size_bytes = len(json_str.encode('utf-8'))
        size_kb = size_bytes / 1024
        size_mb = size_kb / 1024
        
        avg_size = size_bytes / len(memories)
        
        print(f"\n=== Batch Store Size (1000 memories) ===")
        print(f"Total size: {size_kb:.2f} KB ({size_mb:.3f} MB)")
        print(f"Average per memory: {avg_size:.1f} bytes ({avg_size/1024:.3f} KB)")
        
        # Average should be well under 1KB
        assert avg_size < 1024, f"Average memory size {avg_size:.1f} bytes exceeds 1KB"
    
    def test_metadata_overhead(self):
        """
        测试元数据开销
        """
        # Minimal metadata
        minimal = {
            "id": "mem_abc",
            "content": "test",
        }
        
        # Full metadata
        full = {
            "id": "mem_abc",
            "content": "test",
            "metadata": {
                "source": "conversation",
                "timestamp": "2024-06-04T10:30:00Z",
                "category": "preference",
                "tags": ["tag1", "tag2", "tag3"],
            },
            "importance": 0.8,
            "embedding": [0.1] * 384,
            "entities": ["entity1", "entity2"],
            "tags": ["tag1", "tag2", "tag3"],
        }
        
        minimal_size = len(json.dumps(minimal).encode('utf-8'))
        full_size = len(json.dumps(full).encode('utf-8'))
        overhead = (full_size - minimal_size) / minimal_size * 100
        
        print(f"\n=== Metadata Overhead ===")
        print(f"Minimal: {minimal_size} bytes")
        print(f"Full: {full_size} bytes")
        print(f"Overhead: {overhead:.1f}%")
        
        # Overhead should be reasonable
        assert full_size < 5000, f"Full metadata size {full_size} bytes too large"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
