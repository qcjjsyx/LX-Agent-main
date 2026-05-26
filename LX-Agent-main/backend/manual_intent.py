from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


Stage = Literal[
    "references",
    "parser",
    "knowledge",
    "evidence",
    "source_review",
    "outline",
    "chapter_plan",
    "manual",
    "review",
]

MANUAL_STAGE_ORDER: tuple[Stage, ...] = (
    "references",
    "parser",
    "knowledge",
    "evidence",
    "source_review",
    "outline",
    "chapter_plan",
    "manual",
    "review",
)

MANUAL_INTENTS = (
    "generate_manual",
    "continue_workflow",
    "rerun_workflow",
    "inspect_status",
    "cancel_workflow",
    "unknown",
)


@dataclass
class ManualIntent:
    intent: Literal[
        "generate_manual",
        "continue_workflow",
        "rerun_workflow",
        "inspect_status",
        "cancel_workflow",
        "unknown",
    ]
    project_root: str | None = None
    rtl_inputs: str | None = None
    top_module: str | None = None
    audience: str | None = None
    evidence_mode: str | None = None
    start_stage: str | None = None
    manual_generation_mode: str | None = None
    llm_module_page_scope: str | None = None
    llm_module_page_limit: int | None = None
    llm_module_page_allowlist: str | None = None
    rerun_policy: Literal[
        "reuse_valid_artifacts",
        "force_from_stage",
        "clean_all_and_run",
        "manual_only",
    ] = "reuse_valid_artifacts"
    auto_run: bool | None = None
    semantic_enrichment: bool = True
    enrich_modules: str = ""
    confidence: float = 1.0
    conflicts: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    confirmation_required: bool = False
    confirmation_message: str = ""


CONTINUE_WORDS = (
    "继续",
    "下一步",
    "确认",
    "好的",
    "ok",
    "yes",
    "go on",
)

AUTO_RUN_WORDS = (
    "自动",
    "一次性",
    "直接完成",
    "跑完整",
    "完整跑完",
    "自动跑完",
    "auto",
    "automatically",
)

STEP_BY_STEP_WORDS = (
    "分阶段",
    "一步步",
    "单步",
    "逐步",
    "不要自动",
    "先不要继续",
)

MANUAL_REQUEST_WORDS = (
    "生成代码手册",
    "生成手册",
    "代码手册",
    "项目手册",
    "模块手册",
    "手册生成",
    "文档生成",
    "rtl manual",
    "manual generation",
)

RERUN_WORDS = (
    "重新生成",
    "重新执行",
    "重新跑",
    "重跑",
    "强制生成",
    "强制执行",
    "强制重跑",
    "覆盖生成",
    "regenerate",
    "rerun",
    "restart",
    "force",
    "rebuild",
)

CLEAN_ALL_WORDS = (
    "从头",
    "全量",
    "全量重来",
    "全量重跑",
    "清空后",
    "清空结果",
    "清空产物",
    "clean all",
    "clean run",
    "fresh run",
    "from scratch",
)

NO_REUSE_WORDS = (
    "不要复用",
    "不复用",
    "别复用",
    "不要使用旧结果",
    "不要用旧结果",
    "不要用旧产物",
    "no reuse",
    "without reuse",
)

CANCEL_WORDS = ("取消", "cancel", "stop workflow")
STATUS_WORDS = ("状态", "进度", "status", "progress")

STAGE_ALIASES: dict[Stage, tuple[str, ...]] = {
    "references": ("references", "reference", "refs", "参考"),
    "parser": ("parser", "parse", "解析"),
    "knowledge": ("knowledge_ir", "knowledge ir", "knowledge", "manual_context", "manual context", "知识"),
    "evidence": ("evidence", "证据"),
    "source_review": ("source_review", "source review", "source-review", "源码复核", "源代码复核"),
    "outline": ("outline", "toc", "目录", "大纲"),
    "chapter_plan": ("chapter_plan", "chapter plan", "chapter-plan", "章节规划"),
    "manual": ("manual", "markdown 正文", "markdown", "正文"),
    "review": ("review", "checker", "审查", "检查"),
}

