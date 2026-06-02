from __future__ import annotations

from backend import manual_workflow


class _FakeMessage:
    content = "# arm_soc_top\n\n[CPU2NoC](arm_soc_top_generated_modules/CPU2NoC.md)\n\nAI 推断\n\n证据不足\n"


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]


class _FakeCompletions:
    def __init__(self):
        self.messages = None

    def create(self, *, model, messages):
        self.messages = messages
        return _FakeResponse()


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self):
        self.chat = _FakeChat()


def test_source_review_collects_all_flagged_modules_without_twenty_module_cap():
    digest = {
        "top_module": "top",
        "project_context": {"top_level": {"direct_modules": {"value": []}}},
        "modules": [
            {
                "module_name": f"mod_{index:02d}",
                "page_policy": {"detail_level": "compact"},
                "evidence_gaps": [{"reason": f"review mod_{index:02d}"}],
                "source_files": [f"rtl/mod_{index:02d}.v"],
            }
            for index in range(25)
        ],
    }

    targets = manual_workflow._collect_source_review_targets(digest)

    assert len(targets) == 25
    assert targets[0]["module"] == "mod_00"
    assert targets[-1]["module"] == "mod_24"


def test_source_review_ignores_plain_review_questions_without_explicit_flags():
    digest = {
        "top_module": "top",
        "project_context": {"top_level": {"direct_modules": {"value": []}}},
        "modules": [
            {
                "module_name": "plain_question_only",
                "review_questions": [{"question": "human can inspect this later"}],
                "source_files": ["rtl/plain_question_only.v"],
            },
            {
                "module_name": "flagged_module",
                "responsibility": {
                    "short_summary": {
                        "value": "Needs RTL review.",
                        "review_status": "needs_review",
                    }
                },
                "source_files": ["rtl/flagged_module.v"],
            },
        ],
    }

    targets = manual_workflow._collect_source_review_targets(digest)

    assert [target["module"] for target in targets] == ["flagged_module"]


def test_main_manual_polish_receives_manual_context_packet():
    draft = "# arm_soc_top\n\n[CPU2NoC](arm_soc_top_generated_modules/CPU2NoC.md)\n\nAI 推断\n\n证据不足\n"
    packet = {
        "top_module": "arm_soc_top",
        "manual_context_available": True,
        "source_review": {"reviewed_modules": 1, "claim_count": 2},
    }
    client = _FakeClient()

    polished = manual_workflow._polish_manual_with_llm(
        {"top_module": "arm_soc_top", "manual_llm_required": True},
        draft,
        client,
        "test-model",
        packet,
    )

    assert polished == draft.strip()
    user_prompt = client.chat.completions.messages[1]["content"]
    assert "Manual Context 摘要" in user_prompt
    assert '"reviewed_modules": 1' in user_prompt
