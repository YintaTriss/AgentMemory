"""验证 L3 count() 在 lancedb 路径下返回 0 (bug)"""
import sys, tempfile, shutil, os
sys.path.insert(0, 'src')
from agent_memory.l3_lancedb import L3LanceDBStore

test_dir = tempfile.mkdtemp(prefix='am_cnt_')
db_path = os.path.join(test_dir, 'lancedb')
os.makedirs(db_path, exist_ok=True)

l3 = L3LanceDBStore(db_path=db_path)
print(f"  is_using_fallback: {l3.is_using_fallback}")

vec = [0.1, 0.2, 0.3] * 100 + [0.0] * 52
for i in range(5):
    l3.upsert(id=f'id{i}', content=f'content{i}', vector=vec)

cnt = l3.count()
print(f"  count() returns: {cnt}  (期望 5, **实际 0 表明 lancedb 路径下 count() 完全失效**)")

shutil.rmtree(test_dir, ignore_errors=True)
