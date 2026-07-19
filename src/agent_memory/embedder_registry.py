"""
Embedder Registry — 2026-07-15 方向 8

让用户能选择本地 embedding 模型,而非硬编码。

设计原则:
- 不是"切换语言",而是"挑更好的双语模型"
- 所有支持的模型都原生支持中英(单模型,无切换)
- 用户通过环境变量 / 构造函数 / CLI 选择
- 默认推荐:BAAI/bge-m3(中英双语最强,1024 维,2.2GB)

用法:
    # CLI
    python -m agent_memory.embedder_registry list
    python -m agent_memory.embedder_registry recommend

    # 代码
    from agent_memory.embedder_registry import list_models, get_recommended_model
    print(list_models())          # 所有可用模型
    print(get_recommended_model()) # 推荐模型

    # 运行时切换(需重启)
    export AGENTMEMORY_EMBED_MODEL="BAAI/bge-m3"
"""
from __future__ import annotations

import os
from typing import List, Dict, Any, Optional


def get_model_from_env() -> str:
    """从环境变量获取当前选择的模型

    优先级:
    1. AGENTMEMORY_EMBED_MODEL 环境变量
    2. fastembed_embedder.DEFAULT_RECOMMENDED_MODEL 默认推荐
    """
    return os.environ.get(
        "AGENTMEMORY_EMBED_MODEL",
        "BAAI/bge-m3",  # 默认推荐
    )


def list_models() -> List[Dict[str, Any]]:
    """列出所有可用的本地 embedding 模型

    Returns:
        [{"name": str, "dim": int, "size_mb": int, "lang": str,
          "quality": str, "recommended": bool}, ...]
    """
    from .fastembed_embedder import MODEL_INFO
    return [
        {
            "name": name,
            **info,
        }
        for name, info in MODEL_INFO.items()
    ]


def get_model_info(model_name: str) -> Optional[Dict[str, Any]]:
    """获取单个模型信息"""
    from .fastembed_embedder import MODEL_INFO
    if model_name not in MODEL_INFO:
        return None
    return {"name": model_name, **MODEL_INFO[model_name]}


def get_recommended_model() -> str:
    """获取默认推荐模型(单模型支持中英双语)"""
    from .fastembed_embedder import DEFAULT_RECOMMENDED_MODEL
    return DEFAULT_RECOMMENDED_MODEL


def create_embedder(model_name: Optional[str] = None, **kwargs):
    """创建 FastEmbedEmbedder 实例

    Args:
        model_name: 模型名称(默认从环境变量 / 推荐模型读)
        **kwargs: 透传给 FastEmbedEmbedder
    """
    from .fastembed_embedder import FastEmbedEmbedder
    name = model_name or get_model_from_env()
    return FastEmbedEmbedder(model_name=name, **kwargs)


def format_model_table() -> str:
    """人类可读的模型表(给 CLI 用)"""
    models = list_models()
    lines = ["可用本地 Embedding 模型(单模型原生支持中英):"]
    lines.append("")
    lines.append(f"{'名称':<48} {'维度':<6} {'大小':<8} {'语言':<8} {'质量'}")
    lines.append("-" * 95)
    for m in models:
        # 【Bug Fix 2026-07-15 调7】避免 emoji 触发 Windows GBK 编码错
        rec = " *推荐" if m.get("recommended") else ""
        lines.append(
            f"{m['name']:<48} {m['dim']:<6} "
            f"{m['size_mb']}MB{'':<3} {m['lang']:<8} {m['quality']}{rec}"
        )
    return "\n".join(lines)


def main() -> int:
    """CLI 入口:list / recommend / info"""
    import argparse
    parser = argparse.ArgumentParser(
        prog="agent_memory.embedder_registry",
        description="列出 / 选择本地 embedding 模型",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出所有可用模型")
    sub.add_parser("recommend", help="显示推荐模型")
    p_info = sub.add_parser("info", help="显示单个模型信息")
    p_info.add_argument("model_name")

    args = parser.parse_args()
    if args.cmd == "list":
        print(format_model_table())
    elif args.cmd == "recommend":
        rec = get_recommended_model()
        info = get_model_info(rec)
        print(f"推荐模型: {rec}")
        print(f"  维度: {info['dim']}")
        print(f"  大小: {info['size_mb']} MB")
        print(f"  语言: {info['lang']}")
        print(f"  质量: {info['quality']}")
        print(f"\n  设置环境变量: AGENTMEMORY_EMBED_MODEL=\"{rec}\"")
    elif args.cmd == "info":
        info = get_model_info(args.model_name)
        if not info:
            print(f"未知模型: {args.model_name}")
            print(f"可用: {[m['name'] for m in list_models()]}")
            return 1
        for k, v in info.items():
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())