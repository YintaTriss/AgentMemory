# AgentMemory v0.3 E2E Verification Report

Generated: 2026-06-07 00:31:42

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | 7 |
| Passed | 7 |
| Failed | 0 |
| Pass Rate | 100.0% |

## Test Results

| # | Test | Status | Details |
|---|------|--------|---------|
| 1 | add | **PASS** | ID: f5618124e7428abc |
| 2 | L4 files | **PASS** | md=True, vec=True, meta=True |
| 3 | search | **PASS** | Found 1 results |
| 4 | list | **PASS** | 1 memories |
| 5 | category | **PASS** | 1 categories |
| 6 | stats | **PASS** | L4: 1 |
| 7 | delete | **PASS** | Deleted: True |

## Performance Data

| Operation | Time (ms) |
|-----------|----------|
| add | 1.6 |
| search | 0.27 |
| list | 0.45 |

## Logs

```
[00:31:42] Cleanup done
[00:31:42] add: f5618124e7428abc
[00:31:42] L4: True
[00:31:42] search: True
[00:31:42] list: 1
[00:31:42] category: ['test']
[00:31:42] stats: {'total_memories': 1, 'layers': {'L4_Files': {'memory_count': 1, 'total_size_bytes': 2492, 'storage_dir': 'memory'}, 'L3_Vector': {'memory_count': 1, 'engine': 'simple-json'}}, 'embedder': 'hash'}
[00:31:42] delete: True
```

## Known Issues

- Hash-based embedder (no real embedding API)
- Keyword-based search (not semantic)
- Layer 2 (Graph) removed in v0.3

## Conclusion

All acceptance criteria PASSED!