from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

try:
    from .manual_intent import MANUAL_STAGE_ORDER, ManualIntent, normalize_stage_name
except ImportError:  # pragma: no cover - supports direct script execution
    from manual_intent import MANUAL_STAGE_ORDER, ManualIntent, normalize_stage_name


@dataclass
class WorkflowPlan:
    workflow: Literal["rtl_manual_generation"]
    project_root: str
    rtl_inputs: str
    top_module: str
    audience: str
    evidence_mode: str
    start_stage: str
    stages: list[str]
    force_stages: list[str]
    artifact_policy: Literal[
        "reuse_valid",
        "overwrite_forced",
        "clean_before_run",
    ]
    auto_run: bool
    semantic_enrichment: bool = True
    enrich_modules: str = ""
    manual_generation_mode: str = "deterministic"
    llm_module_page_scope: str = "top_and_direct"
    llm_module_page_limit: int = 20
    llm_module_page_allowlist: str = ""
    confirmation_required: bool = False
    confirmation_message: str = ""


VALID_AUDIENCES = {"newcomer", "maintainer", "reviewer"}
VALID_EVIDENCE_MODES = {"project", "reading_path"}
VALID_MANUAL_GENERATION_MODES = {
    "deterministic",
    "llm_polish",
    "llm_section_generate",
    "llm_section_generate_with_page_polish",
}
VALID_LLM_MODULE_PAGE_SCOPES = {"none", "top_only", "top_and_direct", "all", "allowlist"}
TOP_MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def build_manual_plan(
    intent: ManualIntent,
    previous_state: dict | None = None,
    base_dir: str | Path = ".",
) -> WorkflowPlan:
    project_root = _value(intent.project_root, previous_state, "project_root", ".")
    rtl_inputs = _value(intent.rtl_inputs, previous_state, "rtl_inputs", "rtl")
    top_module = _value(intent.top_module, previous_state, "top_module", "")
    audience = _value(intent.audience, previous_state, "audience", "newcomer")
    evidence_mode = _value(intent.evidence_mode, previous_state, "evidence_mode", "project")
    auto_run = _resolve_auto_run(intent, previous_state)
    enrich_modules = intent.enrich_modules
    if not enrich_modules and previous_state:
        enrich_modules = previous_state.get("enrich_modules", "") or ""
    manual_generation_mode = _value(
        intent.manual_generation_mode,
        previous_state,
        "manual_generation_mode",
        "deterministic",
    )
    llm_module_page_scope = _value(
        intent.llm_module_page_scope,
        previous_state,
        "llm_module_page_scope",
        "top_and_direct",
    )
    llm_module_page_limit = _int_value(
        intent.llm_module_page_limit,
        previous_state,
        "llm_module_page_limit",
        20,
    )
    llm_module_page_allowlist = _value(
        intent.llm_module_page_allowlist,
        previous_state,
        "llm_module_page_allowlist",
        "",
    )

    start_stage = _resolve_start_stage(intent, previous_state)
    stages: list[str] = []
    force_stages: list[str] = []
    artifact_policy: Literal["reuse_valid", "overwrite_forced", "clean_before_run"] = "reuse_valid"

    if intent.rerun_policy == "clean_all_and_run":
        start_stage = start_stage or "references"
        stages = _stages_from(start_stage)
        force_stages = list(stages)
        artifact_policy = "clean_before_run"
    elif intent.rerun_policy == "force_from_stage":
        if not start_stage and previous_state and previous_state.get("stage") in MANUAL_STAGE_ORDER:
            start_stage = previous_state.get("stage")
        stages = _stages_from(start_stage)
        force_stages = list(stages)
        artifact_policy = "overwrite_forced"
    elif intent.rerun_policy == "manual_only":
        start_stage = "manual"
        stages = ["manual", "review"]
        force_stages = ["manual", "review"]
        artifact_policy = "overwrite_forced"
    else:
        start_stage = start_stage or _continuable_stage(previous_state) or "references"
        stages = _stages_from(start_stage)
        force_stages = []
        artifact_policy = "reuse_valid"

    confirmation_required, confirmation_message = validate_manual_intent(
        intent=intent,
        project_root=project_root,
        rtl_inputs=rtl_inputs,
        top_module=top_module,
        start_stage=start_stage,
        audience=audience,
        evidence_mode=evidence_mode,
        manual_generation_mode=manual_generation_mode,
        llm_module_page_scope=llm_module_page_scope,
        llm_module_page_limit=llm_module_page_limit,
        base_dir=base_dir,
        previous_state=previous_state,
    )
    if confirmation_required:
        return WorkflowPlan(
            workflow="rtl_manual_generation",
            project_root=project_root,
            rtl_inputs=rtl_inputs,
            top_module=top_module,
            audience=audience,
            evidence_mode=evidence_mode,
            start_stage=start_stage or "",
            stages=[],
            force_stages=[],
            artifact_policy=artifact_policy,
            auto_run=auto_run,
            semantic_enrichment=True,
            enrich_modules=enrich_modules,
            manual_generation_mode=manual_generation_mode,
            llm_module_page_scope=llm_module_page_scope,
            llm_module_page_limit=llm_module_page_limit,
            llm_module_page_allowlist=llm_module_page_allowlist,
            confirmation_required=True,
            confirmation_message=confirmation_message,
        )

    return WorkflowPlan(
        workflow="rtl_manual_generation",
        project_root=project_root,
        rtl_inputs=rtl_inputs,
        top_module=top_module,
        audience=audience,
        evidence_mode=evidence_mode,
        start_stage=start_stage or "references",
        stages=stages,
        force_stages=force_stages,
        artifact_policy=artifact_policy,
        auto_run=auto_run,
        semantic_enrichment=True,
        enrich_modules=enrich_modules,
        manual_generation_mode=manual_generation_mode,
        llm_module_page_scope=llm_module_page_scope,
        llm_module_page_limit=llm_module_page_limit,
        llm_module_page_allowlist=llm_module_page_allowlist,
    )


