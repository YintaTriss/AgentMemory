"""验证 L3 search() 传入 numpy array 但 lancedb 期望 FixedSizeListArray - 架构不匹配"""
import sys, tempfile, shutil, os
sys.path.insert(0, 'src')
import numpy as np
from agent_memory.l3_lancedb import L3LanceDBStore

test_dir = tempfile.mkdtemp(prefix='am_qtype_')
db_path = os.path.join(test_dir, 'lancedb')
os.makedirs(db_path, exist_ok=True)

l3 = L3LanceDBStore(db_path=db_path)
print(f"  is_using_fallback: {l3.is_using_fallback}")

vec = [0.1, 0.2, 0.3] * 100 + [0.0] * 52
vec_arr = np.array(vec, dtype=np.float32)

l3.upsert(id='test1', content='hello', vector=vec)
print(f"  count: {l3.count()}")
print(f"  get_all length: {len(l3.get_all())}")

try:
    results = l3.search(vec_arr, top_k=5)
    print(f"  search results: {len(results)}")
except Exception as e:
    print(f"  *** search error: {e} ***")
    print(f"  This is a P0 - search() 完全不能用（即使数据已写入 L3）")

shutil.rmtree(test_dir, ignore_errors=True)
