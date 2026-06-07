"""验证默认 add() 是否自动签名"""
import sys, asyncio, tempfile, shutil, os, json
sys.path.insert(0, 'src')
import agent_memory.l4_files as l4m
l4m.PORTALOCKER_AVAILABLE = False
from agent_memory.manager import MemoryManager

test_dir = tempfile.mkdtemp(prefix='am_sign_')
l4_dir = os.path.join(test_dir, 'memory')
db_path = os.path.join(test_dir, 'data', 'lancedb')
os.makedirs(l4_dir, exist_ok=True)
os.makedirs(db_path, exist_ok=True)

mm = MemoryManager(base_dir=l4_dir, db_path=db_path)
async def go():
    await mm.add("重要决定：完成项目", importance=0.5)
asyncio.run(go())

print("files:", os.listdir(l4_dir))
meta_path = [f for f in os.listdir(l4_dir) if f.endswith('.meta.json')][0]
with open(os.path.join(l4_dir, meta_path), 'r', encoding='utf-8') as f:
    meta = json.load(f)
print("meta.json keys:", list(meta.keys()))
print("has hmac_signature?", 'hmac_signature' in meta)
print("*** 默认 add() 不签名 ***")

shutil.rmtree(test_dir, ignore_errors=True)
