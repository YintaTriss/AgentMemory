"""
文件完整性验证模块 - HMAC-SHA256 签名/验证

用于验证记忆文件的完整性和真实性。
"""

import hmac
import hashlib
from pathlib import Path
from typing import Dict, Optional, List


def sign_file(file_path: Path, key: bytes) -> str:
    """
    对单个文件进行 HMAC-SHA256 签名
    
    Args:
        file_path: 要签名的文件路径
        key: 签名密钥
    
    Returns:
        签名字符串（十六进制）
    """
    content = file_path.read_bytes()
    signature = hmac.new(key, content, hashlib.sha256).hexdigest()
    return signature


def verify_file(file_path: Path, key: bytes, expected_signature: str) -> bool:
    """
    验证单个文件的 HMAC-SHA256 签名
    
    Args:
        file_path: 要验证的文件路径
        key: 签名密钥
        expected_signature: 期望的签名字符串
    
    Returns:
        签名是否匹配
    """
    actual_signature = sign_file(file_path, key)
    return hmac.compare_digest(actual_signature, expected_signature)


def sign_memory(memory_id: str, base_dir: Path, key: bytes) -> str:
    """
    对记忆文件（.md）进行签名，签名文件命名为 <id>.md.sig
    
    Args:
        memory_id: 记忆 ID
        base_dir: 记忆存储目录
        key: 签名密钥
    
    Returns:
        签名字符串
    
    Raises:
        FileNotFoundError: 如果记忆文件不存在
    """
    md_file = base_dir / f"{memory_id}.md"
    if not md_file.exists():
        raise FileNotFoundError(f"Memory file not found: {md_file}")
    
    signature = sign_file(md_file, key)
    
    # 写入签名文件
    sig_file = base_dir / f"{memory_id}.md.sig"
    sig_file.write_text(signature, encoding="utf-8")
    
    return signature


def verify_memory(memory_id: str, base_dir: Path, key: bytes) -> bool:
    """
    验证记忆文件的 HMAC-SHA256 签名
    
    Args:
        memory_id: 记忆 ID
        base_dir: 记忆存储目录
        key: 签名密钥
    
    Returns:
        签名是否有效
    """
    sig_file = base_dir / f"{memory_id}.md.sig"
    if not sig_file.exists():
        return False
    
    expected_signature = sig_file.read_text(encoding="utf-8")
    md_file = base_dir / f"{memory_id}.md"
    
    if not md_file.exists():
        return False
    
    return verify_file(md_file, key, expected_signature)


def verify_folder(folder: Path, key: bytes) -> Dict[str, bool]:
    """
    验证文件夹中所有记忆文件的签名
    
    Args:
        folder: 记忆存储目录
        key: 签名密钥
    
    Returns:
        验证结果字典 {memory_id: is_valid}
    """
    results: Dict[str, bool] = {}
    
    # 查找所有 .md 文件
    for md_file in folder.glob("*.md"):
        memory_id = md_file.stem  # 去掉 .md 后缀
        
        # 检查是否有对应的签名文件
        sig_file = md_file.with_suffix(".md.sig")
        if not sig_file.exists():
            results[memory_id] = False
            continue
        
        # 读取期望的签名
        expected_signature = sig_file.read_text(encoding="utf-8")
        
        # 计算实际签名
        actual_signature = sign_file(md_file, key)
        
        # 比较签名
        results[memory_id] = hmac.compare_digest(actual_signature, expected_signature)
    
    return results


def sign_all_memories(base_dir: Path, key: bytes) -> List[str]:
    """
    对文件夹中所有记忆文件进行签名
    
    Args:
        base_dir: 记忆存储目录
        key: 签名密钥
    
    Returns:
        已签名的记忆 ID 列表
    """
    signed_ids: List[str] = []
    
    for md_file in base_dir.glob("*.md"):
        memory_id = md_file.stem
        try:
            sign_memory(memory_id, base_dir, key)
            signed_ids.append(memory_id)
        except Exception:
            # 跳过无法签名的文件
            pass
    
    return signed_ids


def get_integrity_report(folder: Path, key: bytes) -> Dict[str, any]:
    """
    生成文件夹完整性报告
    
    Args:
        folder: 记忆存储目录
        key: 签名密钥
    
    Returns:
        完整性报告字典
    """
    verification_results = verify_folder(folder, key)
    
    total = len(verification_results)
    valid = sum(1 for v in verification_results.values() if v)
    invalid = total - valid
    unsigned = sum(1 for v in verification_results.values() if not v)
    
    return {
        "total_memories": total,
        "valid_signatures": valid,
        "invalid_signatures": invalid,
        "unsigned_memories": unsigned,
        "is_verified": invalid == 0 and unsigned == 0,
        "verification_details": verification_results,
    }


def create_signature_key() -> bytes:
    """
    创建新的签名密钥
    
    Returns:
        32 字节的签名密钥
    """
    import secrets
    return secrets.token_bytes(32)
