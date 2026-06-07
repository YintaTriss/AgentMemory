"""验证 L3 JSON fallback 多进程并发写损坏"""
import sys, os, tempfile, shutil, json
sys.path.insert(0, 'src')
import multiprocessing as mp
from agent_memory.l3_lancedb import L3LanceDBStore

test_dir = tempfile.mkdtemp(prefix='am_l3fall_')
db_path = os.path.join(test_dir, 'lancedb')
os.makedirs(db_path, exist_ok=True)

# 强制 fallback
import agent_memory.l3_lancedb as l3m
import builtins
real_import = builtins.__import__
def fake_import(name, *args, **kwargs):
    if name == 'lancedb':
        raise ImportError("force fallback")
    return real_import(name, *args, **kwargs)
builtins.__import__ = fake_import

l3 = L3LanceDBStore(db_path=db_path)
print(f"  is_using_fallback: {l3.is_using_fallback}")

vec = [0.1] * 384
def writer(i):
    l3.upsert(id=f'id{i}', content=f'content{i}', vector=vec)

if __name__ == '__main__':
    with mp.Pool(4) as pool:
        pool.map(writer, range(20))
    
    print(f"  fallback_data size: {len(l3._fallback_data)}")
    
    # 验证文件是否损坏
    fp = os.path.join(test_dir, 'data', 'lancedb_fallback.json')
    if os.path.exists(fp):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"  JSON loaded: {len(data)} records")
        except json.JSONDecodeError as e:
            print(f"  *** JSON 损坏: {e} ***")
    else:
        print(f"  fallback file not found: {fp}")
    
    shutil.rmtree(test_dir, ignore_errors=True)
