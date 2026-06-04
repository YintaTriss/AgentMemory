#!/usr/bin/env python3
"""
测试运行脚本

用法:
    python run_tests.py              # 运行所有测试
    python run_tests.py unit         # 只运行单元测试
    python run_tests.py integration  # 只运行集成测试
    python run_tests.py security     # 只运行安全测试
    python run_tests.py performance   # 只运行性能测试
    python run_tests.py --coverage   # 生成覆盖率报告
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
SRC_PATH = PROJECT_ROOT / "src"


def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}")
    
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=PROJECT_ROOT,
        capture_output=False
    )
    
    return result.returncode == 0


def run_unit_tests(coverage=False):
    """运行单元测试"""
    cmd = "python -m pytest tests/unit -v"
    if coverage:
        cmd += " --cov=src --cov-report=html --cov-report=term"
    return run_command(cmd, "单元测试")


def run_integration_tests(coverage=False):
    """运行集成测试"""
    cmd = "python -m pytest tests/integration -v"
    if coverage:
        cmd += " --cov=src --cov-report=html --cov-report=term"
    return run_command(cmd, "集成测试")


def run_security_tests(coverage=False):
    """运行安全测试"""
    cmd = "python -m pytest tests/security -v"
    if coverage:
        cmd += " --cov=src --cov-report=html --cov-report=term"
    return run_command(cmd, "安全测试")


def run_performance_tests():
    """运行性能测试"""
    cmd = "python -m pytest tests/performance -v -s"
    return run_command(cmd, "性能测试")


def run_compatibility_tests():
    """运行兼容性测试"""
    cmd = "python -m pytest tests/compatibility -v"
    return run_command(cmd, "框架兼容性测试")


def run_all_tests(coverage=False):
    """运行所有测试"""
    print("\n" + "="*60)
    print("  AgentMemory 测试套件")
    print("="*60)
    
    all_passed = True
    
    # 单元测试
    if not run_unit_tests(coverage):
        all_passed = False
    
    # 集成测试
    if not run_integration_tests(coverage):
        all_passed = False
    
    # 安全测试
    if not run_security_tests(coverage):
        all_passed = False
    
    # 兼容性测试
    if not run_compatibility_tests():
        all_passed = False
    
    return all_passed


def generate_test_report():
    """生成测试报告"""
    print("\n" + "="*60)
    print("  生成测试报告")
    print("="*60)
    
    report_cmd = f'python -m pytest tests/ -v --tb=short --html="{PROJECT_ROOT}/test_report.html" --self-contained-html'
    return run_command(report_cmd, "测试报告生成")


def check_dependencies():
    """检查测试依赖"""
    print("\n检查测试依赖...")
    
    required = ["pytest", "pytest-asyncio"]
    missing = []
    
    for package in required:
        result = subprocess.run(
            f"python -c 'import {package.replace('-', '_')}'",
            shell=True,
            capture_output=True
        )
        if result.returncode != 0:
            missing.append(package)
    
    if missing:
        print(f"缺少依赖: {', '.join(missing)}")
        print("安装命令: pip install " + " ".join(missing))
        return False
    
    print("所有依赖已安装")
    return True


def main():
    parser = argparse.ArgumentParser(description="AgentMemory 测试运行器")
    parser.add_argument(
        "test_type",
        nargs="?",
        choices=["unit", "integration", "security", "performance", "compatibility", "all"],
        default="all",
        help="测试类型"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="生成覆盖率报告"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="生成 HTML 报告"
    )
    
    args = parser.parse_args()
    
    # 检查依赖
    if not check_dependencies():
        return 1
    
    # 运行测试
    success = False
    
    if args.test_type == "unit":
        success = run_unit_tests(args.coverage)
    elif args.test_type == "integration":
        success = run_integration_tests(args.coverage)
    elif args.test_type == "security":
        success = run_security_tests(args.coverage)
    elif args.test_type == "performance":
        success = run_performance_tests()
    elif args.test_type == "compatibility":
        success = run_compatibility_tests()
    else:
        success = run_all_tests(args.coverage)
    
    # 生成报告
    if args.report:
        generate_test_report()
    
    print("\n" + "="*60)
    if success:
        print("  ✅ 所有测试通过!")
    else:
        print("  ❌ 部分测试失败")
    print("="*60)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
