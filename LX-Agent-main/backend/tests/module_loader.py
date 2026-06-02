from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = ROOT / "backend" / "skills" / "catalog" / "rtl-manual-generation" / "packages" / "knowledge"
SCRIPT_DIR = ROOT / "backend" / "skills" / "catalog" / "rtl-manual-generation" / "scripts"


def load_module(module_name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_llm_client() -> ModuleType:
    return load_module("knowledge_llm_client_under_test", KNOWLEDGE_DIR / "llm_client.py")


def load_semantic_layer() -> ModuleType:
    return load_module("knowledge_semantic_layer_under_test", KNOWLEDGE_DIR / "semantic_layer.py")


def load_run_knowledge_tool() -> ModuleType:
    return load_module("run_knowledge_tool_under_test", SCRIPT_DIR / "run_knowledge_tool.py")
