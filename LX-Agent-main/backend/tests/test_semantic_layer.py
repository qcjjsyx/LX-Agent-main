import importlib.util
import sys
import tempfile
import threading
import unittest
from pathlib import Path


SEMANTIC_LAYER_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "catalog"
    / "rtl-manual-generation"
    / "packages"
    / "knowledge"
    / "semantic_layer.py"
)


def load_semantic_layer():
    module_dir = str(SEMANTIC_LAYER_PATH.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location("semantic_layer_under_test", SEMANTIC_LAYER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE_RESPONSE = """[MODULE_ROLE]
summary: 模块语义说明
evidence: ai_context/modules/{module}.json@compact_context
confidence: high
"""


FLOW_RESPONSE = """[FLOW_INTENT]
summary: flow 语义说明
evidence: ai_context/modules/{module}/flows/{flow}.json@compact_context.flow
confidence: high
"""


class FakeLLMClient:
    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def complete_text(self, messages):
        user_prompt = messages[-1]["content"]
        with self.lock:
            self.calls.append(user_prompt)
        if "flow f1" in user_prompt:
            return FLOW_RESPONSE.format(module="m1", flow="f1")
        if "module m2" in user_prompt:
            return MODULE_RESPONSE.format(module="m2")
        return MODULE_RESPONSE.format(module="m1")


class FailingLLMClient:
    def complete_text(self, messages):
        raise AssertionError("cached semantic card should have been reused")


class SemanticLayerTest(unittest.TestCase):
    def setUp(self):
        self.semantic = load_semantic_layer()

    def make_knowledge_root(self, tmpdir, *, modules=("m1",), include_flow=False):
        root = Path(tmpdir) / "knowledge_ir" / "top"
        self.semantic.write_json(root / "manifest.json", {
            "schema": "knowledge_ir_manifest",
            "top_module": "top",
            "files": {},
            "counts": {},
        })
        module_files = {}
        flow_files = {}
        for module_name in modules:
            module_rel = f"ai_context/modules/{module_name}.json"
            module_files[module_name] = module_rel
            self.semantic.write_json(root / module_rel, {
                "top_module": "top",
                "module": module_name,
                "source": {},
                "evidence_index": [],
            })
        if include_flow:
            flow_rel = "ai_context/modules/m1/flows/f1.json"
            flow_files["m1"] = [flow_rel]
            self.semantic.write_json(root / flow_rel, {
                "top_module": "top",
                "module": "m1",
                "flow_id": "f1",
                "source": {},
                "evidence_index": [],
            })
        self.semantic.write_json(root / "ai_context" / "index.json", {
            "top_module": "top",
            "files": {
                "modules": module_files,
                "flows": flow_files,
            },
        })
        return root

    def test_reuses_cached_module_card_with_matching_input_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self.make_knowledge_root(tmpdir, modules=("m1",))
            context = self.semantic.read_json(root / "ai_context/modules/m1.json")
            card = self.semantic.parse_module_semantic_card(
                MODULE_RESPONSE.format(module="m1"),
                context,
            )
            self.semantic.write_json(root / "semantic/modules/m1.json", card)

            report = self.semantic.enrich_semantic_layer(
                root,
                include_flows=False,
                max_workers=2,
                llm_client=FailingLLMClient(),
            )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["count"]["modules"], 1)
        self.assertEqual(report["count"]["skipped_modules"], 1)
        self.assertEqual(report["count"]["claims"], 1)

    def test_generates_modules_and_flows_with_worker_setting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self.make_knowledge_root(tmpdir, modules=("m1", "m2"), include_flow=True)
            client = FakeLLMClient()

            report = self.semantic.enrich_semantic_layer(
                root,
                include_flows=True,
                max_workers=2,
                llm_client=client,
            )
            index = self.semantic.read_json(root / "semantic/index.json")

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["workers"], 2)
        self.assertEqual(report["count"]["modules"], 2)
        self.assertEqual(report["count"]["flows"], 1)
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(index["counts"]["modules"], 2)
        self.assertEqual(index["counts"]["flows"], 1)

    def test_default_worker_count_is_four(self):
        with unittest.mock.patch.dict(self.semantic.os.environ, {}, clear=True):
            self.assertEqual(self.semantic.resolve_semantic_workers(), 4)


if __name__ == "__main__":
    unittest.main()
