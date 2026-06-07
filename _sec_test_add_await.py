"""验证 add() 中漏写 await 的关键 bug"""
import sys, asyncio, tempfile, shutil, os
sys.path.insert(0, 'src')
import agent_memory.l4_files as l4m
l4m.PORTALOCKER_AVAILABLE = False
from agent_memory.manager import MemoryManager

test_dir = tempfile.mkdtemp(prefix='am_await_')
l4_dir = os.path.join(test_dir, 'memory')
db_path = os.path.join(test_dir, 'data', 'lancedb')
os.makedirs(l4_dir, exist_ok=True)
os.makedirs(db_path, exist_ok=True)

mm = MemoryManager(base_dir=l4_dir, db_path=db_path)

async def go():
    mid = await mm.add("Test content", importance=0.5)
    print(f"  memory_id: {mid}")
    files_after_add = os.listdir(l4_dir)
    print(f"  files after add: {files_after_add}")
    vec_exists = f"{mid}.vec.json" in files_after_add
    print(f"  *** {mid}.vec.json exists? {vec_exists}  (期望 True) ***")
    cnt = mm.l3.count()
    print(f"  L3 count: {cnt}  (期望 1)")
    # 等待任务完成 (background)
    await asyncio.sleep(0.5)
    files2 = os.listdir(l4_dir)
    print(f"  files after 0.5s wait: {files2}")

asyncio.run(go())
shutil.rmtree(test_dir, ignore_errors=True)
