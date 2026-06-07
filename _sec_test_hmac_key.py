"""HMAC 密钥管理审查"""
import sys, os, shutil, tempfile, json, subprocess
from pathlib import Path
sys.path.insert(0, 'src')

from agent_memory.integrity import (
    sign_file, verify_file, verify_folder, sign_all_memories,
    create_signature_key, get_integrity_report
)

# === 1. 密钥来源审查 ===
print("=" * 80)
print("[1] 密钥来源 - grep 检查所有 integrity 调用 + 密钥相关")
print("=" * 80)
result = subprocess.run(
    ['grep', '-rn', '--include=*.py', '-E', 'integrity|sign_file|verify_folder|cmd_sign|cmd_verify|hmac|AGENT_MEMORY_KEY|MEMORY_KEY|os.environ', 'src/'],
    cwd='C:/Users/31683/.openclaw/workspace/AgentMemory',
    capture_output=True, text=True
)
print(result.stdout[:4000])

# === 2. sign/verify 流程 ===
print()
print("=" * 80)
print("[2] 完整 sign/verify 流程")
print("=" * 80)
test_dir = tempfile.mkdtemp(prefix='am_hmac_')
l4_dir = os.path.join(test_dir, 'mem')
os.makedirs(l4_dir, exist_ok=True)

md = Path(l4_dir) / 'mem_abc12345.md'
md.write_text('今天决定完成石榴籽项目', encoding='utf-8')

key = create_signature_key()
print(f"  Key length: {len(key)} bytes (32 expected)")
print(f"  Key (hex, first 32): {key.hex()[:32]}")

sig = sign_file(md, key)
print(f"  Signature: {sig[:32]}...")
ok = verify_file(md, key, sig)
print(f"  Verify (correct key): {ok}")
ok2 = verify_file(md, b'wrong-key', sig)
print(f"  Verify (wrong key): {ok2}")

# === 3. CRITICAL: 默认是否自动签名？===
print()
print("=" * 80)
print("[3] CRITICAL: 默认 add() 是否自动签名？")
print("=" * 80)
shutil.rmtree(test_dir)
test_dir = tempfile.mkdtemp(prefix='am_hmac2_')
l4_dir = os.path.join(test_dir, 'mem')
db_path = os.path.join(test_dir, 'data', 'lancedb')
os.makedirs(l4_dir, exist_ok=True)
os.makedirs(db_path, exist_ok=True)

import asyncio
import agent_memory.l4_files as l4m
l4m.PORTALOCKER_AVAILABLE = False
from agent_memory.l4_files import L4FilesStore

l4 = L4FilesStore(base_dir=l4_dir)
async def add_test():
    await l4.save('mem_test001', '重要决定：完成项目', {'importance': 0.5, 'category_path': 'general'})
asyncio.run(add_test())

meta_path = os.path.join(l4_dir, 'mem_test001.meta.json')
with open(meta_path, 'r', encoding='utf-8') as f: meta = json.load(f)
print(f"  meta.json keys: {list(meta.keys())}")
print(f"  has hmac_signature? {'hmac_signature' in meta}")
if 'hmac_signature' in meta:
    print(f"  hmac_signature = {meta['hmac_signature'][:32]}...")
else:
    print(f"  *** NO HMAC SIGNATURE — 默认 add() 不签名！***")

# === 4. verify_folder 行为 ===
print()
print("=" * 80)
print("[4] verify_folder 行为 (无签名场景)")
print("=" * 80)
key = create_signature_key()
ok, bad = verify_folder(test_dir, key)
print(f"  ok={ok}, bad_files count={len(bad)}")
print(f"  bad_files: {bad}")
print(f"  *** CRITICAL: 即使文件未被篡改，未签名文件也报告为 bad ***")

# === 5. CLI 参数 ===
print()
print("=" * 80)
print("[5] CLI sign/verify --key 参数")
print("=" * 80)
r = subprocess.run(['grep', '-n', '-E', 'sign_parser|verify_parser|key', 'src/agent_memory/cli.py'],
                   cwd='C:/Users/31683/.openclaw/workspace/AgentMemory',
                   capture_output=True, text=True)
lines = [l for l in r.stdout.split('\n') if 'key' in l.lower() or 'sign' in l.lower() or 'verify' in l.lower()]
for l in lines[:10]:
    print(f"  {l}")

# === 6. 密钥泄露面分析 ===
print()
print("=" * 80)
print("[6] 密钥泄露面分析")
print("=" * 80)
print("  [P1] CLI --key 参数: 出现在 shell history / ps 输出")
print("  [P1] 无 os.environ 集成 (除 DASHSCOPE_API_KEY 外)")
print("  [P1] 无 keyring / secret manager 集成")
print("  [P1] 无 .env 加载")
print("  [P0] 默认 add() 不签名 — 攻击者改文件后无任何检测")
print("  [P0] 同一 key 用于所有文件 = 单点泄露全失守")

shutil.rmtree(test_dir, ignore_errors=True)
