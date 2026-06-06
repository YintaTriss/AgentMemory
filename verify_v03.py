#!/usr/bin/env python3
"""
AgentMemory v0.3 - End-to-End Verification Script
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, "src")

from agent_memory import MemoryManager


class VerificationReport:
    def __init__(self):
        self.results = []
        self.performance_data = []
        self.logs = []
        self.start_time = datetime.now()
    
    def add_result(self, test_name, passed, details=""):
        self.results.append({"test": test_name, "status": "PASS" if passed else "FAIL", "details": details})
    
    def add_perf(self, operation, elapsed_ms):
        self.performance_data.append({"operation": operation, "elapsed_ms": round(elapsed_ms, 2)})
    
    def add_log(self, message):
        self.logs.append("[" + datetime.now().strftime('%H:%M:%S') + "] " + message)
    
    def generate_report(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = total - passed
        
        lines = []
        lines.append("# AgentMemory v0.3 E2E Verification Report")
        lines.append("")
        lines.append("Generated: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append("| Total Tests | " + str(total) + " |")
        lines.append("| Passed | " + str(passed) + " |")
        lines.append("| Failed | " + str(failed) + " |")
        rate = str(round(passed/total*100, 1)) if total > 0 else "0"
        lines.append("| Pass Rate | " + rate + "% |")
        lines.append("")
        lines.append("## Test Results")
        lines.append("")
        lines.append("| # | Test | Status | Details |")
        lines.append("|---|------|--------|---------|")
        for i, r in enumerate(self.results, 1):
            lines.append("| " + str(i) + " | " + r["test"] + " | **" + r["status"] + "** | " + str(r["details"]) + " |")
        lines.append("")
        lines.append("## Performance Data")
        lines.append("")
        lines.append("| Operation | Time (ms) |")
        lines.append("|-----------|----------|")
        for p in self.performance_data:
            lines.append("| " + p["operation"] + " | " + str(p["elapsed_ms"]) + " |")
        lines.append("")
        lines.append("## Logs")
        lines.append("")
        lines.append("```")
        for log in self.logs:
            lines.append(log)
        lines.append("```")
        lines.append("")
        lines.append("## Known Issues")
        lines.append("")
        lines.append("- Hash-based embedder (no real embedding API)")
        lines.append("- Keyword-based search (not semantic)")
        lines.append("- Layer 2 (Graph) removed in v0.3")
        lines.append("")
        lines.append("## Conclusion")
        lines.append("")
        if failed == 0:
            lines.append("All acceptance criteria PASSED!")
        else:
            lines.append(str(failed) + " test(s) FAILED.")
        return "\n".join(lines)


def cleanup():
    for d in ["memory", "data"]:
        p = Path(d)
        if p.exists():
            for f in p.glob("*"):
                if f.is_file():
                    f.unlink()


def main():
    print("=" * 50)
    print("AgentMemory v0.3 E2E Verification")
    print("=" * 50)
    
    report = VerificationReport()
    
    print("\n[1] Cleanup...")
    cleanup()
    report.add_log("Cleanup done")
    
    print("\n[2] Testing add...")
    mm = MemoryManager()
    start = time.time()
    mem_id = mm.add("Test memory v0.3", category="test")
    elapsed = (time.time() - start) * 1000
    report.add_perf("add", elapsed)
    report.add_result("add", bool(mem_id), "ID: " + mem_id)
    report.add_log("add: " + mem_id)
    
    print("\n[3] Testing L4 files...")
    md = Path("memory") / (mem_id + ".md")
    vec = Path("memory") / (mem_id + ".vec.json")
    meta = Path("memory") / (mem_id + ".meta.json")
    files_ok = md.exists() and vec.exists() and meta.exists()
    report.add_result("L4 files", files_ok, "md=" + str(md.exists()) + ", vec=" + str(vec.exists()) + ", meta=" + str(meta.exists()))
    report.add_log("L4: " + str(files_ok))
    
    print("\n[4] Testing search...")
    start = time.time()
    results = mm.search("Test")
    elapsed = (time.time() - start) * 1000
    report.add_perf("search", elapsed)
    found = any(r["id"] == mem_id for r in results)
    report.add_result("search", found, "Found " + str(len(results)) + " results")
    report.add_log("search: " + str(found))
    
    print("\n[5] Testing list...")
    start = time.time()
    memories = mm.list_all()
    elapsed = (time.time() - start) * 1000
    report.add_perf("list", elapsed)
    list_ok = any(m["id"] == mem_id for m in memories)
    report.add_result("list", list_ok, str(len(memories)) + " memories")
    report.add_log("list: " + str(len(memories)))
    
    print("\n[6] Testing category...")
    cats = mm.get_categories()
    report.add_result("category", len(cats) > 0, str(len(cats)) + " categories")
    report.add_log("category: " + str(cats))
    
    print("\n[7] Testing stats...")
    stats = mm.stats()
    has_layers = "layers" in stats
    l4_count = stats.get("layers", {}).get("L4_Files", {}).get("memory_count", 0)
    report.add_result("stats", has_layers, "L4: " + str(l4_count))
    report.add_log("stats: " + str(stats))
    
    print("\n[8] Testing delete...")
    deleted = mm.delete(mem_id)
    remaining = mm.list_all()
    not_exists = not any(m["id"] == mem_id for m in remaining)
    report.add_result("delete", deleted and not_exists, "Deleted: " + str(deleted))
    report.add_log("delete: " + str(deleted))
    
    # Write report
    with open("VERIFICATION_REPORT.md", "w", encoding="utf-8") as f:
        f.write(report.generate_report())
    
    print("\n" + "=" * 50)
    total = len(report.results)
    passed = sum(1 for r in report.results if r["status"] == "PASS")
    print("Passed: " + str(passed) + "/" + str(total))
    print("Report: VERIFICATION_REPORT.md")
    print("=" * 50)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