def validate_manual_intent(
    intent: ManualIntent,
    project_root: str,
    rtl_inputs: str,
    top_module: str,
    start_stage: str | None,
    audience: str,
    evidence_mode: str,
    manual_generation_mode: str,
    llm_module_page_scope: str,
    llm_module_page_limit: int,
    base_dir: str | Path = ".",
    previous_state: dict | None = None,
) -> tuple[bool, str]:
    messages: list[str] = []

    if intent.confirmation_required:
        messages.append(intent.confirmation_message or "需要确认 workflow 执行范围。")
    if intent.conflicts:
        messages.extend(intent.conflicts)

    if start_stage and start_stage not in MANUAL_STAGE_ORDER:
        messages.append(f"无法识别起始阶段 `{start_stage}`。")

    if intent.rerun_policy == "force_from_stage" and not start_stage:
        messages.append("强制重跑需要明确起始阶段。")

    if not str(rtl_inputs or "").strip():
        messages.append("`rtl_inputs` 不能为空。")

    if top_module and not TOP_MODULE_RE.fullmatch(top_module):
        messages.append("`top_module` 必须匹配 Verilog module name 格式：[A-Za-z_][A-Za-z0-9_$]*。")

    if audience not in VALID_AUDIENCES:
        messages.append("`audience` 必须是 newcomer、maintainer 或 reviewer。")

    if evidence_mode not in VALID_EVIDENCE_MODES:
        messages.append("`evidence_mode` 必须是 project 或 reading_path。")

    if manual_generation_mode not in VALID_MANUAL_GENERATION_MODES:
        messages.append(
            "`manual_generation_mode` 必须是 deterministic、llm_polish、"
            "llm_section_generate 或 llm_section_generate_with_page_polish。"
        )

    if llm_module_page_scope not in VALID_LLM_MODULE_PAGE_SCOPES:
        messages.append("`llm_module_page_scope` 必须是 none、top_only、top_and_direct、all 或 allowlist。")

    if llm_module_page_limit < 0:
        messages.append("`llm_module_page_limit` 不能为负数。")

    if project_root:
        resolved_root = _resolve_project_root(project_root, base_dir)
        if not resolved_root.exists():
            messages.append(f"`project_root` 路径不存在：{project_root}")
    else:
        messages.append("`project_root` 不能为空。")

    if (
        intent.rerun_policy in {"clean_all_and_run", "force_from_stage", "manual_only"}
        and not _has_destructive_scope(intent, previous_state)
    ):
        messages.append("重跑/覆盖旧产物需要明确起始阶段、全量重来或最终手册等语义。")

    if messages:
        question_text = " ".join(intent.questions)
        details = " ".join(messages)
        if question_text:
            details = f"{details} {question_text}"
        return True, details.strip()

    return False, ""


def _value(explicit_value: str | None, previous_state: dict | None, key: str, default: str) -> str:
    if explicit_value is not None:
        return explicit_value
    if previous_state and previous_state.get(key) is not None:
        return str(previous_state.get(key))
    return default


def _int_value(explicit_value: int | str | None, previous_state: dict | None, key: str, default: int) -> int:
    raw = explicit_value
    if raw is None and previous_state and previous_state.get(key) is not None:
        raw = previous_state.get(key)
    if raw is None:
        return default
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return default


def _resolve_auto_run(intent: ManualIntent, previous_state: dict | None) -> bool:
    if intent.auto_run is not None:
        return bool(intent.auto_run)
    if previous_state and previous_state.get("auto_run") is not None:
        return bool(previous_state.get("auto_run"))
    return True


def _resolve_start_stage(intent: ManualIntent, previous_state: dict | None) -> str | None:
    normalized = normalize_stage_name(intent.start_stage)
    if normalized:
        return normalized
    if intent.intent == "continue_workflow":
        return _continuable_stage(previous_state)
    return None


def _continuable_stage(previous_state: dict | None) -> str | None:
    if not previous_state or not previous_state.get("active"):
        return None
    stage = previous_state.get("stage")
    if stage not in MANUAL_STAGE_ORDER:
        return None
    if stage in set(previous_state.get("completed_stages", [])):
        return None
    return stage


def _stages_from(start_stage: str | None) -> list[str]:
    if start_stage not in MANUAL_STAGE_ORDER:
        return []
    index = MANUAL_STAGE_ORDER.index(start_stage)  # type: ignore[arg-type]
    return list(MANUAL_STAGE_ORDER[index:])


def _resolve_project_root(project_root: str, base_dir: str | Path) -> Path:
    root = Path(project_root).expanduser()
    if not root.is_absolute():
        root = Path(base_dir).expanduser() / root
    return root.resolve()


def _has_destructive_scope(intent: ManualIntent, previous_state: dict | None) -> bool:
    if intent.rerun_policy == "manual_only":
        return True
    if intent.rerun_policy == "clean_all_and_run":
        return True
    if intent.start_stage:
        return True
    return bool(previous_state and previous_state.get("active") and previous_state.get("stage") in MANUAL_STAGE_ORDER)
