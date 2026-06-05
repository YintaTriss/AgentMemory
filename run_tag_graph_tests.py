"""
run_tag_graph_tests.py - Direct test runner for tag_graph
Bypasses the circular import issue in agentmemory/__init__.py
"""
import sys, asyncio, tempfile

sys.path.insert(0, '.')

# Direct import bypassing the broken __init__
import importlib.util
spec = importlib.util.spec_from_file_location('tag_graph', 'agentmemory/knowledge/tag_graph.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
TagCooccurrenceGraph = mod.TagCooccurrenceGraph


def edge_key(a, b):
    return (min(a, b), max(a, b))


async def run_tests():
    print('Running all tests...')
    
    # Test 1: add_memory_tags
    with tempfile.TemporaryDirectory() as tmp:
        g = TagCooccurrenceGraph(tmp)
        await g.add_memory_tags('mem_001', ['石榴籽', '省赛', '答辩'])
        await g.add_memory_tags('mem_002', ['石榴籽', '语料'])
        
        assert g.nodes['石榴籽'].frequency == 2, f'石榴籽 freq: {g.nodes["石榴籽"].frequency}'
        assert g.nodes['省赛'].frequency == 1
        ek = edge_key('石榴籽', '省赛')
        assert ek in g.edges, f'Edge {ek} not found'
        assert g.edges[ek].co_count == 1
        print('  test_add_memory_tags: PASS')
    
    # Test 2: remove_memory_tags
    with tempfile.TemporaryDirectory() as tmp:
        g = TagCooccurrenceGraph(tmp)
        await g.add_memory_tags('mem_001', ['石榴籽', '省赛'])
        await g.add_memory_tags('mem_002', ['石榴籽', '语料'])
        await g.remove_memory_tags('mem_001', ['石榴籽', '省赛'])
        assert g.nodes['石榴籽'].frequency == 1
        assert '省赛' not in g.nodes
        assert edge_key('石榴籽', '省赛') not in g.edges
        print('  test_remove_memory_tags: PASS')
    
    # Test 3: get_neighbors
    with tempfile.TemporaryDirectory() as tmp:
        g = TagCooccurrenceGraph(tmp)
        await g.add_memory_tags('mem_001', ['石榴籽', '省赛'])
        await g.add_memory_tags('mem_002', ['石榴籽', '语料'])
        await g.add_memory_tags('mem_003', ['石榴籽', '答辩'])
        
        neighbors = await g.get_neighbors('石榴籽', top_k=3)
        assert len(neighbors) == 3
        tags = [t for t, _ in neighbors]
        weights = [w for _, w in neighbors]
        assert '省赛' in tags and '语料' in tags and '答辩' in tags
        assert weights == sorted(weights, reverse=True)
        print('  test_get_neighbors: PASS')
    
    # Test 4: suggest_tags
    with tempfile.TemporaryDirectory() as tmp:
        g = TagCooccurrenceGraph(tmp)
        await g.add_memory_tags('mem_001', ['石榴籽', '省赛'])
        await g.add_memory_tags('mem_002', ['石榴籽', '语料'])
        await g.add_memory_tags('mem_003', ['石榴籽', '答辩'])
        
        suggestions = await g.suggest_tags(['省赛'], top_k=2)
        suggested_tags = [t for t, _ in suggestions]
        assert '石榴籽' in suggested_tags
        # Verify input is excluded
        suggestions2 = await g.suggest_tags(['A'], top_k=5)
        if suggestions2:
            assert 'A' not in [t for t, _ in suggestions2]
        print('  test_suggest_tags: PASS')
    
    # Test 5: community_discovery
    with tempfile.TemporaryDirectory() as tmp:
        g = TagCooccurrenceGraph(tmp)
        await g.add_memory_tags('mem_001', ['A', 'B', 'C'])
        await g.add_memory_tags('mem_002', ['A', 'B'])
        await g.add_memory_tags('mem_003', ['X', 'Y', 'Z'])
        await g.add_memory_tags('mem_004', ['X', 'Y'])
        
        communities = await g.get_communities(weight_threshold=0.3)
        assert len(communities) >= 2, f'Expected >= 2 communities, got {len(communities)}'
        all_tags = [tag for community in communities for tag in community]
        assert set(all_tags) == {'A', 'B', 'C', 'X', 'Y', 'Z'}
        print('  test_community_discovery: PASS')
    
    # Test 6: search_by_cooccurrence
    with tempfile.TemporaryDirectory() as tmp:
        g = TagCooccurrenceGraph(tmp)
        await g.add_memory_tags('mem_001', ['A', 'B'])
        await g.add_memory_tags('mem_002', ['B', 'C'])
        await g.add_memory_tags('mem_003', ['C', 'D'])
        
        result0 = await g.search_by_cooccurrence(['A'], depth=0)
        assert result0 == ['A']
        
        result1 = await g.search_by_cooccurrence(['A'], depth=2)
        assert 'A' in result1 and 'B' in result1 and 'C' in result1 and 'D' in result1
        print('  test_search_by_cooccurrence: PASS')
    
    # Test 7: persist_and_reload
    with tempfile.TemporaryDirectory() as tmp:
        g = TagCooccurrenceGraph(tmp)
        await g.add_memory_tags('mem_001', ['石榴籽', '省赛'])
        
        g2 = TagCooccurrenceGraph(tmp)
        await g2.load()
        assert '石榴籽' in g2.nodes
        assert g2.nodes['石榴籽'].frequency == 1
        assert edge_key('石榴籽', '省赛') in g2.edges
        print('  test_persist_and_reload: PASS')
    
    # Test 8: weight_normalization
    with tempfile.TemporaryDirectory() as tmp:
        g = TagCooccurrenceGraph(tmp)
        await g.add_memory_tags('mem_001', ['A', 'B'])
        await g.add_memory_tags('mem_002', ['A', 'B'])
        
        edge = g.edges[edge_key('A', 'B')]
        assert edge.co_count == 2
        assert edge.weight == 1.0
        print('  test_weight_normalization: PASS')
    
    # Test 9: empty tags
    with tempfile.TemporaryDirectory() as tmp:
        g = TagCooccurrenceGraph(tmp)
        await g.add_memory_tags('mem_001', [])
        assert len(g.nodes) == 0
        print('  test_empty_tags: PASS')
    
    # Test 10: top_k limit
    with tempfile.TemporaryDirectory() as tmp:
        g = TagCooccurrenceGraph(tmp)
        await g.add_memory_tags('mem_001', ['A', 'B'])
        await g.add_memory_tags('mem_002', ['A', 'C'])
        await g.add_memory_tags('mem_003', ['A', 'D'])
        await g.add_memory_tags('mem_004', ['A', 'E'])
        
        neighbors = await g.get_neighbors('A', top_k=2)
        assert len(neighbors) == 2
        print('  test_top_k_limit: PASS')
    
    print('\n✅ All tests passed!')


if __name__ == '__main__':
    asyncio.run(run_tests())
