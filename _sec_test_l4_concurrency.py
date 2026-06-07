"""L4 文件并发安全验证 - 真实多进程并发写同一 memory_id"""
import sys, os, shutil, tempfile, json
sys.path.insert(0, 'src')

# 强制让 PORTALOCKER_AVAILABLE = False 走 fallback
import agent_memory.l4_files as l4_mod
l4_mod.PORTALOCKER_AVAILABLE = False

import asyncio
from agent_memory.l4_files import L4FilesStore
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing as mp

test_dir = tempfile.mkdtemp(prefix='am_conc_')
l4_dir = os.path.join(test_dir, 'mem')
os.makedirs(l4_dir, exist_ok=True)

# === 1. asyncio 并发（协作式，但测试是否能保持一致性）===
print("=" * 80)
print("[1] asyncio.gather: 20 并发写同一 memory_id (fallback mode)")
print("=" * 80)

l4 = L4FilesStore(base_dir=l4_dir)

async def async_concurrent():
    results = []
    errors = []
    async def writer(i):
        try:
            await l4.save('async_target', f'async_v{i}', {'importance': 0.5})
            results.append(i)
        except Exception as e:
            errors.append((i, type(e).__name__, str(e)))
    await asyncio.gather(*[writer(i) for i in range(20)])
    return results, errors

ok, err = asyncio.run(async_concurrent())
print(f"  successes: {len(ok)}/20, errors: {len(err)}")
md_path = os.path.join(l4_dir, 'async_target.md')
meta_path = os.path.join(l4_dir, 'async_target.meta.json')
if os.path.exists(md_path):
    with open(md_path, 'r', encoding='utf-8') as f: content = f.read()
    print(f"  .md final: {content!r}")
if os.path.exists(meta_path):
    with open(meta_path, 'r', encoding='utf-8') as f: meta = json.load(f)
    print(f"  .meta.json final updated_at: {meta.get('updated_at')}")

# === 2. ThreadPoolExecutor 真多线程 ===
print()
print("=" * 80)
print("[2] ThreadPoolExecutor: 10 线程并发写 (fallback mode, 无锁)")
print("=" * 80)

def thread_writer(i, base_dir):
    """每个线程新建 L4FilesStore 共享同一 base_dir"""
    import sys as _s
    _s.path.insert(0, 'src')
    import agent_memory.l4_files as _l4m
    _l4m.PORTALOCKER_AVAILABLE = False  # 强制 fallback
    from agent_memory.l4_files import L4FilesStore as _L4
    l4 = _L4(base_dir=base_dir)
    async def go():
        await l4.save('thread_target', f'thread_v{i}', {'importance': 0.5})
    asyncio.run(go())
    return i

with ThreadPoolExecutor(max_workers=10) as ex:
    futs = [ex.submit(thread_writer, i, l4_dir) for i in range(10)]
    for f in futs:
        try: f.result(timeout=10)
        except Exception as e: print(f"  thread error: {e}")

md_path = os.path.join(l4_dir, 'thread_target.md')
meta_path = os.path.join(l4_dir, 'thread_target.meta.json')
if os.path.exists(md_path):
    with open(md_path, 'r', encoding='utf-8') as f: content = f.read()
    print(f"  .md final: {content!r}")
if os.path.exists(meta_path):
    with open(meta_path, 'r', encoding='utf-8') as f: meta = json.load(f)
    print(f"  .meta.json final updated_at: {meta.get('updated_at')}")

# === 3. 关键检查：是否有 .tmp 残留文件 ===
print()
print("=" * 80)
print("[3] 残留文件检查")
print("=" * 80)
files = os.listdir(l4_dir)
print(f"  all files: {files}")
tmp_residue = [f for f in files if f.endswith('.tmp')]
print(f"  .tmp residue: {tmp_residue}")
lock_residue = [f for f in files if f.startswith('.lock_')]
print(f"  .lock residue: {lock_residue}")

# === 4. 验证 os.replace 的原子性 vs 双写竞争 ===
print()
print("=" * 80)
print("[4] .md vs .meta.json 写时序竞争检测")
print("=" * 80)
# 检查 .md 和 .meta.json 是否同时被更新 - 它们的 updated_at 应该相近
for mid in ['async_target', 'thread_target']:
    mp = os.path.join(l4_dir, f'{mid}.md')
    mtp = os.path.join(l4_dir, f'{mid}.meta.json')
    if os.path.exists(mp) and os.path.exists(mtp):
        m_st = os.stat(mp).st_mtime
        mt_st = os.stat(mtp).st_mtime
        with open(mtp, 'r', encoding='utf-8') as f: meta = json.load(f)
        with open(mp, 'r', encoding='utf-8') as f: content = f.read()
        # 检查 meta 的 updated_at 是否包含索引信息能匹配
        print(f"  [{mid}]")
        print(f"    .md content: {content!r}")
        print(f"    meta updated_at: {meta.get('updated_at')}")
        print(f"    .md mtime={m_st:.3f}, .meta.json mtime={mt_st:.3f}, diff={mt_st - m_st:.3f}s")

shutil.rmtree(test_dir, ignore_errors=True)