_ALIAS_TO_STAGE = {
    alias.lower(): stage
    for stage, aliases in STAGE_ALIASES.items()
    for alias in aliases
}

_SORTED_ALIASES = sorted(_ALIAS_TO_STAGE, key=len, reverse=True)


def parse_manual_intent(user_input: str, state: dict | None = None) -> ManualIntent:
    text = user_input or ""
    lower_text = text.lower()
    params = _extract_explicit_params(text)
    if state and not state.get("top_module") and "top_module" not in params:
        bare_top_module = _extract_bare_module_name(text)
        if bare_top_module:
            params["top_module"] = bare_top_module
    _apply_evidence_mode_text(params, text)
    if "project_root" not in params:
        path_text = _extract_first_path(text)
        if path_text:
            inferred_project_root, inferred_rtl_inputs = _infer_project_paths(path_text)
            params["project_root"] = inferred_project_root
            if "rtl_inputs" not in params:
                params["rtl_inputs"] = inferred_rtl_inputs
    explicit_stage = _extract_explicit_stage(text)
    stage_from_expression = _extract_stage_expression(text)

    start_stage = explicit_stage or stage_from_expression
    continue_requested = _is_continue_request(text)
    rerun_requested = _has_any(text, RERUN_WORDS) or bool(start_stage) or _has_any(text, CLEAN_ALL_WORDS) or _has_any(text, NO_REUSE_WORDS)
    clean_all_requested = _has_any(text, CLEAN_ALL_WORDS)
    no_reuse_requested = _has_any(text, NO_REUSE_WORDS)
    manual_only_requested = _is_manual_only_request(text)

    if _is_cancel_request(text):
        intent_name = "cancel_workflow"
    elif _is_status_request(text):
        intent_name = "inspect_status"
    elif rerun_requested or manual_only_requested:
        intent_name = "rerun_workflow"
    elif continue_requested:
        intent_name = "continue_workflow"
    elif _is_generate_request(text) or params:
        intent_name = "generate_manual"
    else:
        intent_name = "unknown"

    rerun_policy = "reuse_valid_artifacts"
    if manual_only_requested:
        rerun_policy = "manual_only"
        start_stage = "manual"
    elif clean_all_requested:
        rerun_policy = "clean_all_and_run"
        start_stage = start_stage or "references"
    elif start_stage and rerun_requested:
        rerun_policy = "force_from_stage"
    elif no_reuse_requested:
        rerun_policy = "force_from_stage"

    if not start_stage and intent_name == "continue_workflow" and state:
        state_stage = state.get("stage")
        if state.get("active") and state_stage in MANUAL_STAGE_ORDER:
            start_stage = state_stage

    intent = ManualIntent(
        intent=intent_name,  # type: ignore[arg-type]
        project_root=params.get("project_root"),
        rtl_inputs=params.get("rtl_inputs"),
        top_module=params.get("top_module"),
        audience=params.get("audience"),
        evidence_mode=params.get("evidence_mode"),
        start_stage=start_stage,
        manual_generation_mode=params.get("manual_generation_mode"),
        llm_module_page_scope=params.get("llm_module_page_scope"),
        llm_module_page_limit=params.get("llm_module_page_limit"),
        llm_module_page_allowlist=params.get("llm_module_page_allowlist"),
        rerun_policy=rerun_policy,  # type: ignore[arg-type]
        auto_run=_extract_auto_run(text),
        semantic_enrichment=True,
        enrich_modules=params.get("enrich_modules", ""),
    )

    if continue_requested and rerun_policy != "reuse_valid_artifacts" and _starts_with_continue(lower_text):
        intent.conflicts.append("用户同时要求继续当前流程和重跑/全量重来。")

    if no_reuse_requested and not start_stage and not _can_infer_start_stage(state):
        intent.confirmation_required = True
        intent.questions.append("你想从哪个阶段开始强制重跑？可选 references/parser/knowledge/evidence/source_review/outline/chapter_plan/manual/review。")

    if intent.conflicts:
        intent.confirmation_required = True
        intent.questions.append("请确认是继续当前阶段，还是从某个阶段开始全量/强制重跑。")

    if intent.confirmation_required and not intent.confirmation_message:
        intent.confirmation_message = "我无法确定这次请求的 workflow 执行范围，需要你确认后再执行。"

    return intent


