"""
文件完整性验证模块 - HMAC-SHA256 签名/验证

用于验证记忆文件的完整性和真实性。

P0-4 Security:
- sign_file(path, key): 对文件进行 HMAC-SHA256 签名，结果写入同名的 .meta.json
- verify_folder(root, key): 验证目录下所有记忆文件，返回 (ok, bad_files)
- CLI: agent-memory sign <dir> 和 agent-memory verify <dir>
"""

from __future__ import annotations

import hmac
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple


def sign_file(file_path: Path, key: bytes) -> str:
    """
    P0-4: 对文件进行 HMAC-SHA256 签名，结果追加到同名的 .meta.json

    如果 .meta.json 不存在则创建它。
    如果已存在 hmac_signature 字段则覆盖。

    Args:
        file_path: 要签名的文件路径（.md 文件）
        key: 签名密钥

    Returns:
        签名字符串（十六进制）
    """
    if not isinstance(key, bytes):
        key = key.encode("utf-8")

    content = file_path.read_bytes()
    signature = hmac.new(key, content, hashlib.sha256).hexdigest()

    meta_path = file_path.with_suffix(file_path.suffix + ".meta.json")

    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}
    else:
        meta = {}

    meta["hmac_signature"] = signature
    meta["hmac_algorithm"] = "HMAC-SHA256"
    try:
        meta["signed_at"] = Path(file_path).stat().st_mtime
    except Exception:
        # File deleted or inaccessible between read_bytes and stat (race condition).
        # P2-11 fix: set signed_at to None and document the gap rather than
        # silently omitting the field from what appears to be a complete meta.
        meta["signed_at"] = None

    # Atomic write
    import tempfile
    tmp = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8",
        delete=False, suffix=".tmp",
        dir=str(meta_path.parent),
    )
    try:
        json.dump(meta, tmp, ensure_ascii=False, indent=2)
        tmp.close()
        os.replace(tmp.name, str(meta_path))
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise

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
    if not isinstance(key, bytes):
        key = key.encode("utf-8")

    actual_signature = hmac.new(key, file_path.read_bytes(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(actual_signature, expected_signature)


def verify_folder(root: Path, key: bytes) -> Tuple[bool, List[str]]:
    """
    P0-4: 验证目录下所有记忆文件（.md）的 HMAC 签名

    从对应的 .meta.json 读取 hmac_signature，与重新计算的签名比对。

    Args:
        root: 记忆存储目录
        key: 签名密钥

    Returns:
        Tuple of (ok: bool, bad_files: List[str])
        - ok: True if ALL files verify successfully
        - bad_files: 签名不匹配或无法验证的文件路径列表
    """
    if not isinstance(key, bytes):
        key = key.encode("utf-8")

    bad_files: List[str] = []

    root_path = Path(root)
    if not root_path.is_dir():
        return False, bad_files

    for md_file in root_path.glob("*.md"):
        meta_path = md_file.with_suffix(md_file.suffix + ".meta.json")

        if not meta_path.exists():
            bad_files.append(str(md_file))
            continue

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            bad_files.append(str(md_file))
            continue

        stored_sig = meta.get("hmac_signature")
        if not stored_sig:
            bad_files.append(str(md_file))
            continue

        # Recompute signature
        actual_sig = hmac.new(key, md_file.read_bytes(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(actual_sig, stored_sig):
            bad_files.append(str(md_file))

    return len(bad_files) == 0, bad_files


# --- 以下为原有 API（保留向后兼容）---


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

    # 写入签名文件（legacy .sig 格式）
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


def sign_all_memories(base_dir: Path, key: bytes) -> List[str]:
    """
    对文件夹中所有记忆文件进行签名。

    Writes to .meta.json (current API via sign_file) AND .sig (legacy API
    via sign_memory) for full backward compatibility.

    Args:
        base_dir: 记忆存储目录
        key: 签名密钥

    Returns:
        已签名的记忆 ID 列表
    """
    signed_ids: List[str] = []
    base_path = Path(base_dir)

    for md_file in base_path.glob("*.md"):
        memory_id = md_file.stem
        try:
            # Current API: write signature to .meta.json
            sign_file(md_file, key)
            # Legacy API: also write .sig file for verify_memory() compatibility
            sign_memory(memory_id, base_path, key)
            signed_ids.append(memory_id)
        except Exception:
            # 跳过无法签名的文件
            pass

    return signed_ids


def verify_all_memories(base_dir: Path, key: bytes) -> Dict[str, bool]:
    """
    验证文件夹中所有记忆文件的签名（legacy API）

    Args:
        base_dir: 记忆存储目录
        key: 签名密钥

    Returns:
        验证结果字典 {memory_id: is_valid}
    """
    results: Dict[str, bool] = {}

    for md_file in base_dir.glob("*.md"):
        memory_id = md_file.stem

        sig_file = md_file.with_suffix(".md.sig")
        if not sig_file.exists():
            results[memory_id] = False
            continue

        expected_signature = sig_file.read_text(encoding="utf-8")
        actual_signature = hmac.new(
            key if isinstance(key, bytes) else key.encode("utf-8"),
            md_file.read_bytes(),
            hashlib.sha256,
        ).hexdigest()

        results[memory_id] = hmac.compare_digest(actual_signature, expected_signature)

    return results


def get_integrity_report(folder: Path, key: bytes) -> Dict:
    """
    生成文件夹完整性报告

    Args:
        folder: 记忆存储目录
        key: 签名密钥

    Returns:
        完整性报告字典

    P2-10 fix: use verify_folder (reads .meta.json) instead of
    verify_all_memories (reads .sig files) — these were mismatched.
    sign_all_memories -> .meta.json via sign_file.
    verify_all_memories -> .sig files (legacy). The old code always
    returned all-False because .sig files were never created.
    """
    ok, bad_files = verify_folder(folder, key)

    # Count from .meta.json-based verification
    root_path = Path(folder)
    md_files = list(root_path.glob("*.md")) if root_path.is_dir() else []
    total = len(md_files)
    invalid = len(bad_files)
    valid = total - invalid

    return {
        "total_memories": total,
        "valid_signatures": valid,
        "invalid_signatures": invalid,
        "unsigned_memories": invalid,  # bad_files covers both unsigned and tampered
        "is_verified": ok,
        "bad_files": bad_files,
    }


def create_signature_key() -> bytes:
    """
    创建新的签名密钥

    Returns:
        32 字节的签名密钥
    """
    import secrets
    return secrets.token_bytes(32)
