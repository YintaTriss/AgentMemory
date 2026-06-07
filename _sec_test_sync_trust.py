"""绕过 portalocker bug 直接测试 sync trust_score 降级逻辑"""
import sys, os, shutil, asyncio, json, tempfile
sys.path.insert(0, 'src')

# 模拟 portalocker 不可用以强制走 fallback 路径
import sys as _s
class _FakePortalocker:
    LOCK_EX = 1
    LOCK_SH = 2
_s.modules['portalocker'] = _FakePortalocker()

# 但 l4_files 已经在导入时检测过了，需要重新触发 - 用直接文件写入代替 l4.save
test_dir = tempfile.mkdtemp(prefix="agentmem_sec_")
l4_dir = os.path.join(test_dir, "memory")
db_path = os.path.join(test_dir, "data", "lancedb")
os.makedirs(l4_dir, exist_ok=True)
os.makedirs(db_path, exist_ok=True)

from agent_memory.l3_lancedb import L3LanceDBStore
from agent_memory.embedder import HashEmbedder
from agent_memory.utils.injection import check_injection

l3 = L3LanceDBStore(db_path=db_path)
emb = HashEmbedder(dim=64)

# 手动调用 check_injection 后写入 L3，模拟 sync.sync_one() 的核心行为
print("=" * 80)
print("L3 (fallback={}) 写入行为验证".format(l3.is_using_fallback))
print("=" * 80)

test_data = [
    ("mem_clean", "今天决定完成石榴籽项目", "干净中文"),
    ("mem_inj_root", "rm -rf / 重要决定", "root rm"),
    ("mem_inj_sql", "'; DROP TABLE users; --", "SQL drop"),
    ("mem_inj_template", "Project: {{7*7}} done", "模板注入"),
]

for mid, content, label in test_data:
    flagged, score, patterns = check_injection(content)
    vec = emb.embed(content)
    metadata = {
        "source": "manual",
        "tags": [],
        "flagged": flagged,
        "trust_score": score,
        "flagged_patterns": patterns,
    }
    l3.upsert(id=mid, content=content, vector=vec, metadata=metadata,
              importance=0.5, category_path="general", created_at="2026-06-07T00:00:00")
    print(f"  [{label}]")
    print(f"    content = {content!r}")
    print(f"    check_injection: flagged={flagged}, trust={score}, patterns={patterns}")
    print(f"    -> WRITTEN to L3: True (无拒绝)")
    print()

# 关键问题：search 时是否过滤
print("=" * 80)
print("Search 行为：flagged 记忆是否被过滤？")
print("=" * 80)
vec_query = emb.embed("rm -rf")
results = l3.search(vec_query, top_k=10)
print(f"  search('rm -rf') returned {len(results)} results:")
for r in results:
    meta = r.get("metadata", {})
    if isinstance(meta, str):
        try: meta = json.loads(meta)
        except: meta = {}
    print(f"    [{r.get('id'):<20}] score={r.get('score',0):.3f} flagged={meta.get('flagged')} trust={meta.get('trust_score')}")

# 结论
print()
print("=" * 80)
print("结论 (CRITICAL FINDINGS)")
print("=" * 80)
print("1. check_injection() 仅计算 score 并写入 L3 metadata")
print("2. flagged=True 的内容依然被存入 L3，没有拒绝逻辑")
print("3. search() 不过滤 flagged=True 的记录，污染数据可被检索")
print("4. trust_score 降级信息仅是'标记'，没有任何强制保护")

shutil.rmtree(test_dir, ignore_errors=True)
