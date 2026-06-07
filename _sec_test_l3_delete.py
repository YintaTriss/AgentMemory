"""验证 L3LanceDBStore.delete() 的 lancedb 路径缺少 return"""
import sys, tempfile, shutil, os
sys.path.insert(0, 'src')
from agent_memory.l3_lancedb import L3LanceDBStore

test_dir = tempfile.mkdtemp(prefix='am_l3del_')
db_path = os.path.join(test_dir, 'lancedb')
os.makedirs(db_path, exist_ok=True)

l3 = L3LanceDBStore(db_path=db_path)
print(f"  is_using_fallback: {l3.is_using_fallback}")
print(f"  hasattr(_fallback_data): {hasattr(l3, '_fallback_data')}")

# 测试 lancedb 路径
vec = [0.1, 0.2, 0.3] * 100 + [0.0] * 52
l3.upsert(id='test1', content='hello', vector=vec)
cnt_before = l3.count()
print(f"  count before delete: {cnt_before}")

result = l3.delete('test1')
print(f"  delete() return: {result!r}  (期望 True 或 False，**实际 None**)")
print(f"  type: {type(result).__name__}")

cnt_after = l3.count()
print(f"  count after delete: {cnt_after}")
print(f"  *** count decreased? {cnt_after < cnt_before} ***")

shutil.rmtree(test_dir, ignore_errors=True)
