"""
该包保持面向代理的适配器精简，同时将生成的手册制品分离到 
基础层 、 增强片段层 和 组合最终层
"""

from .workflow import (
    build_base_manual,
    compose_final_manual,
    enhance_main_manual,
    enhance_module_page,
    run_source_review,
)

__all__ = [
    "build_base_manual",
    "compose_final_manual",
    "enhance_main_manual",
    "enhance_module_page",
    "run_source_review",
]