def normalize_stage_name(value: str | None) -> str | None:
    raw = (value or "").strip().strip("`'\"")
    if not raw:
        return None
    lowered = raw.lower().replace("-", "_")
    if lowered in MANUAL_STAGE_ORDER:
        return lowered
    alias_key = lowered.replace("_", " ")
    if alias_key in _ALIAS_TO_STAGE:
        return _ALIAS_TO_STAGE[alias_key]
    if lowered in _ALIAS_TO_STAGE:
        return _ALIAS_TO_STAGE[lowered]
    return None


def _extract_explicit_params(text: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for key, patterns in {
        "project_root": (
            r"project_root\s*(?:=|:|：|是|为)\s*([^\s，,。；;]+)",
            r"项目根目录\s*(?:=|:|：|是|为)\s*([^\s，,。；;]+)",
        ),
        "rtl_inputs": (
            r"rtl_inputs\s*(?:=|:|：|是|为)\s*([^\s，,。；;]+)",
            r"RTL\s*输入目录\s*(?:=|:|：|是|为)\s*([^\s，,。；;]+)",
        ),
        "top_module": (
            r"top_module\s*(?:=|:|：|是|为)\s*`?([A-Za-z_][A-Za-z0-9_$]*)`?",
            r"top module\s*(?:=|:|：|是|为)\s*`?([A-Za-z_][A-Za-z0-9_$]*)`?",
            r"顶层模块(?:名)?\s*(?:=|:|：|是|为)\s*`?([A-Za-z_][A-Za-z0-9_$]*)`?",
        ),
        "audience": (
            r"audience\s*(?:=|:|：|是|为)\s*(newcomer|maintainer|reviewer)",
            r"阅读对象\s*(?:=|:|：|是|为)\s*(newcomer|maintainer|reviewer|新读者|维护者|审查者)",
        ),
        "evidence_mode": (
            r"evidence_mode\s*(?:=|:|：|是|为)\s*([A-Za-z_\-一-龥]+)",
            r"证据模式\s*(?:=|:|：|是|为)\s*([A-Za-z_\-一-龥]+)",
        ),
        "enrich_modules": (
            r"enrich_modules\s*(?:=|:|：|是|为)\s*([A-Za-z0-9_,$\-\s，]+)",
            r"增强模块\s*(?:=|:|：|是|为)\s*([A-Za-z0-9_,$\-\s，]+)",
            r"语义模块\s*(?:=|:|：|是|为)\s*([A-Za-z0-9_,$\-\s，]+)",
        ),
        "manual_generation_mode": (
            r"manual_generation_mode\s*(?:=|:|：|是|为)\s*(llm_section_generate_with_page_polish|llm_section_generate|llm_polish|deterministic)",
            r"manual_mode\s*(?:=|:|：|是|为)\s*(llm_section_generate_with_page_polish|llm_section_generate|llm_polish|deterministic)",
            r"手册生成模式\s*(?:=|:|：|是|为)\s*(llm_section_generate_with_page_polish|llm_section_generate|llm_polish|deterministic)",
            r"手册模式\s*(?:=|:|：|是|为)\s*(llm_section_generate_with_page_polish|llm_section_generate|llm_polish|deterministic)",
        ),
        "llm_module_page_scope": (
            r"llm_module_page_scope\s*(?:=|:|：|是|为)\s*(top_and_direct|top_only|allowlist|none|all)",
            r"模块页范围\s*(?:=|:|：|是|为)\s*(top_and_direct|top_only|allowlist|none|all)",
        ),
        "llm_module_page_limit": (
            r"llm_module_page_limit\s*(?:=|:|：|是|为)\s*(\d+)",
        ),
        "llm_module_page_allowlist": (
            r"llm_module_page_allowlist\s*(?:=|:|：|是|为)\s*([A-Za-z0-9_,$\-\s，]+)",
            r"模块页白名单\s*(?:=|:|：|是|为)\s*([A-Za-z0-9_,$\-\s，]+)",
        ),
    }.items():
        value = _match_value(text, patterns)
        if value:
            params[key] = _clean_param_value(key, value)

    if params.get("audience") in {"新读者", "维护者", "审查者"}:
        params["audience"] = {
            "新读者": "newcomer",
            "维护者": "maintainer",
            "审查者": "reviewer",
        }[params["audience"]]

    if "evidence_mode" in params:
        params["evidence_mode"] = _normalize_evidence_mode(params["evidence_mode"])

    if params.get("enrich_modules"):
        modules = [
            item.strip()
            for item in re.split(r"[,，\s]+", params["enrich_modules"])
            if item.strip()
        ]
        params["enrich_modules"] = ",".join(modules)
    if params.get("llm_module_page_allowlist"):
        modules = [
            item.strip()
            for item in re.split(r"[,，\s]+", params["llm_module_page_allowlist"])
            if item.strip()
        ]
        params["llm_module_page_allowlist"] = ",".join(modules)
    if params.get("llm_module_page_limit"):
        try:
            params["llm_module_page_limit"] = max(0, int(params["llm_module_page_limit"]))
        except ValueError:
            params.pop("llm_module_page_limit", None)

    mode = params.get("manual_generation_mode") or _extract_manual_generation_mode_text(text)
    if mode:
        params["manual_generation_mode"] = mode

    return params


def _extract_explicit_stage(text: str) -> str | None:
    value = _match_value(
        text,
        (
            r"(?:start_stage|from_stage|restart_stage|stage)\s*(?:=|:|：|是|为)\s*([A-Za-z_ -]+)",
            r"(?:起始阶段|重跑阶段)\s*(?:=|:|：|是|为)\s*([A-Za-z_ \-一-龥]+)",
        ),
    )
    return normalize_stage_name(value) or _normalize_stage_prefix(value)


def _extract_stage_expression(text: str) -> str | None:
    mentions = _find_stage_mentions(text)
    if not mentions:
        return None

    candidates: list[tuple[int, int, str]] = []
    lowered = text.lower()
    rerun_positions = _word_positions(lowered, RERUN_WORDS + ("start from", "from", "自", "从"))

    for start, end, stage in mentions:
        prefix = lowered[max(0, start - 32):start]
        suffix = lowered[end:min(len(lowered), end + 64)]
        if _stage_context_is_explicit(prefix, suffix):
            distance = min((abs(start - pos) for pos in rerun_positions), default=0)
            candidates.append((distance, start, stage))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _find_stage_mentions(text: str) -> list[tuple[int, int, str]]:
    lowered = text.lower()
    matches: list[tuple[int, int, str, int]] = []
    for alias in _SORTED_ALIASES:
        pattern = re.escape(alias).replace(r"\ ", r"[\s_-]+")
        if _alias_is_latin(alias):
            pattern = rf"(?<![A-Za-z0-9_$]){pattern}(?![A-Za-z0-9_$])"
        for match in re.finditer(pattern, lowered, flags=re.IGNORECASE):
            matches.append((match.start(), match.end(), _ALIAS_TO_STAGE[alias], len(match.group(0))))

    matches.sort(key=lambda item: (-item[3], item[0]))
    accepted: list[tuple[int, int, str, int]] = []
    for candidate in matches:
        start, end, _stage, _length = candidate
        if any(not (end <= old_start or start >= old_end) for old_start, old_end, _old_stage, _old_length in accepted):
            continue
        accepted.append(candidate)

    accepted.sort(key=lambda item: item[0])
    return [(start, end, stage) for start, end, stage, _length in accepted]


def _normalize_stage_prefix(value: str | None) -> str | None:
    lowered = (value or "").strip().strip("`'\"").lower()
    if not lowered:
        return None
    for alias in _SORTED_ALIASES:
        pattern = re.escape(alias).replace(r"\ ", r"[\s_-]+")
        if _alias_is_latin(alias):
            pattern = rf"^{pattern}(?![A-Za-z0-9_$])"
        else:
            pattern = rf"^{pattern}"
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            return _ALIAS_TO_STAGE[alias]
    return None


def _stage_context_is_explicit(prefix: str, suffix: str) -> bool:
    return (
        bool(re.search(r"(?:从|自)\s*$", prefix))
        or bool(re.search(r"(?:start\s+from|rerun\s+from|restart\s+(?:at|from)|from)\s*$", prefix))
        or bool(re.search(r"(?:重新做|重做|重新执行|重跑)\s*$", prefix))
        or bool(re.search(r"^\s*(?:阶段)?\s*(?:开始|起|重跑|重新跑|重新执行|重新生成|之后|后面|后续|及后续|rerun|restart)", suffix))
    )


def _is_manual_only_request(text: str) -> bool:
    lower_text = text.lower()
    has_generation_or_rerun = _has_any(text, RERUN_WORDS) or "生成" in text
    explicit_final_manual = any(phrase in text for phrase in ("最终手册", "最终正文", "Markdown 正文", "markdown 正文"))
    explicit_only_manual = (
        bool(re.search(r"(?:只|仅)\s*(?:重新生成|重跑|生成)?\s*(?:manual|markdown|正文)(?:\s*阶段)?", lower_text))
        or bool(re.search(r"(?:只|仅).*(?:最终手册|Markdown 正文|markdown 正文|正文)", text))
    )
    return explicit_only_manual or (explicit_final_manual and has_generation_or_rerun)


def _extract_auto_run(text: str) -> bool | None:
    if _has_any(text, STEP_BY_STEP_WORDS):
        return False
    if _has_any(text, AUTO_RUN_WORDS):
        return True
    return None


def _extract_manual_generation_mode_text(text: str) -> str:
    raw_text = text or ""
    lower_text = raw_text.lower()
    compact_text = re.sub(r"[\s_-]+", "_", lower_text)
    deterministic_patterns = (
        "不用 llm",
        "不用LLM",
        "不要 llm",
        "不要LLM",
        "不要让 llm",
        "不要让LLM",
        "不用模型润色",
        "不要模型润色",
        "确定性",
        "模板生成",
        "deterministic",
    )
    if any(pattern.lower() in lower_text for pattern in deterministic_patterns):
        return "deterministic"

    if "llm_section_generate_with_page_polish" in compact_text:
        return "llm_section_generate_with_page_polish"
    if "llm_section_generate" in compact_text:
        return "llm_section_generate"
    if "llm_polish" in compact_text:
        return "llm_polish"

    if (
        re.search(r"(?:llm|模型).*(?:章节|按章节).*(?:模块页).*(?:润色|polish)", raw_text, flags=re.IGNORECASE)
        or re.search(r"(?:模块页).*(?:也)?.*(?:llm|模型).*(?:润色|polish)", raw_text, flags=re.IGNORECASE)
        or re.search(r"(?:llm|模型).*(?:生成章节|章节内容).*(?:润色模块页)", raw_text, flags=re.IGNORECASE)
    ):
        return "llm_section_generate_with_page_polish"

    section_patterns = (
        r"用\s*(?:llm|模型)\s*(?:按章节)?生成主手册",
        r"(?:llm|模型)\s*按章节\s*生成(?:主手册)?",
        r"章节内容\s*用\s*(?:llm|模型)\s*生成",
        r"(?:llm|模型)\s*生成章节内容",
    )
    for pattern in section_patterns:
        if re.search(pattern, raw_text, flags=re.IGNORECASE):
            return "llm_section_generate"

    polish_patterns = (
        r"(?:llm|模型)\s*润色",
        r"润色\s*(?:主手册|最终手册)",
        r"用\s*(?:llm|模型)\s*润色手册",
        r"让\s*模型\s*润色(?:最终)?手册",
        r"llm\s*polish",
    )
    for pattern in polish_patterns:
        if re.search(pattern, raw_text, flags=re.IGNORECASE):
            return "llm_polish"
    return ""


def _is_continue_request(text: str) -> bool:
    lower_text = text.lower()
    return any(word.lower() in lower_text for word in CONTINUE_WORDS)


def _is_generate_request(text: str) -> bool:
    lower_text = text.lower()
    return any(word.lower() in lower_text for word in MANUAL_REQUEST_WORDS)


def _is_cancel_request(text: str) -> bool:
    lower_text = text.lower()
    return any(word.lower() in lower_text for word in CANCEL_WORDS)


def _is_status_request(text: str) -> bool:
    lower_text = text.lower()
    return any(word.lower() in lower_text for word in STATUS_WORDS)


def _starts_with_continue(lower_text: str) -> bool:
    stripped = lower_text.strip()
    return any(stripped.startswith(word.lower()) for word in CONTINUE_WORDS)


def _can_infer_start_stage(state: dict | None) -> bool:
    return bool(state and state.get("active") and state.get("stage") in MANUAL_STAGE_ORDER)


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    lower_text = text.lower()
    return any(word.lower() in lower_text for word in words)


def _word_positions(lower_text: str, words: tuple[str, ...]) -> list[int]:
    positions: list[int] = []
    for word in words:
        start = lower_text.find(word.lower())
        while start >= 0:
            positions.append(start)
            start = lower_text.find(word.lower(), start + len(word))
    return positions


def _alias_is_latin(alias: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9_ -]+", alias))


def _match_value(text: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text or "", flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _clean_param_value(key: str, value: str) -> str:
    value = (value or "").strip().strip("`'\"")
    if key not in {"enrich_modules", "llm_module_page_allowlist"}:
        for splitter in ("并", "，", ",", "。", "；", ";"):
            value = value.split(splitter)[0]
    return value.strip().strip("`'\"")


def _clean_path(value: str) -> str:
    return _clean_param_value("project_root", value)


def _normalize_evidence_mode(value: str) -> str:
    lower_value = (value or "").lower()
    if lower_value in {"reading_path", "reading-path", "reading guide"} or value in {"新读者", "入门指南", "新人指南"}:
        return "reading_path"
    return "project"


def _apply_evidence_mode_text(params: dict[str, str], text: str) -> None:
    lower_text = (text or "").lower()
    if any(word in lower_text for word in ("project", "full", "complete")):
        params.setdefault("evidence_mode", "project")
    if any(word in (text or "") for word in ("完整项目", "整个项目", "项目代码手册", "完整代码手册", "全项目")):
        params.setdefault("evidence_mode", "project")

    if any(word in lower_text for word in ("reading_path", "reading guide")):
        params["evidence_mode"] = "reading_path"

    if any(word in (text or "") for word in ("新读者", "入门指南", "新人指南")):
        params["evidence_mode"] = "reading_path"
        params["audience"] = "newcomer"
    if any(word in (text or "") for word in ("维护者", "维护指南")):
        params["evidence_mode"] = "reading_path"
        params["audience"] = "maintainer"
    if any(word in (text or "") for word in ("审查者", "审查指南", "审核指南")):
        params["evidence_mode"] = "reading_path"
        params["audience"] = "reviewer"


def _extract_bare_module_name(text: str) -> str:
    value = (text or "").strip().strip("`'\"")
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", value):
        if value.lower() not in {"ok", "yes", "go", "continue"}:
            return value
    return ""


def _extract_first_path(text: str) -> str:
    match = re.search(r"[A-Za-z]:[\\/][^\n\r\t，,。；;]+", text or "")
    if not match:
        return ""
    return _clean_path(match.group(0))


def _infer_project_paths(path_text: str) -> tuple[str, str]:
    candidate = Path(path_text)

    if candidate.name.lower() == "rtl":
        return str(candidate.parent), candidate.name

    if candidate.exists() and candidate.is_dir():
        rtl_child = candidate / "rtl"
        if _looks_like_rtl_input_dir(rtl_child):
            return str(candidate), "rtl"
        if _looks_like_rtl_input_dir(candidate):
            return str(candidate.parent), candidate.name

    return str(candidate), "rtl"


def _looks_like_rtl_input_dir(path: Path) -> bool:
    return (
        path.exists()
        and path.is_dir()
        and (
            (path / "read_rtl_list.tcl").exists()
            or (path / "rtl_top_list.tcl").exists()
            or any(path.rglob("*.v"))
            or any(path.rglob("*.sv"))
        )
    )
