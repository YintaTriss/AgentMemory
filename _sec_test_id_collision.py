"""验证 _generate_id 的 hash 碰撞 - 同样内容反复 add() 会互相覆盖"""
import sys, asyncio, tempfile, shutil, os
sys.path.insert(0, 'src')
import agent_memory.l4_files as l4m
l4m.PORTALOCKER_AVAILABLE = False
from agent_memory.manager import MemoryManager

test_dir = tempfile.mkdtemp(prefix='am_id_')
l4_dir = os.path.join(test_dir, 'memory')
db_path = os.path.join(test_dir, 'data', 'lancedb')
os.makedirs(l4_dir, exist_ok=True)
os.makedirs(db_path, exist_ok=True)

mm = MemoryManager(base_dir=l4_dir, db_path=db_path)

async def go():
    content = "今天要完成石榴籽项目"
    id1 = await mm.add(content, importance=0.5)
    id2 = await mm.add(content, importance=0.9)
    id3 = await mm.add(content, importance=0.1)
    print(f"  id1={id1}, id2={id2}, id3={id3}")
    print(f"  All same ID? {id1 == id2 == id3}")
    mems = await mm.list()
    print(f"  total memories: {len(mems)} (期望 1)")
    if mems:
        print(f"  memory[0].importance: {mems[0].get('importance')} (最后一次是 0.1)")

asyncio.run(go())
shutil.rmtree(test_dir, ignore_errors=True)
