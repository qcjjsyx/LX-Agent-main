from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    triggers: tuple[str, ...] = field(default_factory=tuple)
    tool_names: tuple[str, ...] = field(default_factory=tuple)
    instruction: str = ""
    reference_files: tuple[str, ...] = field(default_factory=tuple)
    priority: int = 100
    skill_type: str = "agentic"
    workflow_id: str = ""
    actions: tuple[str, ...] = field(default_factory=tuple)

    def matches(self, user_input: str) -> bool:
        return self.match_score(user_input) > 0

    def match_score(self, user_input: str) -> int:
        text = (user_input or "").lower()
        if not text:
            return 0

        if self.name == "rtl-manual-generation":
            return self._rtl_manual_score(text)

        score = self._trigger_score(text)

        if self.name == "python-code-analysis" and any(
            ext in text for ext in (".py", ".pyw", ".ipynb")
        ):
            score += 8

        return score

    def matched_triggers(self, user_input: str) -> tuple[str, ...]:
        text = (user_input or "").lower()
        return tuple(
            trigger for trigger in self.triggers
            if trigger and trigger.lower() in text
        )

    def _trigger_score(self, text: str) -> int:
        return len([
            trigger for trigger in self.triggers
            if trigger and trigger.lower() in text
        ]) * 10

    def _rtl_manual_score(self, text: str) -> int:
        strong_triggers = {
            "manual",
            "manual_ir",
            "manual_context",
            "contextpack",
            "parser",
            "knowledge",
            "knowledge_ir",
            "semantic_layer",
            "docs",
            "readme",
        }
        score = 0

        for trigger in self.triggers:
            if not trigger:
                continue
            normalized = trigger.lower()
            if normalized not in text:
                continue
            score += 2 if normalized == "rtl" else 10

        if any(token in text for token in strong_triggers):
            score += 8
        if "top_module" in text or "top module" in text:
            score += 6

        return score if score >= 8 else 0


def split_skill_markdown(content: str):
    if not content.startswith("---"):
        return {}, content.strip()

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content.strip()

    metadata = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")

    return metadata, parts[2].strip()


def load_skill_from_directory(skill_dir: Path):
    skill_path = skill_dir / "SKILL.md"
    metadata_path = skill_dir / "skill.json"

    if not skill_path.exists() or not metadata_path.exists():
        return None

    frontmatter, body = split_skill_markdown(
        skill_path.read_text(encoding="utf-8")
    )
    runtime_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    return SkillSpec(
        name=frontmatter["name"],
        description=frontmatter["description"],
        triggers=tuple(runtime_metadata.get("triggers", [])),
        tool_names=tuple(runtime_metadata.get("tool_names", [])),
        instruction=body,
        reference_files=tuple(runtime_metadata.get("reference_files", [])),
        priority=int(runtime_metadata.get("priority", 100)),
        skill_type=runtime_metadata.get("type", "agentic"),
        workflow_id=runtime_metadata.get("workflow_id", ""),
        actions=tuple(runtime_metadata.get("actions", [])),
    )


def unique_names(names):
    result = []
    seen = set()

    for name in names:
        if name not in seen:
            result.append(name)
            seen.add(name)

    return result
