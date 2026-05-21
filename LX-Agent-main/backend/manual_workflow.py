import json
import re
from pathlib import Path

try:
    from .tools import run_knowledge_tool, run_parser_tool
except ImportError:
    from tools import run_knowledge_tool, run_parser_tool


MANUAL_SKILL_NAME = "rtl-manual-generation"
MANUAL_STAGE_ORDER = (
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
RESTART_WORDS = (
    "重新生成",
    "重新执行",
    "重新跑",
    "重跑",
    "强制生成",
    "强制执行",
    "覆盖生成",
    "regenerate",
    "rerun",
    "restart",
    "force",
    "rebuild",
)
RESTART_STAGE_ALIASES = {
    "references": ("references", "reference", "refs", "参考"),
    "parser": ("parser", "parse", "解析"),
    "knowledge": ("knowledge", "knowledge_ir", "knowledge ir", "manual_context", "manual context", "知识"),
    "evidence": ("evidence", "证据"),
    "source_review": ("source_review", "source review", "源码复核", "源代码复核"),
    "outline": ("outline", "toc", "目录", "大纲"),
    "chapter_plan": ("chapter_plan", "chapter plan", "章节规划"),
    "manual": ("manual", "markdown", "手册", "正文"),
    "review": ("review", "checker", "审查", "检查"),
}
RESTART_NEGATION_WORDS = ("不要", "不", "别", "无需", "不用", "skip", "without", "do not", "don't")

MANUAL_TRIGGERS = (
    "生成代码手册",
    "生成手册",
    "代码手册",
    "项目手册",
    "模块手册",
    "手册生成",
    "文档生成",
    "manual",
    "manual_ir",
    "manual_context",
    "contextpack",
    "parser",
    "knowledge",
    "rtl",
)

CONTINUE_WORDS = (
    "继续",
    "下一步",
    "开始",
    "确认",
    "好的",
    "好",
    "ok",
    "yes",
    "go on",
)

STEP_BY_STEP_WORDS = (
    "分阶段",
    "一步步",
    "单步",
    "逐步",
    "不要自动",
    "先不要继续",
)

AUTO_RUN_WORDS = (
    "自动",
    "一次性",
    "直接完成",
    "跑完整",
    "完整跑完",
)

REGENERATE_WORDS = (
    "重新生成",
    "重新跑",
    "重新执行",
    "强制生成",
    "强制重跑",
    "覆盖生成",
    "不要复用",
)

DEFAULT_ENRICH_MODULES = ""

REFERENCE_FILES = (
    "backend/skills/catalog/rtl-manual-generation/references/skill_script_reference.md",
)

PROJECT_EVIDENCE_MODE = "project"
READING_PATH_EVIDENCE_MODE = "reading_path"
VALID_AUDIENCES = {"newcomer", "maintainer", "reviewer"}
SOURCE_REVIEW_MAX_MODULES = 20
SOURCE_REVIEW_MAX_TARGETS_PER_MODULE = 8
SOURCE_REVIEW_MAX_SNIPPET_LINES = 180
SOURCE_REVIEW_MAX_SNIPPET_CHARS = 16000


def should_handle_manual_workflow(user_input, state):
    text = (user_input or "").strip()
    if not text:
        return False

    if state and state.get("active") and state.get("stage") != "done":
        return True

    if state and state.get("active") and is_continue_request(text):
        return True

    return is_manual_request(text)


def is_manual_request(text):
    lower_text = (text or "").lower()
    return any(trigger.lower() in lower_text for trigger in MANUAL_TRIGGERS)


def is_continue_request(text):
    lower_text = (text or "").strip().lower()
    return any(word in lower_text for word in CONTINUE_WORDS)


def _update_execution_mode(state, user_input, auto_run):
    if auto_run is not None:
        state["auto_run"] = bool(auto_run)
        return

    if _wants_step_by_step(user_input):
        state["auto_run"] = False
        return

    if _wants_auto_run(user_input):
        state["auto_run"] = True


def _wants_step_by_step(text):
    return any(word in (text or "") for word in STEP_BY_STEP_WORDS)


def _wants_auto_run(text):
    return any(word in (text or "") for word in AUTO_RUN_WORDS)


def _wants_regenerate(text):
    return any(word in (text or "") for word in REGENERATE_WORDS)


def _extract_restart_stage(text):
    raw_text = text or ""
    lower_text = raw_text.lower()
    if not any(word.lower() in lower_text for word in RESTART_WORDS):
        return ""

    matches = []
    for stage, aliases in RESTART_STAGE_ALIASES.items():
        for alias in aliases:
            alias_text = alias.lower()
            start = lower_text.find(alias_text)
            while start >= 0:
                if not _stage_mention_is_negated(lower_text, start):
                    matches.append((start, stage))
                start = lower_text.find(alias_text, start + len(alias_text))

    if not matches:
        return ""

    matches.sort(key=lambda item: item[0])
    return matches[0][1]


def _stage_mention_is_negated(lower_text, start_index):
    prefix = lower_text[max(0, start_index - 16):start_index]
    return any(word.lower() in prefix for word in RESTART_NEGATION_WORDS)


def _reset_from_stage(state, stage):
    if stage not in MANUAL_STAGE_ORDER:
        return

    index = MANUAL_STAGE_ORDER.index(stage)
    affected_stages = list(MANUAL_STAGE_ORDER[index:])
    affected_set = set(affected_stages)

    state["stage"] = stage
    state["active"] = True
    state["restart_stage"] = stage
    state["last_error"] = ""
    state["force_regenerate"] = False
    state["force_stages"] = affected_stages
    state["completed_stages"] = [
        item for item in state.get("completed_stages", [])
        if item not in affected_set
    ]
    _clear_stage_outputs(state, affected_set)


def _clear_stage_outputs(state, affected_stages):
    if "parser" in affected_stages:
        state["parser_result"] = ""
    if "knowledge" in affected_stages:
        state["knowledge_result"] = ""
    if "evidence" in affected_stages:
        state["evidence_digest"] = {}
    if "source_review" in affected_stages:
        state["source_review_report"] = {}
        state["source_review_output_path"] = ""
    if "outline" in affected_stages:
        state["outline"] = []
    if "chapter_plan" in affected_stages:
        state["chapter_plan"] = []
    if "manual" in affected_stages:
        state["manual_summary"] = {}
        state["manual_needs_regenerate"] = True
    if "review" in affected_stages:
        state["review_report"] = ""
        state["review_output_path"] = ""


def _extract_enrich_modules(text):
    value = _match_value(
        text or "",
        (
            r"enrich_modules\s*(?:=|:|：|是|为)?\s*([A-Za-z0-9_,$\-\s，]+)",
            r"增强模块\s*(?:=|:|：|是|为)?\s*([A-Za-z0-9_,$\-\s，]+)",
            r"语义模块\s*(?:=|:|：|是|为)?\s*([A-Za-z0-9_,$\-\s，]+)",
        ),
    )
    if not value:
        return ""
    modules = [
        item.strip()
        for item in re.split(r"[,，\s]+", value)
        if item.strip()
    ]
    return ",".join(modules)


def handle_manual_workflow(user_input, state, base_dir, client, model, auto_run=None, event_logger=None):
    if (
        state
        and (not state.get("active") or state.get("stage") == "done")
        and is_manual_request(user_input)
        and not is_continue_request(user_input)
        and not _extract_restart_stage(user_input)
    ):
        state = None

    state = _ensure_state(state)
    _update_state_from_user_input(state, user_input)
    _update_execution_mode(state, user_input, auto_run)

    _log_event(
        event_logger,
        "manual_workflow_request",
        skill=MANUAL_SKILL_NAME,
        stage=state.get("stage"),
        project_root=state.get("project_root"),
        rtl_inputs=state.get("rtl_inputs"),
        top_module=state.get("top_module"),
        evidence_mode=state.get("evidence_mode"),
        auto_run=state.get("auto_run"),
        force_regenerate=state.get("force_regenerate"),
        force_stages=state.get("force_stages"),
        semantic_enrichment=state.get("semantic_enrichment"),
        enrich_modules=state.get("enrich_modules"),
    )

    if _is_cancel_request(user_input):
        state["active"] = False
        state["stage"] = "cancelled"
        return "已取消当前代码手册生成流程。", state

    if not state.get("top_module"):
        state["stage"] = "awaiting_top_module"
        return _format_reply(
            state,
            "等待顶层模块",
            [
                "我已经进入后端驱动的 RTL 代码手册流水线，但还缺少 `top_module`。",
                "请回复顶层模块名，例如：`top_module=arm_soc_top`。",
                f"当前 project_root：`{state['project_root']}`",
                f"当前 rtl_inputs：`{state['rtl_inputs']}`",
            ],
        ), state

    if state.get("stage") in ("collect_params", "awaiting_top_module"):
        state["stage"] = "references"

    if not state.get("auto_run", True):
        return _run_current_stage(state, base_dir, client, model, user_input, event_logger), state

    replies = []
    for _ in range(10):
        before_stage = state.get("stage")
        _log_event(
            event_logger,
            "manual_stage_start",
            skill=MANUAL_SKILL_NAME,
            stage=before_stage,
        )
        reply = _run_current_stage(state, base_dir, client, model, user_input, event_logger)
        replies.append(reply)
        after_stage = state.get("stage")
        _log_event(
            event_logger,
            "manual_stage_end",
            skill=MANUAL_SKILL_NAME,
            from_stage=before_stage,
            to_stage=after_stage,
            last_error=state.get("last_error", ""),
        )

        if after_stage in ("done", "cancelled", "awaiting_top_module"):
            break
        if state.get("last_error"):
            break
        if after_stage == before_stage:
            break

    return _combine_stage_replies(replies), state


def _run_current_stage(state, base_dir, client, model, user_input, event_logger=None):
    stage = state.get("stage")
    handler = MANUAL_STAGE_HANDLERS.get(stage)
    if handler:
        return handler(state, base_dir, client, model, user_input, event_logger)
    if stage == "done":
        return _format_reply(
            state,
            "流程已完成",
            [
                "当前代码手册生成流程已经完成。",
                f"Manual Context 目录：`{state.get('manual_context_dir', '')}`",
                f"手册输出：`{state.get('manual_output_path') or '未保存到文件'}`",
            ],
        )

    state["stage"] = "references"
    return _run_reference_stage(state, base_dir, event_logger)


MANUAL_STAGE_HANDLERS = {
    "references": lambda state, base_dir, client, model, user_input, event_logger: _run_reference_stage(
        state, base_dir, event_logger
    ),
    "parser": lambda state, base_dir, client, model, user_input, event_logger: _run_parser_stage(
        state, event_logger
    ),
    "knowledge": lambda state, base_dir, client, model, user_input, event_logger: _run_knowledge_stage(
        state, event_logger
    ),
    "evidence": lambda state, base_dir, client, model, user_input, event_logger: _run_evidence_stage(
        state, event_logger
    ),
    "source_review": lambda state, base_dir, client, model, user_input, event_logger: _run_source_review_stage(
        state, client, model, event_logger
    ),
    "outline": lambda state, base_dir, client, model, user_input, event_logger: _run_outline_stage(
        state, event_logger
    ),
    "chapter_plan": lambda state, base_dir, client, model, user_input, event_logger: _run_chapter_plan_stage(
        state, event_logger
    ),
    "manual": lambda state, base_dir, client, model, user_input, event_logger: _run_manual_stage(
        state, client, model, user_input, event_logger
    ),
    "review": lambda state, base_dir, client, model, user_input, event_logger: _run_review_stage(
        state, client, model, event_logger
    ),
}


def _combine_stage_replies(replies):
    clean_replies = [reply for reply in replies if reply]
    if not clean_replies:
        return ""
    if len(clean_replies) == 1:
        return clean_replies[0]
    return "\n\n---\n\n".join(clean_replies)


def _log_event(event_logger, event_type, **payload):
    if event_logger is None:
        return
    try:
        event_logger(event_type, **payload)
    except Exception:
        pass


def _ensure_state(state):
    if not state:
        return {
            "active": True,
            "skill": MANUAL_SKILL_NAME,
            "stage": "collect_params",
            "project_root": ".",
            "rtl_inputs": "rtl",
            "top_module": "",
            "audience": "newcomer",
            "evidence_mode": PROJECT_EVIDENCE_MODE,
            "completed_stages": [],
            "artifacts": {},
            "evidence_digest": {},
            "outline": [],
            "chapter_plan": [],
            "manual_summary": {},
            "review_report": "",
            "review_output_path": "",
            "source_review_report": {},
            "source_review_output_path": "",
            "manual_needs_regenerate": False,
            "last_error": "",
            "manual_output_path": "",
            "manual_output_override": "",
            "auto_run": True,
            "force_regenerate": False,
            "force_stages": [],
            "restart_stage": "",
            "semantic_enrichment": True,
            "enrich_modules": DEFAULT_ENRICH_MODULES,
        }

    state = dict(state)
    state.setdefault("active", True)
    state.setdefault("skill", MANUAL_SKILL_NAME)
    state.setdefault("stage", "collect_params")
    state.setdefault("project_root", ".")
    state.setdefault("rtl_inputs", "rtl")
    state.setdefault("top_module", "")
    state.setdefault("audience", "newcomer")
    state.setdefault("evidence_mode", PROJECT_EVIDENCE_MODE)
    state.setdefault("completed_stages", [])
    state.setdefault("artifacts", {})
    state.setdefault("evidence_digest", {})
    state.setdefault("outline", [])
    state.setdefault("chapter_plan", [])
    state.setdefault("manual_summary", {})
    state.setdefault("review_report", "")
    state.setdefault("review_output_path", "")
    state.setdefault("source_review_report", {})
    state.setdefault("source_review_output_path", "")
    state.setdefault("manual_needs_regenerate", False)
    state.setdefault("last_error", "")
    state.setdefault("manual_output_path", "")
    state.setdefault("manual_output_override", "")
    state.setdefault("auto_run", True)
    state.setdefault("force_regenerate", False)
    state.setdefault("force_stages", [])
    state.setdefault("restart_stage", "")
    state["semantic_enrichment"] = True
    state.setdefault("enrich_modules", DEFAULT_ENRICH_MODULES)
    return state


def _update_state_from_user_input(state, user_input):
    params = _extract_params(user_input)

    if not state.get("top_module") and "top_module" not in params:
        bare_top_module = _extract_bare_module_name(user_input)
        if bare_top_module:
            params["top_module"] = bare_top_module

    for key, value in params.items():
        if value:
            state[key] = value

    restart_stage = _extract_restart_stage(user_input)
    if restart_stage:
        _reset_from_stage(state, restart_stage)
    elif _wants_regenerate(user_input):
        state["force_regenerate"] = True
    state["semantic_enrichment"] = True
    enrich_modules = _extract_enrich_modules(user_input)
    if enrich_modules:
        state["enrich_modules"] = enrich_modules

    _normalize_evidence_selection(state)

    parser_dir = _select_parser_dir(state["project_root"])
    artifact_base = _artifact_base_from_parser(state["project_root"], parser_dir)
    state["parser_dir"] = str(parser_dir)
    if state.get("top_module"):
        state["knowledge_dir"] = str(artifact_base / "knowledge_ir" / state["top_module"])
        state["manual_context_dir"] = str(artifact_base / "manual_context" / state["top_module"])


def _extract_params(text):
    params = {}
    text = text or ""

    explicit_project_root = _match_value(
        text,
        (
            r"project_root\s*(?:=|:|：|是|为)?\s*([^\s，,。；;]+)",
            r"项目根目录\s*(?:=|:|：|是|为)?\s*([^\s，,。；;]+)",
        ),
    )
    explicit_rtl_inputs = _match_value(
        text,
        (
            r"rtl_inputs\s*(?:=|:|：|是|为)?\s*([^\s，,。；;]+)",
            r"RTL输入目录\s*(?:=|:|：|是|为)?\s*([^\s，,。；;]+)",
            r"RTL 输入目录\s*(?:=|:|：|是|为)?\s*([^\s，,。；;]+)",
        ),
    )
    top_module = _match_value(
        text,
        (
            r"top_module\s*(?:=|:|：|是|为)?\s*`?([A-Za-z_][A-Za-z0-9_$]*)`?",
            r"top module\s*(?:=|:|：|是|为)?\s*`?([A-Za-z_][A-Za-z0-9_$]*)`?",
            r"顶层模块(?:名)?\s*(?:=|:|：|是|为)?\s*`?([A-Za-z_][A-Za-z0-9_$]*)`?",
        ),
    )
    audience = _match_value(
        text,
        (
            r"audience\s*(?:=|:|：|是|为)?\s*(newcomer|maintainer|reviewer)",
            r"阅读对象\s*(?:=|:|：|是|为)?\s*(newcomer|maintainer|reviewer|新读者|维护者|审查者)",
        ),
    )
    evidence_mode = _match_value(
        text,
        (
            r"主证据\s*(?:=|:|：|是|为)?\s*([A-Za-z_\-一-龥]+)",
            r"证据模式\s*(?:=|:|：|是|为)?\s*([A-Za-z_\-一-龥]+)",
            r"手册类型\s*(?:=|:|：|是|为)?\s*([A-Za-z_\-一-龥]+)",
        ),
    )

    if explicit_project_root:
        params["project_root"] = _clean_path(explicit_project_root)
    if explicit_rtl_inputs:
        params["rtl_inputs"] = _clean_path(explicit_rtl_inputs)
    if top_module:
        params["top_module"] = top_module
    if audience:
        params["audience"] = _normalize_audience(audience)
    if evidence_mode:
        _apply_evidence_mode_text(params, evidence_mode)

    _apply_evidence_mode_text(params, text)

    path_text = _extract_first_path(text)
    if path_text and not explicit_project_root:
        inferred_project_root, inferred_rtl_inputs = _infer_project_paths(path_text)
        params["project_root"] = inferred_project_root
        if not explicit_rtl_inputs:
            params["rtl_inputs"] = inferred_rtl_inputs

    return params


def _apply_evidence_mode_text(params, text):
    lower_text = (text or "").lower()
    if any(word in lower_text for word in ("project", "full", "complete")):
        params["evidence_mode"] = PROJECT_EVIDENCE_MODE
    if any(word in (text or "") for word in ("完整项目", "整个项目", "项目代码手册", "完整代码手册", "全项目")):
        params["evidence_mode"] = PROJECT_EVIDENCE_MODE

    if any(word in lower_text for word in ("reading_path", "reading guide")):
        params["evidence_mode"] = READING_PATH_EVIDENCE_MODE

    if any(word in (text or "") for word in ("新读者", "入门指南", "新人指南")):
        params["evidence_mode"] = READING_PATH_EVIDENCE_MODE
        params["audience"] = "newcomer"
    if any(word in (text or "") for word in ("维护者", "维护指南")):
        params["evidence_mode"] = READING_PATH_EVIDENCE_MODE
        params["audience"] = "maintainer"
    if any(word in (text or "") for word in ("审查者", "审查指南", "审核指南")):
        params["evidence_mode"] = READING_PATH_EVIDENCE_MODE
        params["audience"] = "reviewer"


def _normalize_audience(value):
    mapping = {
        "新读者": "newcomer",
        "维护者": "maintainer",
        "审查者": "reviewer",
    }
    value = (value or "").strip()
    return mapping.get(value, value)


def _normalize_evidence_selection(state):
    if state.get("audience") not in VALID_AUDIENCES:
        state["audience"] = "newcomer"
    if state.get("evidence_mode") not in {PROJECT_EVIDENCE_MODE, READING_PATH_EVIDENCE_MODE}:
        state["evidence_mode"] = PROJECT_EVIDENCE_MODE


def _match_value(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _extract_first_path(text):
    match = re.search(r"[A-Za-z]:[\\/][^\n\r\t，,。；;]+", text or "")
    if not match:
        return ""
    return _clean_path(match.group(0))


def _extract_bare_module_name(text):
    value = (text or "").strip().strip("`'\"")
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", value):
        if value.lower() not in {"ok", "yes", "go", "continue"}:
            return value
    return ""


def _clean_path(value):
    value = (value or "").strip().strip("`'\"")
    for splitter in ("并", "，", ",", "。", "；", ";"):
        value = value.split(splitter)[0]
    return value.strip().strip("`'\"")


def _infer_project_paths(path_text):
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


def _looks_like_rtl_input_dir(path):
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


def _is_cancel_request(text):
    lower_text = (text or "").strip().lower()
    return "取消" in lower_text and ("手册" in lower_text or "manual" in lower_text)


def _run_reference_stage(state, base_dir, event_logger=None):
    results = []
    for reference_file in REFERENCE_FILES:
        path = Path(base_dir) / reference_file
        if path.exists():
            content = path.read_text(encoding="utf-8")
            results.append({
                "path": reference_file,
                "ok": True,
                "chars": len(content),
            })
        else:
            results.append({
                "path": reference_file,
                "ok": False,
                "chars": 0,
            })

    state["references"] = results
    _log_event(
        event_logger,
        "manual_references_read",
        skill=MANUAL_SKILL_NAME,
        references=results,
    )
    _mark_stage_done(state, "references")
    state["stage"] = "parser"

    lines = [
        "阶段1完成：reference 规则文件读取完毕。",
        "",
        "固定流水线已经接管后续步骤：",
        "2. Parser Tool：读取 `project_root/rtl_inputs`，生成 `parser_pipeline_rtl/`。",
        "3. Knowledge Tool：读取 parser 产物，生成 `knowledge_ir/<top_module>/` 与 `manual_context/<top_module>/`。",
        "4. Evidence：建立 Manual Context 主证据索引。",
        "5. Source Review：对需要 RTL 源码复核的关键项做受控 AI 复核并写回 Manual Context。",
        "6. Outline：根据证据生成完整手册目录。",
        "7. Chapter Plan：生成每章大致内容与证据来源。",
        "8. Manual：生成 Markdown 代码手册正文。",
        "9. Review：审查手册是否越过公开输出边界。",
        "",
        "reference 文件结果：",
    ]
    for item in results:
        status = "OK" if item["ok"] else "缺失"
        lines.append(f"- {item['path']}：{status}，{item['chars']} 字符")

    lines.extend([
        "",
        _next_stage_hint(state, "阶段2：运行 Parser Tool"),
    ])
    return _format_reply(state, "阶段1：读取规则", lines)


def _next_stage_hint(state, next_stage_text):
    if state.get("auto_run", True):
        return f"自动进入下一阶段：{next_stage_text}。"
    return f"发送 `继续` 将进入{next_stage_text}。"


def _force_regenerate(state):
    return bool(state.get("force_regenerate"))


def _should_force_stage(state, stage):
    return _force_regenerate(state) or stage in set(state.get("force_stages", []))


def _candidate_parser_dirs(project_root):
    root = Path(project_root)
    return [
        root / "rtl" / "parser_pipeline_rtl",
        root / "parser_pipeline_rtl",
    ]


def _select_parser_dir(project_root):
    candidates = _candidate_parser_dirs(project_root)
    for candidate in candidates:
        if (candidate / "project_index.json").exists() and (candidate / "modules").is_dir():
            return candidate
    return candidates[-1]


def _artifact_base_from_parser(project_root, parser_dir):
    parser_dir = Path(parser_dir)
    if parser_dir.parent.name == "rtl":
        return parser_dir.parent
    return Path(project_root)


def _parser_artifacts_ready(state):
    parser_dir = _select_parser_dir(state["project_root"])
    required_items = [
        parser_dir / "project_index.json",
        parser_dir / "build_report.json",
        parser_dir / "modules",
        parser_dir / "components",
    ]
    missing = [path for path in required_items if not path.exists()]
    return not missing, parser_dir, missing


def _run_parser_stage(state, event_logger=None):
    project_root = state["project_root"]
    rtl_inputs = state["rtl_inputs"]

    ready, parser_dir, missing = _parser_artifacts_ready(state)
    if ready and not _should_force_stage(state, "parser"):
        _log_event(
            event_logger,
            "tool_skip",
            skill=MANUAL_SKILL_NAME,
            tool="run_parser_tool",
            reason="parser_artifacts_ready",
            output_dir=str(parser_dir),
        )
        state["parser_result"] = f"复用已有 Parser 产物：{parser_dir}"
        _mark_stage_done(state, "parser")
        state["stage"] = "knowledge"
        return _format_reply(
            state,
            "阶段2：Parser Tool 已跳过",
            [
                "检测到已有 `parser_pipeline_rtl/` 且关键产物齐全，本次复用已有 Parser 产物。",
                f"Parser 产物目录：`{parser_dir}`",
                "",
                "如需重新生成，请在请求中加入 `重新生成`、`强制生成` 或 `覆盖生成`。",
                "",
                _next_stage_hint(state, "阶段3：运行或复用 Knowledge Tool"),
            ],
        )

    _log_event(
        event_logger,
        "tool_start",
        skill=MANUAL_SKILL_NAME,
        tool="run_parser_tool",
        args={"project_root": project_root, "rtl_inputs": rtl_inputs},
    )
    result = run_parser_tool(project_root=project_root, rtl_inputs=rtl_inputs)

    state["parser_result"] = _clip_text(result)
    if _tool_failed(result):
        _log_event(
            event_logger,
            "tool_end",
            skill=MANUAL_SKILL_NAME,
            tool="run_parser_tool",
            status="error",
            result_preview=_clip_text(result, 1200),
        )
        state["last_error"] = result
        return _format_reply(
            state,
            "阶段2：Parser Tool 失败",
            [
                "Parser Tool 没有成功生成 `parser_pipeline_rtl/`。",
                "我不会继续编造项目结构。请根据下面的错误修正路径或输入目录后再继续。",
                "",
                "```text",
                _clip_text(result, 3000),
                "```",
            ],
        )

    _log_event(
        event_logger,
        "tool_end",
        skill=MANUAL_SKILL_NAME,
        tool="run_parser_tool",
        status="success",
        result_preview=_clip_text(result, 1200),
    )
    _mark_stage_done(state, "parser")
    state["stage"] = "knowledge"
    return _format_reply(
        state,
        "阶段2：Parser Tool 完成",
        [
            "Parser Tool 已完成，后端记录了 parser 产物目录。",
            f"parser 产物目录：`{state.get('parser_dir', '')}`",
            "",
            _next_stage_hint(state, "阶段3：运行 Knowledge Tool"),
            "",
            "```text",
            _clip_text(result, 1800),
            "```",
        ],
    )


def _knowledge_artifacts_ready(state):
    manual_context_dir = Path(state["manual_context_dir"])
    knowledge_dir = Path(state["knowledge_dir"])
    required_items = [
        knowledge_dir / "manifest.json",
        knowledge_dir / "project.json",
        knowledge_dir / "modules",
        knowledge_dir / "ai_context" / "index.json",
        manual_context_dir / "manifest.json",
        manual_context_dir / "project_context.json",
        manual_context_dir / "system_topology.json",
        manual_context_dir / "interface_index.json",
        manual_context_dir / "flow_index.json",
        manual_context_dir / "evidence_index.json",
        manual_context_dir / "validation_report.json",
        manual_context_dir / "modules" / state["top_module"] / "module_context.json",
        manual_context_dir / "modules" / state["top_module"] / "module_doc_card.json",
        manual_context_dir / "modules" / state["top_module"] / "interfaces.json",
        manual_context_dir / "modules" / state["top_module"] / "gaps.json",
    ]
    if state.get("semantic_enrichment"):
        required_items.append(knowledge_dir / "semantic" / "index.json")

    missing = [path for path in required_items if not path.exists()]
    if missing:
        return False, manual_context_dir, missing

    try:
        manifest = _read_json(manual_context_dir / "manifest.json")
    except Exception:
        return False, manual_context_dir, [manual_context_dir / "manifest.json"]

    if manifest.get("top_module") and manifest.get("top_module") != state.get("top_module"):
        return False, manual_context_dir, [manual_context_dir / "manifest.json"]

    return True, manual_context_dir, []


def _run_knowledge_stage(state, event_logger=None):
    project_root = state["project_root"]
    top_module = state["top_module"]
    audience = state.get("audience", "newcomer")
    enrich = bool(state.get("semantic_enrichment"))
    enrich_modules = state.get("enrich_modules") or DEFAULT_ENRICH_MODULES

    ready, manual_context_dir, missing = _knowledge_artifacts_ready(state)
    if ready and not _should_force_stage(state, "knowledge"):
        _log_event(
            event_logger,
            "tool_skip",
            skill=MANUAL_SKILL_NAME,
            tool="run_knowledge_tool",
            reason="manual_context_artifacts_ready",
            output_dir=str(manual_context_dir),
        )
        state["knowledge_result"] = f"复用已有 Manual Context 产物：{manual_context_dir}"
        _mark_stage_done(state, "knowledge")
        state["stage"] = "evidence"
        return _format_reply(
            state,
            "阶段3：Knowledge Tool 已跳过",
            [
                "检测到已有 `manual_context/<top_module>/` 且关键产物齐全，本次复用已有 Manual Context。",
                f"Knowledge IR 目录：`{state.get('knowledge_dir', '')}`",
                f"Manual Context 目录：`{manual_context_dir}`",
                "Semantic Layer：`已满足或已按配置跳过`",
                "",
                "如需重新生成，请在请求中加入 `重新生成`、`强制生成` 或 `覆盖生成`。",
                "",
                _next_stage_hint(state, "阶段4：建立 Manual Context 主证据索引"),
            ],
        )

    args = {
        "project_root": project_root,
        "top_module": top_module,
        "audience": audience,
        "enrich": enrich,
        "enrich_modules": enrich_modules,
    }
    _log_event(
        event_logger,
        "tool_start",
        skill=MANUAL_SKILL_NAME,
        tool="run_knowledge_tool",
        args=args,
    )
    result = run_knowledge_tool(
        project_root=project_root,
        top_module=top_module,
        audience=audience,
        enrich=enrich,
        enrich_modules=enrich_modules,
    )

    state["knowledge_result"] = _clip_text(result)
    if _tool_failed(result):
        _log_event(
            event_logger,
            "tool_end",
            skill=MANUAL_SKILL_NAME,
            tool="run_knowledge_tool",
            status="error",
            result_preview=_clip_text(result, 1200),
        )
        state["last_error"] = result
        return _format_reply(
            state,
            "阶段3：Knowledge Tool 失败",
            [
                "Knowledge Tool 没有成功生成 Manual Context。",
                "我会停在这个阶段，不会基于记忆或猜测生成手册。",
                "",
                "```text",
                _clip_text(result, 3000),
                "```",
            ],
        )

    _log_event(
        event_logger,
        "tool_end",
        skill=MANUAL_SKILL_NAME,
        tool="run_knowledge_tool",
        status="success",
        result_preview=_clip_text(result, 1200),
    )
    _mark_stage_done(state, "knowledge")
    state["stage"] = "evidence"
    return _format_reply(
        state,
        "阶段3：Knowledge Tool 完成",
        [
            "Knowledge Tool 已完成，Knowledge IR 与 Manual Context 目录已经记录到状态中。",
            f"Knowledge IR 目录：`{state.get('knowledge_dir', '')}`",
            f"Manual Context 目录：`{state.get('manual_context_dir', '')}`",
            "Semantic Layer：`开启`" if enrich else "Semantic Layer：`跳过`",
            f"语义模块：`{enrich_modules or '全部模块'}`",
            "",
            _next_stage_hint(state, "阶段4：读取 Manual Context 证据"),
            "",
            "```text",
            _clip_text(result, 1800),
            "```",
        ],
    )


def _run_evidence_stage(state, event_logger=None):
    try:
        digest = _load_manual_context_digest(state)
    except FileNotFoundError as exc:
        missing = [item for item in str(exc).splitlines() if item]
        manual_context_dir = Path(state.get("manual_context_dir", ""))
        _log_event(
            event_logger,
            "manual_evidence_missing",
            skill=MANUAL_SKILL_NAME,
            missing=missing,
        )
        state["last_error"] = "\n".join(missing)
        return _format_reply(
            state,
            "阶段4：证据读取失败",
            [
                "Manual Context 关键证据文件缺失，因此我不会继续生成项目结构。",
                "缺失文件：",
                *[f"- `{item}`" for item in missing],
            ],
        )
    except Exception as exc:
        state["last_error"] = str(exc)
        return _format_reply(
            state,
            "阶段4：证据读取失败",
            [
                "Manual Context 证据读取时发生错误。",
                "",
                "```text",
                str(exc),
                "```",
            ],
        )

    manual_context_dir = Path(state["manual_context_dir"])
    state["evidence_digest"] = digest
    _log_event(
        event_logger,
        "manual_evidence_indexed",
        skill=MANUAL_SKILL_NAME,
        evidence_mode=digest.get("evidence_mode"),
        counts=digest.get("counts"),
        manual_context_dir=str(manual_context_dir),
    )
    _mark_stage_done(state, "evidence")
    state["stage"] = "source_review"

    return _format_reply(
        state,
        "阶段4：证据读取完成",
        [
            "我已建立 Manual Context 主证据索引。下一阶段会对需要源码复核的关键项做受控 RTL 读取并写回 Manual Context。",
            "",
            _format_digest(digest),
            "",
            _next_stage_hint(state, "阶段5：AI 源码复核"),
        ],
    )


def _load_manual_context_digest(state):
    manual_context_dir = Path(state["manual_context_dir"])
    manifest_path = manual_context_dir / "manifest.json"
    project_context_path = manual_context_dir / "project_context.json"
    system_topology_path = manual_context_dir / "system_topology.json"
    interface_index_path = manual_context_dir / "interface_index.json"
    flow_index_path = manual_context_dir / "flow_index.json"
    evidence_index_path = manual_context_dir / "evidence_index.json"
    validation_report_path = manual_context_dir / "validation_report.json"

    required_paths = (
        manifest_path,
        project_context_path,
        system_topology_path,
        interface_index_path,
        flow_index_path,
        evidence_index_path,
        validation_report_path,
    )
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError("\n".join(missing))

    manifest = _read_json(manifest_path)
    project_context = _read_json(project_context_path)
    system_topology = _read_json(system_topology_path)
    interface_index = _read_json(interface_index_path)
    flow_index = _read_json(flow_index_path)
    evidence_index = _read_json(evidence_index_path)
    validation_report = _read_json(validation_report_path)
    digest = _build_manual_context_evidence_digest(
        manual_context_dir=manual_context_dir,
        manifest=manifest,
        project_context=project_context,
        system_topology=system_topology,
        interface_index=interface_index,
        flow_index=flow_index,
        evidence_index=evidence_index,
        validation_report=validation_report,
        state=state,
    )
    return digest


def _run_source_review_stage(state, client, model, event_logger=None):
    digest = state.get("evidence_digest") or _load_manual_context_digest(state)
    report_path = _source_review_output_path(state)
    if report_path.exists() and report_path.is_file() and not _should_force_stage(state, "source_review"):
        report = _read_json(report_path)
        state["source_review_report"] = report
        state["source_review_output_path"] = str(report_path)
        state["evidence_digest"] = _load_manual_context_digest(state)
        state["manual_needs_regenerate"] = True
        _mark_stage_done(state, "source_review")
        state["stage"] = "outline"
        return _format_reply(
            state,
            "阶段5：AI 源码复核已跳过",
            [
                "检测到已有源码复核报告，本次复用并重新读取 Manual Context。",
                f"源码复核报告：`{report_path}`",
                _format_source_review_summary(report),
                "",
                _next_stage_hint(state, "阶段6：根据证据生成完整手册目录"),
            ],
        )

    try:
        report = _build_source_review_report(state, digest, client, model, event_logger)
    except Exception as exc:
        state["last_error"] = str(exc)
        return _format_reply(
            state,
            "阶段5：AI 源码复核失败",
            [
                "源码复核阶段失败，流程已停在 `source_review` 阶段。",
                "",
                "```text",
                str(exc),
                "```",
            ],
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(report_path, report)
    state["source_review_report"] = report
    state["source_review_output_path"] = str(report_path)
    state["evidence_digest"] = _load_manual_context_digest(state)
    state["manual_needs_regenerate"] = True
    _mark_stage_done(state, "source_review")
    state["stage"] = "outline"

    _log_event(
        event_logger,
        "manual_source_review_complete",
        skill=MANUAL_SKILL_NAME,
        report_path=str(report_path),
        reviewed_modules=report.get("reviewed_modules", 0),
        claim_count=report.get("claim_count", 0),
        unresolved_count=report.get("unresolved_count", 0),
    )
    return _format_reply(
        state,
        "阶段5：AI 源码复核完成",
        [
            "源码复核结论已结构化写回 Manual Context，后续手册和 review 文档会从这些字段读取。",
            f"源码复核报告：`{report_path}`",
            _format_source_review_summary(report),
            "",
            _next_stage_hint(state, "阶段6：根据证据生成完整手册目录"),
        ],
    )


def _source_review_output_path(state):
    return Path(state["manual_context_dir"]) / "source_review_report.json"


def _build_source_review_report(state, digest, client, model, event_logger=None):
    targets = _collect_source_review_targets(digest)
    reports = []
    for target in targets:
        _log_event(
            event_logger,
            "manual_source_review_module_start",
            skill=MANUAL_SKILL_NAME,
            module=target.get("module"),
            target_count=len(target.get("items", [])),
        )
        module_report = _review_source_for_module(state, target, client, model)
        _write_source_review_module_report(state, module_report)
        reports.append(module_report)
        _log_event(
            event_logger,
            "manual_source_review_module_end",
            skill=MANUAL_SKILL_NAME,
            module=target.get("module"),
            status=module_report.get("status"),
            claim_count=len(module_report.get("claims", [])),
        )

    root_report = {
        "schema": "manual_context_source_review_report",
        "schema_version": "0.1",
        "top_module": digest.get("top_module", state.get("top_module", "")),
        "policy": {
            "scope": "priority_flagged_items",
            "max_modules": SOURCE_REVIEW_MAX_MODULES,
            "max_targets_per_module": SOURCE_REVIEW_MAX_TARGETS_PER_MODULE,
            "allowed_slices": [
                "module declaration",
                "related assign lines",
                "related instance connections",
                "related always snippets",
            ],
            "promotion_rule": "source review may create ai_inferred or evidence_gap claims only",
        },
        "target_count": len(targets),
        "reviewed_modules": len(reports),
        "claim_count": sum(len(item.get("claims", [])) for item in reports),
        "unresolved_count": sum(len(item.get("open_questions", [])) for item in reports),
        "modules": [
            {
                "module": item.get("module", ""),
                "status": item.get("status", ""),
                "source_file": item.get("source_file", ""),
                "target_count": len(item.get("targets", [])),
                "claim_count": len(item.get("claims", [])),
                "open_question_count": len(item.get("open_questions", [])),
                "report_file": f"modules/{safe_filename(item.get('module', ''))}/source_review_report.json",
            }
            for item in reports
        ],
    }
    _update_source_review_manifest(state, reports)
    return root_report


def _collect_source_review_targets(digest):
    top_module = digest.get("top_module", "")
    direct_modules = set(_claim_value(digest.get("project_context", {}).get("top_level", {}).get("direct_modules")) or [])
    candidates = []
    for module in digest.get("modules", []):
        module_name = module.get("module_name", "")
        policy = module.get("page_policy", {})
        detail_level = policy.get("detail_level", "standard")
        is_priority_module = (
            module_name == top_module
            or module_name in direct_modules
            or detail_level == "detailed"
        )
        if not is_priority_module:
            continue
        items = _collect_module_source_review_items(digest, module)
        if not items:
            continue
        priority = 0 if module_name == top_module else 1 if module_name in direct_modules else 2
        candidates.append({
            "module": module_name,
            "priority": priority,
            "source_file": _first_source_file_from_module(module),
            "items": items[:SOURCE_REVIEW_MAX_TARGETS_PER_MODULE],
            "page_policy": policy,
        })
    candidates.sort(key=lambda item: (item.get("priority", 99), item.get("module", "")))
    return candidates[:SOURCE_REVIEW_MAX_MODULES]


def _collect_module_source_review_items(digest, module):
    module_name = module.get("module_name", "")
    items = []

    summary = module.get("responsibility", {}).get("short_summary", {})
    if _claim_requires_source_review(summary):
        items.append(_source_review_item("module_responsibility", module_name, summary))

    for claim in module.get("responsibility", {}).get("responsibility_claims", []):
        if _claim_requires_source_review(claim):
            items.append(_source_review_item("responsibility_claim", module_name, claim))

    for gap in module.get("evidence_gaps", []):
        items.append(_source_review_item("evidence_gap", module_name, gap))
    for gap in module.get("gap_file", {}).get("gaps", []):
        items.append(_source_review_item("evidence_gap", module_name, gap))
    for question in module.get("review_questions", []):
        items.append(_source_review_item("review_question", module_name, question))

    for flow in _load_module_flow_contexts(digest, module):
        semantic = flow.get("semantic_meaning", {})
        if _claim_requires_source_review(semantic) or flow.get("gaps"):
            items.append(_source_review_item("flow", module_name, {
                "subject": flow.get("flow_id", ""),
                "value": semantic.get("value", flow.get("title", "")),
                "explanation": semantic.get("explanation", ""),
                "signals": [flow.get("trigger_event", {}).get("signal", "")],
                "instances": [],
                "field": flow.get("flow_id", ""),
                "reason": "; ".join(_plain(gap.get("reason", "")) for gap in flow.get("gaps", []) if isinstance(gap, dict)),
                "requires_rtl_source_review": semantic.get("requires_rtl_source_review", False),
                "review_status": semantic.get("review_status", ""),
                "evidence_refs": flow.get("evidence_refs", []),
            }))

    deduped = []
    seen = set()
    for item in items:
        key = (item.get("kind"), item.get("subject"), item.get("reason"), item.get("summary"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _claim_requires_source_review(claim):
    if not isinstance(claim, dict):
        return False
    return (
        bool(claim.get("requires_rtl_source_review"))
        or claim.get("review_status") == "needs_review"
        or claim.get("certainty") == "evidence_gap"
    )


def _source_review_item(kind, module_name, item):
    item = item if isinstance(item, dict) else {"reason": str(item)}
    return {
        "kind": kind,
        "module": module_name,
        "subject": _plain(item.get("subject") or item.get("field") or item.get("semantic_claim_id") or kind),
        "summary": _plain(item.get("value") or item.get("summary") or item.get("question") or ""),
        "explanation": _plain(item.get("explanation") or ""),
        "reason": _plain(item.get("reason") or item.get("question") or ""),
        "signals": [value for value in item.get("signals", []) if value],
        "instances": [value for value in item.get("instances", []) if value],
        "evidence_refs": item.get("evidence_refs", []),
        "requires_rtl_source_review": bool(item.get("requires_rtl_source_review")),
        "review_status": item.get("review_status", ""),
    }


def _review_source_for_module(state, target, client, model):
    module_name = target.get("module", "")
    source_file = target.get("source_file", "")
    source_path = _resolve_source_path(state, source_file)
    if not source_path.exists():
        return _source_review_fallback_report(
            target,
            status="source_missing",
            reason=f"RTL source file not found: {source_file}",
        )

    source_text = source_path.read_text(encoding="utf-8", errors="replace")
    source_lines = source_text.splitlines()
    tokens = _source_review_tokens(target)
    snippets = _extract_rtl_review_snippets(source_lines, module_name, tokens)
    if not snippets:
        return _source_review_fallback_report(
            target,
            status="no_relevant_slice",
            reason="No whitelisted source slice matched the flagged items.",
            source_refs=[{"file": source_file, "line_start": 1, "line_end": min(len(source_lines), 1)}],
        )

    if client is None or model is None:
        return _source_review_fallback_report(
            target,
            status="model_unavailable",
            reason="No model client is available for AI source review.",
            source_refs=_snippet_source_refs(source_file, snippets),
        )

    messages = _build_source_review_messages(module_name, target.get("items", []), source_file, snippets)
    try:
        response = client.chat.completions.create(model=model, messages=messages)
        raw = response.choices[0].message.content
        parsed = _parse_source_review_response(raw)
    except Exception as exc:
        return _source_review_fallback_report(
            target,
            status="model_failed",
            reason=str(exc),
            source_refs=_snippet_source_refs(source_file, snippets),
        )

    claims, open_questions = _normalize_source_review_payload(parsed, target, source_file, snippets)
    status = "reviewed" if claims else "reviewed_without_claims"
    return {
        "schema": "manual_context_module_source_review_report",
        "schema_version": "0.1",
        "module": module_name,
        "status": status,
        "source_file": source_file,
        "targets": target.get("items", []),
        "source_refs": _snippet_source_refs(source_file, snippets),
        "claims": claims,
        "open_questions": open_questions,
        "raw_model_chars": len(raw or ""),
    }


def _source_review_fallback_report(target, status, reason, source_refs=None):
    module_name = target.get("module", "")
    refs = source_refs or []
    claim = {
        "subject": "source_review",
        "summary": "源码复核未形成可写入公开手册的结论。",
        "explanation": reason,
        "certainty": "evidence_gap",
        "source_layers": ["source_review"],
        "signals": _source_review_tokens(target)[:20],
        "instances": [],
        "source_refs": refs,
        "evidence_refs": _target_evidence_refs(target),
        "review_status": "needs_review",
    }
    return {
        "schema": "manual_context_module_source_review_report",
        "schema_version": "0.1",
        "module": module_name,
        "status": status,
        "source_file": target.get("source_file", ""),
        "targets": target.get("items", []),
        "source_refs": refs,
        "claims": [claim],
        "open_questions": [
            {
                "subject": "source_review",
                "question": reason,
                "source_refs": refs,
                "evidence_refs": _target_evidence_refs(target),
            }
        ],
    }


def _resolve_source_path(state, source_file):
    source_file = str(source_file or "")
    path = Path(source_file)
    if path.is_absolute():
        return path
    return Path(state.get("project_root", ".")) / path


def _first_source_file_from_module(module):
    source_files = module.get("source_files", [])
    if source_files:
        return source_files[0]
    context = module.get("source_review_context", {})
    return context.get("rtl_file", "")


def _source_review_tokens(target):
    tokens = set()
    for item in target.get("items", []):
        for key in ("signals", "instances"):
            for value in item.get(key, []) or []:
                if value:
                    tokens.add(str(value))
        for key in ("subject", "summary", "explanation", "reason"):
            for match in re.findall(r"\b[A-Za-z_][A-Za-z0-9_$]*\b", item.get(key, "") or ""):
                if len(match) > 1 and match not in {"review", "source", "module", "flow"}:
                    tokens.add(match)
    tokens.add(target.get("module", ""))
    return sorted(token for token in tokens if token)


def _extract_rtl_review_snippets(lines, module_name, tokens):
    ranges = []
    module_range = _find_module_declaration_range(lines, module_name)
    if module_range:
        ranges.append(module_range)

    token_set = set(tokens)
    for index, line in enumerate(lines):
        if not _line_matches_tokens(line, token_set):
            continue
        start = max(1, index - 2 + 1)
        end = min(len(lines), index + 3)
        if "always" in line:
            end = min(len(lines), index + 24)
        ranges.append((start, end))

    merged = _merge_line_ranges(ranges)
    snippets = []
    total_lines = 0
    total_chars = 0
    for start, end in merged:
        if total_lines >= SOURCE_REVIEW_MAX_SNIPPET_LINES or total_chars >= SOURCE_REVIEW_MAX_SNIPPET_CHARS:
            break
        excerpt_lines = []
        for number in range(start, end + 1):
            excerpt_lines.append(f"{number}: {lines[number - 1]}")
        text = "\n".join(excerpt_lines)
        snippets.append({"line_start": start, "line_end": end, "text": text})
        total_lines += end - start + 1
        total_chars += len(text)
    return snippets


def _find_module_declaration_range(lines, module_name):
    pattern = re.compile(rf"\bmodule\s+{re.escape(module_name)}\b")
    for index, line in enumerate(lines):
        if not pattern.search(line):
            continue
        end = index + 1
        while end < len(lines) and end - index < 120:
            if ");" in lines[end] or lines[end].strip().endswith(";"):
                return (index + 1, end + 1)
            end += 1
        return (index + 1, min(len(lines), index + 80))
    return None


def _line_matches_tokens(line, tokens):
    if not tokens:
        return False
    return any(token and token in line for token in tokens)


def _merge_line_ranges(ranges):
    if not ranges:
        return []
    ordered = sorted((max(1, start), max(start, end)) for start, end in ranges)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + 2:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _snippet_source_refs(source_file, snippets):
    return [
        {
            "file": source_file,
            "line_start": item.get("line_start"),
            "line_end": item.get("line_end"),
        }
        for item in snippets
    ]


def _build_source_review_messages(module_name, items, source_file, snippets):
    snippet_text = "\n\n".join(
        f"[slice {index}: lines {item['line_start']}-{item['line_end']}]\n{item['text']}"
        for index, item in enumerate(snippets, start=1)
    )
    target_text = json.dumps(items, ensure_ascii=False, indent=2)
    system_prompt = (
        "你是 RTL 源码复核助手。只允许基于用户提供的 flagged Manual Context 项和 RTL 白名单切片作答。"
        "不要补写未被要求的连接、flow、FSM、always 行为、寄存器更新条件或时序保证。"
        "输出必须是 JSON，不要 Markdown 或代码围栏。summary、explanation、question 必须用简体中文；"
        "模块名、信号名、实例名保持源码原文。certainty 只能是 ai_inferred 或 evidence_gap。"
    )
    user_prompt = (
        f"模块：{module_name}\n"
        f"源码文件：{source_file}\n\n"
        "需要复核的 Manual Context 项：\n"
        f"{target_text}\n\n"
        "允许阅读的 RTL 切片：\n"
        f"{snippet_text}\n\n"
        "请输出 JSON：\n"
        "{\n"
        "  \"claims\": [\n"
        "    {\n"
        "      \"subject\": \"被复核对象\",\n"
        "      \"summary\": \"一句中文结论\",\n"
        "      \"explanation\": \"中文说明，只引用给定切片能支持的内容\",\n"
        "      \"certainty\": \"ai_inferred 或 evidence_gap\",\n"
        "      \"signals\": [\"相关信号\"],\n"
        "      \"instances\": [\"相关实例\"],\n"
        "      \"source_refs\": [{\"file\": \"源码文件\", \"line_start\": 1, \"line_end\": 2}]\n"
        "    }\n"
        "  ],\n"
        "  \"open_questions\": [\n"
        "    {\"subject\": \"对象\", \"question\": \"仍需人工确认的问题\", \"source_refs\": []}\n"
        "  ]\n"
        "}\n"
    )
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]


def _parse_source_review_response(raw):
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start:end + 1]
    return json.loads(text)


def _normalize_source_review_payload(payload, target, source_file, snippets):
    default_refs = _snippet_source_refs(source_file, snippets)
    evidence_refs = _target_evidence_refs(target)
    claims = []
    for item in (payload.get("claims", []) if isinstance(payload, dict) else []):
        if not isinstance(item, dict):
            continue
        certainty = item.get("certainty")
        if certainty not in {"ai_inferred", "evidence_gap"}:
            certainty = "evidence_gap"
        claims.append({
            "subject": _plain(item.get("subject") or "source_review"),
            "summary": _plain(item.get("summary") or ""),
            "explanation": _plain(item.get("explanation") or ""),
            "certainty": certainty,
            "source_layers": ["source_review", "rtl_source", "manual_context"],
            "signals": item.get("signals", []) if isinstance(item.get("signals"), list) else [],
            "instances": item.get("instances", []) if isinstance(item.get("instances"), list) else [],
            "source_refs": item.get("source_refs") if isinstance(item.get("source_refs"), list) and item.get("source_refs") else default_refs,
            "evidence_refs": evidence_refs,
            "review_status": "needs_review" if certainty == "evidence_gap" else "ready",
        })
    open_questions = []
    for item in (payload.get("open_questions", []) if isinstance(payload, dict) else []):
        if not isinstance(item, dict):
            continue
        open_questions.append({
            "subject": _plain(item.get("subject") or "source_review"),
            "question": _plain(item.get("question") or ""),
            "source_refs": item.get("source_refs") if isinstance(item.get("source_refs"), list) else default_refs,
            "evidence_refs": evidence_refs,
        })
    return claims, open_questions


def _target_evidence_refs(target):
    refs = []
    for item in target.get("items", []):
        refs.extend(ref for ref in item.get("evidence_refs", []) if ref)
    return list(dict.fromkeys(refs))


def _write_source_review_module_report(state, report):
    manual_context_dir = Path(state["manual_context_dir"])
    module_name = report.get("module", "")
    module_dir = manual_context_dir / "modules" / safe_filename(module_name)
    module_context_path = module_dir / "module_context.json"
    module_doc_card_path = module_dir / "module_doc_card.json"
    report_path = module_dir / "source_review_report.json"
    module_dir.mkdir(parents=True, exist_ok=True)

    if module_context_path.exists():
        module_context = _read_json(module_context_path)
    else:
        module_context = {}
    module_context["source_review_claims"] = report.get("claims", [])
    module_context["source_review_report"] = {
        "status": report.get("status", ""),
        "claim_count": len(report.get("claims", [])),
        "open_question_count": len(report.get("open_questions", [])),
        "source_file": report.get("source_file", ""),
        "report_file": "source_review_report.json",
    }
    _write_json(module_context_path, module_context)

    if module_doc_card_path.exists():
        module_doc_card = _read_json(module_doc_card_path)
        module_doc_card["source_review_claims"] = report.get("claims", [])
        module_doc_card["source_review_report"] = module_context["source_review_report"]
        _write_json(module_doc_card_path, module_doc_card)

    _write_json(report_path, report)


def _update_source_review_manifest(state, reports):
    manifest_path = Path(state["manual_context_dir"]) / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = _read_json(manifest_path)
    files = manifest.setdefault("files", {})
    files["source_review_report"] = "source_review_report.json"
    files["source_review_reports"] = {
        item.get("module", ""): f"modules/{safe_filename(item.get('module', ''))}/source_review_report.json"
        for item in reports
        if item.get("module")
    }
    counts = manifest.setdefault("counts", {})
    counts["source_review_modules"] = len(reports)
    counts["source_review_claims"] = sum(len(item.get("claims", [])) for item in reports)
    _write_json(manifest_path, manifest)


def _format_source_review_summary(report):
    return "\n".join([
        "## 源码复核摘要",
        f"- 目标模块数：{report.get('target_count', 0)}",
        f"- 已复核模块数：{report.get('reviewed_modules', 0)}",
        f"- 写回 claim 数：{report.get('claim_count', 0)}",
        f"- 未解决问题数：{report.get('unresolved_count', 0)}",
    ])


def _run_outline_stage(state, event_logger=None):
    digest = state.get("evidence_digest") or {}
    outline = _build_outline(digest)
    state["outline"] = outline
    _log_event(
        event_logger,
        "manual_outline_created",
        skill=MANUAL_SKILL_NAME,
        chapter_count=len(outline),
        titles=[item.get("title", "") for item in outline],
    )

    _mark_stage_done(state, "outline")
    state["stage"] = "chapter_plan"

    lines = [
        "阶段6完成：已根据 Manual Context 证据生成手册目录。",
        "",
        "## 拟定目录",
    ]
    for index, item in enumerate(outline, start=1):
        lines.append(f"{index}. {item['title']}")
        if item.get("evidence"):
            lines.append(f"   证据：{', '.join(item['evidence'])}")

    lines.extend([
        "",
        _next_stage_hint(state, "阶段7：生成每章大致内容规划"),
    ])
    return _format_reply(state, "阶段6：规划目录", lines)


def _run_chapter_plan_stage(state, event_logger=None):
    digest = state.get("evidence_digest") or {}
    outline = state.get("outline") or _build_outline(digest)
    chapter_plan = _build_chapter_plan(outline, digest)
    state["chapter_plan"] = chapter_plan
    _log_event(
        event_logger,
        "manual_chapter_plan_created",
        skill=MANUAL_SKILL_NAME,
        chapter_count=len(chapter_plan),
        titles=[item.get("title", "") for item in chapter_plan],
    )

    _mark_stage_done(state, "chapter_plan")
    state["stage"] = "manual"

    lines = [
        "阶段7完成：已生成每章大致内容和证据来源。",
        "",
        "## 每章内容规划",
    ]
    for index, item in enumerate(chapter_plan, start=1):
        lines.append(f"{index}. {item['title']}")
        lines.append(f"   写作目标：{item['purpose']}")
        lines.append(f"   主要内容：{'；'.join(item['content_points'])}")
        lines.append(f"   证据来源：{', '.join(item['evidence_sources'])}")
        if item.get("evidence_gaps"):
            lines.append(f"   证据边界：{'；'.join(item['evidence_gaps'])}")

    lines.extend([
        "",
        _next_stage_hint(state, "阶段8：生成完整 Markdown 手册"),
    ])
    return _format_reply(state, "阶段7：章节内容规划", lines)


def _build_chapter_plan(outline, digest):
    mode = digest.get("evidence_mode", PROJECT_EVIDENCE_MODE)
    plan = []
    for item in outline:
        title = item.get("title", "")
        evidence = item.get("evidence", [])
        purpose, content_points = _chapter_intent(title, mode)
        plan.append({
            "title": title,
            "purpose": purpose,
            "content_points": content_points,
            "evidence_sources": evidence,
            "evidence_gaps": [
                "不推断 Manual Context 未提供的 always/FSM/寄存器更新语义。",
                "缺少字段时写明当前 Manual Context 未提供足够证据。",
            ],
        })
    return plan


def _chapter_intent(title, mode):
    if mode == READING_PATH_EVIDENCE_MODE:
        return (
            "按照选定 ReadingPath 给目标读者提供阅读顺序和证据说明。",
            ["说明本章覆盖的上下文对象", "概括对象职责和风险", "标注 unresolved covers 或证据不足"],
        )

    rules = [
        ("项目总览", "用一句话说明项目用途和工程入口。", ["写项目用途推断", "列出 RTL 目录", "列出顶层文件"]),
        ("顶层模块", "解释顶层模块组成和外部端口分组。", ["列出直接一级子模块", "按 pad/端口组自然语言总结输入输出", "区分确定事实和 AI 推断"]),
        ("模块层级", "让读者看到完整父子层级。", ["列出全部 hierarchy_edges", "不使用层级样本替代完整结构", "提示证据来自 system_topology 和 module_context"]),
        ("子系统", "提供全量模块入口和模块页索引。", ["按 region 组织模块", "所有 reachable modules 都有入口", "职责摘要只保留工程师可读内容"]),
    ]
    for keyword, purpose, points in rules:
        if keyword in title:
            return purpose, points
    return "基于 Manual Context 证据解释本章主题。", ["概括相关对象", "说明关键字段", "标注证据不足"]


def _manual_file_ready(state, user_input):
    output_path = _manual_output_path(state, user_input)
    if not output_path.exists() or not output_path.is_file():
        return False, output_path
    try:
        return output_path.stat().st_size > 0, output_path
    except OSError:
        return False, output_path


def _run_manual_stage(state, client, model, user_input, event_logger=None):
    ready, output_path = _manual_file_ready(state, user_input)
    state["_manual_output_stem"] = output_path.stem
    if ready and not _should_force_stage(state, "manual") and not state.get("manual_needs_regenerate"):
        _log_event(
            event_logger,
            "model_skip",
            skill=MANUAL_SKILL_NAME,
            stage="manual",
            reason="manual_file_ready",
            output_path=str(output_path),
        )
        manual = output_path.read_text(encoding="utf-8")
        state["manual_output_path"] = str(output_path)
        state["manual_summary"] = _build_manual_summary(manual, state)
        _mark_stage_done(state, "manual")
        state["stage"] = "review"

        return _format_reply(
            state,
            "阶段8：手册生成已跳过",
            [
                "检测到已有 Markdown 代码手册文件，本次复用已有手册。",
                f"手册路径：`{state['manual_output_path']}`",
                "",
                _format_manual_summary(state["manual_summary"]),
                "",
                "如需重新生成，请在请求中加入 `重新生成`、`强制生成` 或 `覆盖生成`。",
                "",
                _next_stage_hint(state, "阶段9：审查或复用审查报告"),
            ],
        )

    try:
        _log_event(
            event_logger,
            "manual_render_start",
            skill=MANUAL_SKILL_NAME,
            stage="manual",
            model=model,
        )
        manual = _generate_manual_markdown(state, client, model)
    except Exception as exc:
        _log_event(
            event_logger,
            "manual_render_end",
            skill=MANUAL_SKILL_NAME,
            stage="manual",
            status="error",
            error=str(exc),
        )
        state["last_error"] = str(exc)
        return _format_reply(
            state,
            "阶段8：生成手册失败",
            [
                "Manual Context Markdown 渲染失败，流程已停在 `manual` 阶段。",
                "Manual Context 证据和目录规划已经保存在会话状态中，修正渲染问题后可以发送 `继续` 重试。",
                "",
                "```text",
                str(exc),
                "```",
            ],
        )

    output_path = _manual_output_path(state, user_input)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(manual + "\n", encoding="utf-8")
    module_page_paths = _write_module_pages(state, output_path)

    _log_event(
        event_logger,
        "manual_render_end",
        skill=MANUAL_SKILL_NAME,
        stage="manual",
        status="success",
        chars=len(manual),
    )
    _log_event(
        event_logger,
        "artifact_write",
        skill=MANUAL_SKILL_NAME,
        artifact="manual_markdown",
        path=str(output_path),
        chars=len(manual),
    )
    if module_page_paths:
        _log_event(
            event_logger,
            "artifact_write",
            skill=MANUAL_SKILL_NAME,
            artifact="manual_module_pages",
            path=str(output_path.with_name(output_path.stem + "_modules")),
            count=len(module_page_paths),
        )

    state["manual_output_path"] = str(output_path)
    state["manual_module_pages_dir"] = str(output_path.with_name(output_path.stem + "_modules"))
    state["manual_module_page_count"] = len(module_page_paths)
    state["manual_summary"] = _build_manual_summary(manual, state)
    state["manual_needs_regenerate"] = False
    _mark_stage_done(state, "manual")
    state["stage"] = "review"

    lines = [
        "阶段8完成：完整 Markdown 手册已生成并保存。",
        "",
        f"保存路径：`{state['manual_output_path']}`",
        f"模块页目录：`{state['manual_module_pages_dir']}`（{len(module_page_paths)} 个模块页）",
        "",
        _format_manual_summary(state["manual_summary"]),
        "",
        _next_stage_hint(state, "阶段9：审查手册"),
    ]

    return _format_reply(state, "阶段8：生成手册", lines)


def _run_review_stage(state, client, model, event_logger=None):
    manual_path = Path(state.get("manual_output_path") or state.get("manual_output_override") or "")
    if not manual_path.exists():
        _log_event(
            event_logger,
            "manual_review_missing_input",
            skill=MANUAL_SKILL_NAME,
            manual_path=str(manual_path),
        )
        state["last_error"] = f"manual file not found: {manual_path}"
        return _format_reply(
            state,
            "阶段9：审查失败",
            [
                "没有找到可审查的手册文件，流程停在 `review` 阶段。",
                f"期望路径：`{manual_path}`",
            ],
        )

    state["manual_output_path"] = str(manual_path)
    review_output_path = _review_output_path(state)
    if review_output_path.exists() and review_output_path.is_file() and not _should_force_stage(state, "review"):
        _log_event(
            event_logger,
            "model_skip",
            skill=MANUAL_SKILL_NAME,
            stage="review",
            reason="review_file_ready",
            output_path=str(review_output_path),
        )
        review = review_output_path.read_text(encoding="utf-8")
        state["review_report"] = review
        state["review_output_path"] = str(review_output_path)
        _mark_stage_done(state, "review")
        state["stage"] = "done"
        return _format_reply(
            state,
            "阶段9：审查已跳过",
            [
                "检测到已有审查报告，本次复用已有审查结果。",
                "",
                f"手册路径：`{state.get('manual_output_path', '')}`",
                f"审查报告路径：`{state.get('review_output_path', '')}`",
                "",
                _review_summary(review),
            ],
        )

    try:
        _log_event(
            event_logger,
            "manual_review_start",
            skill=MANUAL_SKILL_NAME,
            stage="review",
            model=model,
            manual_path=str(manual_path),
        )
        review = _review_manual_markdown(state, client, model)
    except Exception as exc:
        _log_event(
            event_logger,
            "manual_review_end",
            skill=MANUAL_SKILL_NAME,
            stage="review",
            status="error",
            error=str(exc),
        )
        state["last_error"] = str(exc)
        return _format_reply(
            state,
            "阶段9：审查失败",
            [
                "Manual Context 结构化审查失败，流程已停在 `review` 阶段。",
                "",
                "```text",
                str(exc),
                "```",
            ],
        )

    review_output_path.parent.mkdir(parents=True, exist_ok=True)
    review_output_path.write_text(review + "\n", encoding="utf-8")

    _log_event(
        event_logger,
        "manual_review_end",
        skill=MANUAL_SKILL_NAME,
        stage="review",
        status="success",
        chars=len(review),
    )
    _log_event(
        event_logger,
        "artifact_write",
        skill=MANUAL_SKILL_NAME,
        artifact="review_markdown",
        path=str(review_output_path),
        chars=len(review),
    )

    state["review_report"] = review
    state["review_output_path"] = str(review_output_path)
    _mark_stage_done(state, "review")
    state["stage"] = "done"

    return _format_reply(
        state,
        "阶段9：审查完成",
        [
            "代码手册已完成审查，审查报告已保存。",
            "",
            f"手册路径：`{state.get('manual_output_path', '')}`",
            f"审查报告路径：`{state.get('review_output_path', '')}`",
            "",
            _review_summary(review),
        ],
    )


def _build_manual_context_evidence_digest(
    manual_context_dir,
    manifest,
    project_context,
    system_topology,
    interface_index,
    flow_index,
    evidence_index,
    validation_report,
    state,
):
    top_module = manifest.get("top_module", state.get("top_module", ""))
    selected_modules = _select_manual_context_modules(
        top_module,
        manifest,
        project_context,
        system_topology,
    )
    module_summaries = []
    for module_name in selected_modules:
        module_payload = _read_manual_context_module(manual_context_dir, module_name)
        if module_payload:
            module_summaries.append(_summarize_manual_context_module(module_payload))

    project_major_modules = project_context.get("major_modules", [])
    flow_samples = flow_index.get("flows", [])
    primary_interfaces = [
        item for item in interface_index.get("interfaces", [])
        if item.get("doc_priority") == "primary"
    ]
    evidence_policy = evidence_index.get("evidence_policy", {})
    source_review_report_path = manual_context_dir / "source_review_report.json"
    source_review_report = _read_json(source_review_report_path) if source_review_report_path.exists() else {}

    return {
        "evidence_mode": PROJECT_EVIDENCE_MODE,
        "manual_kind": "complete_project_code_manual",
        "top_module": top_module,
        "manual_context_dir": str(manual_context_dir),
        "knowledge_dir": str(Path(state.get("knowledge_dir", ""))),
        "counts": manifest.get("counts", {}),
        "doc_focus": manifest.get("doc_focus", {}),
        "validation": {
            "status": validation_report.get("status", "unknown"),
            "issue_count": len(validation_report.get("issues", [])),
            "issues": validation_report.get("issues", [])[:30],
            "checked_file_count": len(validation_report.get("checked_files", [])),
        },
        "project_context": {
            "top_module": project_context.get("top_module", {}),
            "project_purpose": project_context.get("project_purpose", {}),
            "system_summary": project_context.get("system_summary", {}),
            "top_level": project_context.get("top_level", {}),
            "major_modules": project_major_modules[:30],
            "component_families_overview": project_context.get("component_families_overview", [])[:30],
            "system_level_gaps": project_context.get("system_level_gaps", [])[:40],
            "manual_toc_plan": project_context.get("manual_toc_plan", []),
            "source_review_context": project_context.get("source_review_context", {}),
        },
        "known_modules": sorted((manifest.get("files", {}).get("modules") or {}).keys()),
        "system_topology": _summarize_manual_context_topology(system_topology, top_module),
        "interface_index": {
            "counts": interface_index.get("counts", {}),
            "primary_samples": primary_interfaces,
            "all_samples": interface_index.get("interfaces", []),
        },
        "flow_index": {
            "counts": flow_index.get("counts", {}),
            "samples": flow_samples,
            "review_required": [
                item for item in flow_index.get("flows", [])
                if item.get("requires_review")
            ][:60],
        },
        "modules": module_summaries,
        "source_review_report": source_review_report,
        "evidence_policy": evidence_policy,
        "evidence_samples": evidence_index.get("evidence", [])[:80],
        "evidence_boundary": [
            "主证据为 Manual Context；最终手册不要直接把 parser JSON、Knowledge IR、AI Context 或 Semantic Layer 当作主输入。",
            "允许受控读取 RTL 源码作为 source_review_context：只用于端口分组、模块一句话用途和证据缺口复核；不得补写连接、flow、FSM、always 或时序保证。",
            "deterministic_fact 可以直接陈述；derived_fact 必须说明是派生事实。",
            "ai_inferred 必须标注为推断、可能或需要 review，不能写成确定事实。",
            "human_asserted 必须标注为人工断言；evidence_gap 必须写入证据不足或待审查章节。",
            "不得补写 Manual Context 中不存在的连接、接口、flow、FSM、always 行为、寄存器更新条件或时序保证。",
            "drive 是主要事件信号；free 只在影响 drive availability/backpressure 时重点解释。",
        ],
        "manual_generation_policy": {
            "renderer": "manual_context_evidence_bound_markdown",
            "llm_freeform_generation": False,
            "allowed_main_sources": [
                "project_context.json",
                "system_topology.json",
                "interface_index.json",
                "flow_index.json",
                "evidence_index.json",
                "modules/<module>/module_context.json",
                "modules/<module>/module_doc_card.json",
                "modules/<module>/interfaces.json",
                "modules/<module>/flows/<flow_id>.json",
            ],
            "forbidden_promotions": [
                "ai_inferred_to_deterministic_fact",
                "evidence_gap_to_confirmed_behavior",
                "free_signal_to_main_protocol_without_backpressure_evidence",
            ],
            "output_shape": "main_manual_plus_module_pages",
            "module_page_policy": "all reachable modules get a module page; detailed modules are expanded, helper/leaf modules use compact cards",
        },
    }


def _select_manual_context_modules(top_module, manifest, project_context, system_topology):
    selected = []

    def add(name):
        if name and name not in selected:
            selected.append(name)

    add(top_module)
    for page in _module_pages_from_toc(project_context.get("manual_toc_plan", [])):
        add(page.get("module"))
    direct_modules = (
        project_context.get("top_level", {})
        .get("direct_modules", {})
        .get("value", [])
    )
    for module_name in direct_modules:
        add(module_name)
    for item in project_context.get("major_modules", [])[:20]:
        add(item.get("module"))
    for edge in system_topology.get("hierarchy_edges", [])[:80]:
        if edge.get("parent") == top_module:
            add(edge.get("child"))

    known_modules = set((manifest.get("files", {}).get("modules") or {}).keys())
    for name in sorted(known_modules):
        add(name)
    return [name for name in selected if name in known_modules]


def _module_pages_from_toc(toc_plan):
    pages = []
    for item in toc_plan or []:
        if not isinstance(item, dict):
            continue
        if item.get("page_type") == "module":
            pages.append(item)
        for page in item.get("pages", []) or []:
            if isinstance(page, dict) and page.get("page_type") == "module":
                pages.append(page)
    return pages


def _read_manual_context_module(manual_context_dir, module_name):
    module_dir = Path(manual_context_dir) / "modules" / module_name
    module_context_path = module_dir / "module_context.json"
    if not module_context_path.exists():
        return {}
    payload = _read_json(module_context_path)
    payload["_interfaces"] = _read_json(module_dir / "interfaces.json") if (module_dir / "interfaces.json").exists() else {}
    payload["_gaps"] = _read_json(module_dir / "gaps.json") if (module_dir / "gaps.json").exists() else {}
    payload["_doc_card"] = _read_json(module_dir / "module_doc_card.json") if (module_dir / "module_doc_card.json").exists() else {}
    payload["_source_review_report"] = _read_json(module_dir / "source_review_report.json") if (module_dir / "source_review_report.json").exists() else {}
    return payload


def _summarize_manual_context_module(item):
    identity = item.get("module_identity", {})
    position = item.get("system_position", {})
    responsibility = item.get("module_responsibility", {})
    interface_summary = item.get("interface_summary", {})
    gaps_payload = item.get("_gaps", {})
    interfaces_payload = item.get("_interfaces", {})
    doc_card_payload = item.get("_doc_card") or item.get("module_doc_card", {})
    source_review_report = item.get("_source_review_report") or item.get("source_review_report", {})
    source_review_claims = (
        item.get("source_review_claims")
        or doc_card_payload.get("source_review_claims")
        or source_review_report.get("claims", [])
    )
    components = item.get("internal_components", [])
    assignments = item.get("assignment_impact_summary", [])

    return {
        "module_name": identity.get("module_name", ""),
        "module_role": identity.get("module_role", ""),
        "source_files": identity.get("source_files", []),
        "doc_card": doc_card_payload,
        "page_policy": doc_card_payload.get("page_policy", {}),
        "port_summary": doc_card_payload.get("port_summary", {}),
        "source_review_context": doc_card_payload.get("source_review_context", item.get("source_review_context", {})),
        "source_review_claims": source_review_claims,
        "source_review_report": source_review_report or doc_card_payload.get("source_review_report", {}),
        "identity_certainty": identity.get("certainty", ""),
        "system_position": {
            "parents": _claim_value(position.get("parents")),
            "children": _claim_value(position.get("children")),
            "component_children": _claim_value(position.get("component_children")),
            "region": position.get("region", {}),
        },
        "responsibility": {
            "short_summary": responsibility.get("short_summary", {}),
            "review_status": responsibility.get("review_status", ""),
            "documentation_focus": responsibility.get("documentation_focus", [])[:5],
            "responsibility_claims": responsibility.get("responsibility_claims", [])[:5],
        },
        "interfaces": {
            "counts": interface_summary.get("counts", {}),
            "primary_interfaces": interface_summary.get("primary_interfaces", [])[:20],
            "event_inputs": interface_summary.get("event_inputs", [])[:20],
            "event_outputs": interface_summary.get("event_outputs", [])[:20],
            "free_backpressure_note": interface_summary.get("free_backpressure_note", {}),
            "interface_groups": interfaces_payload.get("interfaces", [])[:12],
        },
        "key_drive_flows": item.get("key_drive_flows", [])[:12],
        "internal_components": {
            "count": len(components),
            "by_family": _count_by(components, "component_family"),
            "primary_samples": [
                component for component in components
                if component.get("doc_priority") == "primary"
            ][:20],
        },
        "assignment_impact_summary": {
            "count": len(assignments),
            "primary_samples": [
                assignment for assignment in assignments
                if assignment.get("doc_priority") == "primary"
            ][:15],
        },
        "evidence_gaps": item.get("evidence_gaps", [])[:20],
        "gap_file": gaps_payload,
        "review_questions": item.get("review_questions", [])[:20],
        "manual_sections": item.get("manual_sections", []),
        "source_context_refs": item.get("source_context_refs", {}),
    }


def _summarize_manual_context_topology(system_topology, top_module):
    edges = system_topology.get("hierarchy_edges", [])
    direct_edges = [edge for edge in edges if edge.get("parent") == top_module]
    return {
        "module_count": system_topology.get("module_count", 0),
        "direct_edges": direct_edges,
        "edges": edges,
        "edge_samples": edges,
        "module_neighbors": system_topology.get("module_neighbors", {}),
    }


def _claim_value(value):
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _count_by(items, key):
    counts = {}
    for item in items:
        value = item.get(key) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def _format_digest(digest):
    counts = digest.get("counts", {})
    project_context = digest.get("project_context", {})
    top_level = project_context.get("top_level", {})
    direct_modules = (
        top_level.get("direct_modules", {})
        .get("value", [])
        if isinstance(top_level.get("direct_modules"), dict)
        else []
    )
    flow_counts = digest.get("flow_index", {}).get("counts", {})
    interface_counts = digest.get("interface_index", {}).get("counts", {})
    validation = digest.get("validation", {})

    lines = [
        "## 证据摘要",
        f"- 主证据模式：`{digest.get('evidence_mode', PROJECT_EVIDENCE_MODE)}` / `{digest.get('manual_kind', '')}`",
        f"- top_module：`{digest.get('top_module', '')}`",
        f"- Manual Context 目录：`{digest.get('manual_context_dir', '')}`",
        f"- 对象数量：{json.dumps(counts, ensure_ascii=False)}",
        f"- 一级模块：{', '.join(direct_modules) or '证据未提供'}",
        f"- 接口索引：{json.dumps(interface_counts, ensure_ascii=False)}",
        f"- Flow 索引：{json.dumps(flow_counts, ensure_ascii=False)}",
        f"- Validation：`{validation.get('status', 'unknown')}` / issues={validation.get('issue_count', 0)}",
    ]
    if digest.get("modules"):
        lines.append(f"- 已加载模块页面上下文：{len(digest.get('modules', []))} 个")
    gaps = []
    for module in digest.get("modules", []):
        for gap in module.get("evidence_gaps", [])[:2]:
            reason = gap.get("reason", "") if isinstance(gap, dict) else str(gap)
            if reason:
                gaps.append(f"{module.get('module_name', '')}: {reason}")
    if gaps:
        lines.append("- 代表性证据缺口：" + "；".join(gaps[:5]))
    return "\n".join(lines)


def _build_outline(digest):
    if digest.get("evidence_mode") == PROJECT_EVIDENCE_MODE:
        top_module = digest.get("top_module", "top_module")
        return [
            {"title": "项目总览", "evidence": ["project_context.project_purpose", "project_context.top_level.source_file"]},
            {"title": f"顶层模块 {top_module}", "evidence": ["project_context.top_level", f"modules.{top_module}.module_doc_card"]},
            {"title": "完整模块层级结构", "evidence": ["system_topology.hierarchy_edges"]},
            {"title": "子系统与模块索引", "evidence": ["project_context.manual_toc_plan", "modules.module_doc_card"]},
        ]

    sections = digest.get("sections", [])
    outline = []

    if sections:
        for section in sections:
            title = section.get("title") or section.get("section_id") or "未命名章节"
            outline.append({
                "title": title,
                "evidence": section.get("covers", []),
            })
        outline.append({
            "title": "证据边界与风险点",
            "evidence": ["manual_context.evidence_boundary", "validation"],
        })
        return outline

    top_module = digest.get("top_module", "top_module")
    return [
        {"title": f"{top_module} 项目概述", "evidence": ["system_view"]},
        {"title": "顶层模块与一级子模块", "evidence": ["system_view.primary_modules"]},
        {"title": "关键组件家族", "evidence": ["system_view.families_used"]},
        {"title": "阅读路径建议", "evidence": ["reading_path"]},
        {"title": "证据边界与风险点", "evidence": ["evidence_boundary", "global_risks"]},
    ]


def _generate_manual_markdown(state, client, model):
    return _render_manual_context_markdown(state)


def _render_manual_context_markdown(state):
    digest = state.get("evidence_digest") or {}
    top_module = digest.get("top_module") or state.get("top_module", "")
    module_dir_name = f"{state.get('_manual_output_stem') or (top_module + '_generated')}_modules"
    project_context = digest.get("project_context", {})
    top_level = project_context.get("top_level", {})
    purpose = _preferred_project_purpose_claim(digest)
    source_file = top_level.get("source_file", "")
    direct_modules = _claim_value(top_level.get("direct_modules")) or []
    rtl_root = _rtl_root_from_source(source_file)
    topology = digest.get("system_topology", {})

    lines = [
        f"# {top_module} RTL 代码手册",
        "",
        "本手册采用“主手册 + 模块页”的结构，主手册用于快速定位系统结构，模块页用于查看具体接口和 flow 细节。",
        "",
        "## 1. 项目总览",
        "",
        f"- 项目用途：{_claim_brief(purpose, limit=180)}",
        f"- RTL 目录：`{rtl_root}`。",
        f"- 顶层文件：`{source_file or 'Manual Context 未提供'}`。",
        "",
        f"## 2. 顶层模块 `{top_module}`",
        "",
        f"- 顶层直接实例化模块：{_code_list(direct_modules)}。",
    ]
    lines.extend(_render_top_external_port_groups(top_level.get("external_port_groups", [])))
    lines.extend(_render_top_child_module_summary(digest, direct_modules, module_dir_name))
    lines.extend(_render_top_structure_diagram(digest, top_module))
    lines.extend(_render_complete_hierarchy_section(topology))
    lines.extend(_render_module_index_section(digest, module_dir_name))
    return "\n".join(lines).strip()


def _render_top_external_port_groups(groups):
    lines = [
        "",
        "### 2.1 外部端口分组",
        "",
        "端口分组按 pad/信号命名和方向归类，用于快速识别顶层对外边界。",
        "",
        "| 端口组 | 方向统计 | 代表信号 |",
        "| --- | --- | --- |",
    ]
    if not groups:
        lines.append("| - | - | Manual Context 未提供顶层外部端口分组 |")
        return lines
    for group in groups:
        signals = [item.get("name", "") for item in group.get("signals", [])]
        direction_counts = group.get("direction_counts", {})
        direction_text = ", ".join(f"{key}:{value}" for key, value in sorted(direction_counts.items())) or "未记录"
        lines.append(
            "| "
            + " | ".join([
                _md_cell(_code(group.get("group"))),
                _md_cell(direction_text),
                _md_cell(_code_list(_clip_list(signals, 8))),
            ])
            + " |"
        )
    return lines


def _render_top_child_module_summary(digest, direct_modules, module_dir_name):
    lines = [
        "",
        "### 2.2 顶层组成",
        "",
        "| 子模块 | 职责 | 接收 | 输出 | 模块页 |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not direct_modules:
        lines.append("| - | 证据不足：Manual Context 未提供顶层子模块 | - | - | - |")
        return lines
    for module_name in direct_modules:
        module = _module_summary_by_name(digest, module_name)
        summary = _preferred_module_summary_claim(module) if module else {}
        port_summary = module.get("port_summary", {}) if module else {}
        lines.append(
            "| "
            + " | ".join([
                _md_cell(_code(module_name)),
                _md_cell(_claim_brief(summary)),
                _md_cell(_natural_port_side(port_summary, "input")),
                _md_cell(_natural_port_side(port_summary, "output")),
                _md_cell(f"[打开]({module_dir_name}/{safe_filename(module_name)}.md)"),
            ])
            + " |"
        )
    return lines


def _render_top_structure_diagram(digest, top_module):
    topology = digest.get("system_topology", {})
    edges = topology.get("edges") or topology.get("edge_samples", [])
    diagram = _build_hierarchy_diagram(top_module, edges, max_depth=2, max_edges=40)
    lines = [
        "",
        "### 2.3 顶层结构图",
        "",
    ]
    if not diagram["edges"]:
        lines.append("Manual Context 未提供可绘制的顶层层级边。")
        return lines
    lines.extend([
        "下图只展示顶层向下的有限层级，完整父子关系见后续层级表。",
        "",
        "```mermaid",
        "flowchart TB",
        *diagram["mermaid"],
        "```",
        "",
        "```text",
        *diagram["ascii"],
        "```",
    ])
    if diagram.get("truncated"):
        lines.append(f"- 图中已截断，未展开 {diagram['truncated']} 条后续层级边。")
    return lines


def _build_hierarchy_diagram(root, edges, max_depth=2, max_edges=40):
    children_by_parent = {}
    for edge in edges or []:
        if not isinstance(edge, dict):
            continue
        parent = str(edge.get("parent", "") or "")
        child = str(edge.get("child", "") or "")
        if not parent or not child:
            continue
        children = children_by_parent.setdefault(parent, [])
        if child not in children:
            children.append(child)

    selected_edges = []
    truncated = 0
    queue = [(root, 0)]
    visited = set()
    while queue and len(selected_edges) < max_edges:
        parent, depth = queue.pop(0)
        key = (parent, depth)
        if key in visited:
            continue
        visited.add(key)
        children = children_by_parent.get(parent, [])
        if depth >= max_depth:
            truncated += len(children)
            continue
        remaining = max_edges - len(selected_edges)
        for child in children[:remaining]:
            selected_edges.append({"parent": parent, "child": child})
            queue.append((child, depth + 1))
        if len(children) > remaining:
            truncated += len(children) - remaining

    selected_children = {}
    for edge in selected_edges:
        selected_children.setdefault(edge["parent"], []).append(edge["child"])

    return {
        "edges": selected_edges,
        "mermaid": [_mermaid_edge(edge["parent"], edge["child"]) for edge in selected_edges],
        "ascii": _ascii_tree(root, selected_children),
        "truncated": truncated,
    }


def _ascii_tree(root, children_by_parent):
    lines = [str(root or "root")]

    def add_children(parent, prefix=""):
        children = children_by_parent.get(parent, [])
        for index, child in enumerate(children):
            is_last = index == len(children) - 1
            connector = "`-- " if is_last else "|-- "
            lines.append(f"{prefix}{connector}{child}")
            add_children(child, prefix + ("    " if is_last else "|   "))

    add_children(root)
    return lines


def _dedupe_diagram_nodes(nodes):
    result = []
    seen = set()
    for item in nodes:
        name = str(item.get("name", "") or "")
        label = str(item.get("label", "") or name)
        if not name and not label:
            continue
        key = (name, label)
        if key in seen:
            continue
        seen.add(key)
        result.append({**item, "name": name, "label": label})
    return result


def _mermaid_edge(parent, child, edge_label=""):
    left = _mermaid_node(parent)
    right = _mermaid_node(child)
    label = _mermaid_label(edge_label)
    if label:
        return f"  {left} -->|{label}| {right}"
    return f"  {left} --> {right}"


def _mermaid_node(label):
    return f'{_mermaid_id(label)}["{_mermaid_label(label)}"]'


def _mermaid_id(label):
    safe = safe_filename(label)
    safe = re.sub(r"[^A-Za-z0-9_]", "_", safe)
    if not safe or safe[0].isdigit():
        safe = "n_" + safe
    return safe


def _mermaid_label(label):
    return _plain(label).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("|", "/")


def _render_complete_hierarchy_section(topology):
    edges = topology.get("edges") or topology.get("edge_samples", [])
    lines = [
        "",
        "## 3. 完整模块层级结构",
        "",
        f"- 模块数：{topology.get('module_count', 0)}。",
        f"- 层级边数：{len(edges)}。",
        "",
        "| Parent | Child | Relationship |",
        "| --- | --- | --- |",
    ]
    if not edges:
        lines.append("| - | - | Manual Context 未提供 hierarchy_edges |")
        return lines
    for edge in edges:
        lines.append(_hierarchy_row(edge))
    return lines


def _render_module_index_section(digest, module_dir_name):
    modules = digest.get("modules", [])
    lines = [
        "",
        "## 4. 子系统与模块索引",
        "",
        "每个 reachable module 都有独立模块页；关键模块详写，helper/leaf 模块使用压缩卡片。",
        "",
        "| 模块 | 区域 | 职责摘要 | 模块页 |",
        "| --- | --- | --- | --- |",
    ]
    for module in sorted(modules, key=lambda item: (_module_region(item), item.get("module_name", ""))):
        module_name = module.get("module_name", "")
        summary = _preferred_module_summary_claim(module)
        lines.append(
            "| "
            + " | ".join([
                _md_cell(_code(module_name)),
                _md_cell(_module_region(module)),
                _md_cell(_claim_brief(summary, limit=96)),
                _md_cell(f"[打开]({module_dir_name}/{safe_filename(module_name)}.md)"),
            ])
            + " |"
        )
    if not modules:
        lines.append("| - | - | 未加载模块上下文 | - |")
    return lines


def _render_cross_module_flow_section(digest):
    flows = digest.get("flow_index", {}).get("samples", [])
    lines = [
        "",
        "## 5. 关键 Drive-centered Flow 索引",
        "",
        "这里保留跨模块阅读入口；完整 flow 细节进入对应模块页。",
        "",
        "| 模块 | Trigger | 标题 | Payload | Review | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not flows:
        lines.append("| - | - | - | - | evidence_gap | - |")
        return lines
    for flow in flows[:80]:
        lines.append(
            "| "
            + " | ".join([
                _md_cell(_code(flow.get("module"))),
                _md_cell(_code(flow.get("trigger_event"))),
                _md_cell(flow.get("title", "")),
                _md_cell(_code_list(_clip_list(flow.get("payloads", []), 4))),
                _md_cell("需要 review" if flow.get("requires_review") else "ready"),
                _md_cell(_refs_text(flow)),
            ])
            + " |"
        )
    if len(flows) > 80:
        lines.append(f"| ... | ... | 其余 {len(flows) - 80} 条 flow 见对应模块页 | ... | ... | ... |")
    return lines


def _render_global_gaps_section(digest):
    grouped = _collect_grouped_gaps(digest)
    lines = [
        "",
        "## 6. 证据缺口与 Review 问题",
        "",
        "本节把底层 gap 翻译成可人工 review 的问题；逐模块细节见模块页。",
        "",
        "| 范围 | Review 问题 | Evidence |",
        "| --- | --- | --- |",
    ]
    if not grouped:
        lines.append("| 全局 | 当前已加载 Manual Context 未提供 evidence_gap | - |")
        return lines
    for item in grouped[:60]:
        lines.append(
            "| "
            + " | ".join([
                _md_cell(item.get("scope", "")),
                _md_cell(item.get("question", "")),
                _md_cell(item.get("evidence", "")),
            ])
            + " |"
        )
    if len(grouped) > 60:
        lines.append(f"| ... | 其余 {len(grouped) - 60} 个 review 项进入对应模块页 | ... |")
    return lines


def _rtl_root_from_source(source_file):
    source_file = str(source_file or "").replace("\\", "/")
    if source_file.startswith("rtl/rtl/"):
        return "rtl/rtl"
    if "/rtl/rtl/" in source_file:
        return source_file.split("/rtl/rtl/", 1)[0] + "/rtl/rtl"
    parts = source_file.split("/")
    if len(parts) > 1:
        return "/".join(parts[:-1])
    return "rtl/rtl"


def _one_sentence(text):
    text = _plain(text)
    for sep in ("。", ". "):
        if sep in text:
            first = text.split(sep, 1)[0].strip()
            if first:
                return first + ("。" if sep == "。" else ".")
    return text


def _clip_list(values, limit):
    values = [value for value in (values or []) if value]
    if len(values) <= limit:
        return values
    return values[:limit] + [f"... +{len(values) - limit}"]


def _claim_brief(claim, limit=120):
    if not isinstance(claim, dict) or not claim.get("value"):
        return "证据不足：Manual Context 未提供职责摘要"
    return f"{_claim_label(claim)}：{_shorten(_one_sentence(claim.get('value', '')), limit)}"


def _preferred_project_purpose_claim(digest):
    top_module = digest.get("top_module", "")
    top_summary = _module_summary_by_name(digest, top_module)
    if top_summary:
        source_claim = _preferred_source_review_claim(top_summary)
        if source_claim:
            return source_claim
    return (
        digest.get("project_context", {}).get("project_purpose")
        or digest.get("project_context", {}).get("system_summary")
        or {"value": f"{top_module} 是该 RTL 项目的顶层模块。", "certainty": "derived_fact"}
    )


def _preferred_module_summary_claim(module):
    source_claim = _preferred_source_review_claim(module)
    if source_claim:
        return source_claim
    return module.get("responsibility", {}).get("short_summary", {})


def _preferred_source_review_claim(module):
    first_claim = {}
    for claim in module.get("source_review_claims", []) or []:
        if not isinstance(claim, dict):
            continue
        if claim.get("certainty") != "ai_inferred":
            continue
        summary = claim.get("summary") or claim.get("value")
        if not summary:
            continue
        if not first_claim:
            first_claim = {
                "value": summary,
                "explanation": claim.get("explanation", ""),
                "certainty": "ai_inferred",
                "source_layers": claim.get("source_layers", []),
                "source_refs": claim.get("source_refs", []),
            }
        subject = (claim.get("subject") or "").lower()
        if any(token in subject for token in ("responsibility", "module", "role", "purpose", "source_review", "职责", "用途", "角色")):
            return {
                "value": summary,
                "explanation": claim.get("explanation", ""),
                "certainty": "ai_inferred",
                "source_layers": claim.get("source_layers", []),
                "source_refs": claim.get("source_refs", []),
            }
    return first_claim


def _natural_port_side(port_summary, direction):
    if not port_summary:
        return "未记录"
    if direction == "input":
        items = []
        items.extend(_signals_from_port_summary(port_summary, "event_inputs", "drive 输入"))
        items.extend(_signals_from_port_summary(port_summary, "data_inputs", "数据输入"))
        items.extend(_signals_from_port_summary(port_summary, "control_inputs", "控制输入"))
        items.extend(_signals_from_port_summary(port_summary, "free_inputs", "free 输入"))
        items.extend(_signals_from_port_summary(port_summary, "unknown_inputs", "其他输入"))
    else:
        items = []
        items.extend(_signals_from_port_summary(port_summary, "event_outputs", "drive 输出"))
        items.extend(_signals_from_port_summary(port_summary, "data_outputs", "数据输出"))
        items.extend(_signals_from_port_summary(port_summary, "control_outputs", "控制输出"))
        items.extend(_signals_from_port_summary(port_summary, "free_outputs", "free 输出"))
        items.extend(_signals_from_port_summary(port_summary, "unknown_outputs", "其他输出"))
        items.extend(_signals_from_port_summary(port_summary, "inout_ports", "双向端口"))
    return "；".join(items[:5]) if items else "未记录"


def _signals_from_port_summary(port_summary, key, label):
    signals = port_summary.get(key, []) if isinstance(port_summary, dict) else []
    names = [item.get("name", "") for item in signals if isinstance(item, dict) and item.get("name")]
    if not names:
        return []
    return [f"{label}：{_code_list(_clip_list(names, 4))}"]


def _module_region(module):
    region = (module.get("system_position", {}).get("region") or {}).get("value", "")
    if not region:
        region = (module.get("doc_card", {}).get("hierarchy", {}).get("region") or {}).get("value", "")
    return region or "other"


def _collect_grouped_gaps(digest):
    rows = []

    def add(scope, gap):
        if not isinstance(gap, dict):
            gap = {"reason": str(gap), "certainty": "evidence_gap"}
        question = _gap_review_question(gap)
        key = (scope, question)
        if key in {(item.get("scope"), item.get("question")) for item in rows}:
            return
        rows.append({
            "scope": scope,
            "question": question,
            "evidence": _refs_text(gap),
        })

    for gap in digest.get("project_context", {}).get("system_level_gaps", []):
        add("全局", gap)
    for module in digest.get("modules", []):
        scope = module.get("module_name", "")
        for gap in module.get("evidence_gaps", []):
            add(scope, gap)
        for gap in module.get("gap_file", {}).get("gaps", []):
            add(scope, gap)
        for question in module.get("review_questions", []):
            if isinstance(question, dict):
                add(scope, {
                    "field": question.get("subject", ""),
                    "reason": question.get("question", ""),
                    "certainty": "evidence_gap",
                    "evidence_refs": question.get("evidence_refs", []),
                })
    return rows


def _gap_review_question(gap):
    field = _plain(gap.get("field", ""))
    reason = _plain(gap.get("reason", ""))
    if field and reason:
        return f"请人工确认 `{field}`：{reason}"
    if reason:
        return f"请人工确认：{reason}"
    if field:
        return f"请人工确认 `{field}` 的证据是否充分。"
    return "请人工确认该项证据是否充分。"


def _render_project_overview_section(digest):
    project_context = digest.get("project_context", {})
    top_level = project_context.get("top_level", {})
    top_module_claim = project_context.get("top_module", {})
    top_module = top_module_claim.get("value") or digest.get("top_module", "")
    source_file = top_level.get("source_file", "")
    direct_modules = _claim_value(top_level.get("direct_modules")) or []
    counts = digest.get("counts", {})
    validation = digest.get("validation", {})
    doc_focus = digest.get("doc_focus", {})
    system_summary = project_context.get("system_summary", {})

    lines = [
        "## 1. 项目总览",
        "",
        "### 1.1 Manual Context 范围",
        "",
        f"- 确定性事实：`top_module` 为 `{top_module}`；源文件为 `{source_file or 'Manual Context 未提供'}`；证据：{_refs_text(top_module_claim or top_level.get('direct_modules', {}))}。",
        f"- 确定性事实：顶层直接实例化模块为 {_code_list(direct_modules)}；证据：{_refs_text(top_level.get('direct_modules', {}))}。",
        f"- Manual Context 对象数量：modules={counts.get('modules', 0)}，interfaces={counts.get('interfaces', 0)}，flows={counts.get('flows', 0)}，evidence_entries={counts.get('evidence_entries', 0)}，validation_issues={counts.get('validation_issues', 0)}。",
        f"- Validation：`{validation.get('status', 'unknown')}` / issues={validation.get('issue_count', 0)} / checked_files={validation.get('checked_file_count', 0)}。",
        "",
        "### 1.2 文档焦点",
        "",
        f"- 派生事实：主要事件信号为 `{doc_focus.get('primary_event', 'drive')}`；次要事件记录为 {_code_list(doc_focus.get('secondary_events', []))}。",
        f"- 派生事实：主要写作主题为 {_code_list(doc_focus.get('primary_topics', []))}。",
        "- 写作策略：`free` 信号只作为 backpressure/drive availability 相关参考出现，不作为主流程解释入口。",
    ]
    if system_summary.get("value"):
        lines.extend([
            "",
            "### 1.3 系统语义摘要",
            "",
            f"- {_claim_label(system_summary)}：{_plain(system_summary.get('value'))}",
            f"  - 说明：{_plain(system_summary.get('explanation') or 'Manual Context 未提供进一步说明。')}",
            f"  - 证据：{_refs_text(system_summary)}",
        ])
    lines.append("")
    return lines


def _render_top_module_section(digest, top_module):
    module = _module_summary_by_name(digest, top_module)
    project_context = digest.get("project_context", {})
    top_level = project_context.get("top_level", {})
    direct_modules = _claim_value(top_level.get("direct_modules")) or []
    lines = [
        f"## 2. 顶层模块 `{top_module}`",
        "",
        "### 2.1 结构边界",
        "",
        f"- 确定性事实：`{top_module}` 的直接子模块为 {_code_list(direct_modules)}。",
    ]
    if module:
        position = module.get("system_position", {})
        children = position.get("children") or []
        component_children = position.get("component_children") or []
        interfaces = module.get("interfaces", {})
        interface_counts = _claim_value(interfaces.get("counts")) or {}
        lines.extend([
            f"- 确定性事实：module_context 中记录的 children 为 {_code_list(children)}。",
            f"- 确定性事实：component_children 为 {_code_list(component_children) if component_children else '无'}。",
            f"- 确定性事实：接口计数为 `{json.dumps(interface_counts, ensure_ascii=False)}`。",
        ])
        summary = module.get("responsibility", {}).get("short_summary", {})
        if summary.get("value"):
            lines.extend([
                "",
                "### 2.2 语义职责",
                "",
                f"- {_claim_label(summary)}：{_plain(summary.get('value'))}",
                f"  - review_status：`{summary.get('review_status', 'unknown')}`；证据：{_refs_text(summary)}。",
            ])
        primary_components = module.get("internal_components", {}).get("primary_samples", [])
        lines.extend([
            "",
            "### 2.3 关键实例",
            "",
            "下表来自 `module_context.internal_components` 的 primary 样本；它不是直接子模块完整清单，完整清单以上方 children 为准。",
            "",
            "| 实例 | 模块类型 | 输入事件 | 输出事件 | 证据 |",
            "| --- | --- | --- | --- | --- |",
        ])
        if primary_components:
            for component in primary_components:
                lines.append(
                    "| "
                    + " | ".join([
                        _md_cell(_code(component.get("instance_name"))),
                        _md_cell(_code(component.get("module_type"))),
                        _md_cell(_code_list(component.get("input_events", []))),
                        _md_cell(_code_list(component.get("output_events", []))),
                        _md_cell(_refs_text(component)),
                    ])
                    + " |"
                )
        else:
            lines.append("| - | - | - | - | Manual Context 未提供 primary key instance |")
    else:
        lines.append("- 证据缺口：当前证据摘要未加载顶层 module_context。")
    lines.append("")
    return lines


def _render_hierarchy_section(digest):
    topology = digest.get("system_topology", {})
    direct_edges = topology.get("direct_edges", [])
    edge_samples = topology.get("edge_samples", [])
    lines = [
        "## 3. 模块层级结构",
        "",
        f"- 确定性事实：system_topology 记录 module_count={topology.get('module_count', 0)}。",
        "",
        "### 3.1 顶层直接层级",
        "",
        "| Parent | Child | Relationship | Certainty | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    if direct_edges:
        for edge in direct_edges:
            lines.append(_hierarchy_row(edge))
    else:
        lines.append("| - | - | - | evidence_gap | Manual Context 未提供顶层直接边 |")
    lines.extend([
        "",
        "### 3.2 层级样本",
        "",
        "| Parent | Child | Relationship | Certainty | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ])
    for edge in edge_samples[:30]:
        lines.append(_hierarchy_row(edge))
    if not edge_samples:
        lines.append("| - | - | - | evidence_gap | Manual Context 未提供 hierarchy_edges |")
    lines.append("")
    return lines


def _hierarchy_row(edge):
    return (
        "| "
        + " | ".join([
            _md_cell(_code(edge.get("parent"))),
            _md_cell(_code(edge.get("child"))),
            _md_cell(edge.get("relationship", "")),
        ])
        + " |"
    )


def _render_responsibility_section(digest):
    major_modules = digest.get("project_context", {}).get("major_modules", [])
    modules = digest.get("modules", [])
    lines = [
        "## 4. 关键模块职责",
        "",
        "### 4.1 主要模块摘要",
        "",
        "以下摘要来自 `project_context.major_modules`。凡 `certainty=ai_inferred` 的内容均按 AI 推断写入，不升级为确定性事实。",
        "",
        "| 模块 | 区域 | 重要性 | Certainty | 摘要 | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in major_modules[:15]:
        lines.append(
            "| "
            + " | ".join([
                _md_cell(_code(item.get("module"))),
                _md_cell(item.get("region", "")),
                _md_cell(item.get("importance_score", "")),
                _md_cell(_certainty_label(item.get("certainty", ""))),
                _md_cell(_plain(item.get("summary", ""))),
                _md_cell(_refs_text(item)),
            ])
            + " |"
        )
    if not major_modules:
        lines.append("| - | - | - | evidence_gap | Manual Context 未提供 major_modules | - |")

    lines.extend([
        "",
        "### 4.2 已加载模块页面职责",
        "",
        "| 模块 | 职责 claim | Review | Evidence |",
        "| --- | --- | --- | --- |",
    ])
    for module in modules[:20]:
        summary = module.get("responsibility", {}).get("short_summary", {})
        value = summary.get("value") or "Manual Context 未提供职责摘要。"
        lines.append(
            "| "
            + " | ".join([
                _md_cell(_code(module.get("module_name"))),
                _md_cell(f"{_claim_label(summary)}：{_plain(value)}"),
                _md_cell(summary.get("review_status", module.get("responsibility", {}).get("review_status", ""))),
                _md_cell(_refs_text(summary)),
            ])
            + " |"
        )
    lines.append("")
    return lines


def _render_interfaces_section(digest):
    counts = digest.get("interface_index", {}).get("counts", {})
    rows = _collect_interface_rows(digest, limit=24)
    lines = [
        "## 5. 接口与数据事件契约",
        "",
        f"- 确定性事实：interface_index 记录 `{json.dumps(counts, ensure_ascii=False)}`。",
        "- 表格只记录 primary event interface 的事件、payload 和 companion free 名称；不推断 free 的生成逻辑。",
        "",
        "| 模块 | Interface | 方向 | Event | Payload | Free/backpressure 记录 | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if rows:
        for row in rows:
            lines.append(
                "| "
                + " | ".join([
                    _md_cell(_code(row["module"])),
                    _md_cell(_code(row["interface"])),
                    _md_cell(row["direction"]),
                    _md_cell(_code(row["event"])),
                    _md_cell(row["payloads"]),
                    _md_cell(row["free_note"]),
                    _md_cell(row["evidence"]),
                ])
                + " |"
            )
    else:
        lines.append("| - | - | - | - | - | evidence_gap：未加载 primary interface 细节 | - |")
    lines.extend([
        "",
        "接口写作边界：payload/event binding 若为 `deterministic_fact` 可以陈述；`manual_description` 若来自 Semantic Layer，必须按 AI 推断处理；`free` 仅在影响 drive availability/backpressure 时解释。",
        "",
    ])
    return lines


def _render_flows_section(digest):
    flow_counts = digest.get("flow_index", {}).get("counts", {})
    flows = _collect_flow_contexts(digest, limit=10)
    lines = [
        "## 6. Drive-centered Flow",
        "",
        f"- 确定性事实：flow_index 记录 `{json.dumps(flow_counts, ensure_ascii=False)}`。",
        "- 每个 flow 先列 Knowledge IR 可证明的 trigger、payload、path/effect，再列 AI 语义 claim 和 evidence_gap。",
        "",
    ]
    if not flows:
        lines.extend(["证据缺口：当前 Manual Context 摘要未提供可读取的 flow context。", ""])
        return lines

    for index, flow in enumerate(flows, start=1):
        trigger = flow.get("trigger_event", {})
        payloads = _format_payloads(flow.get("payloads", []))
        path_steps = flow.get("ordered_path", [])
        component_steps = [step for step in path_steps if step.get("kind") == "component"]
        effects = flow.get("outputs_or_effects", [])
        behavior = flow.get("branch_merge_behavior", {})
        semantic = flow.get("semantic_meaning", {})
        gaps = flow.get("gaps", [])
        lines.extend([
            f"### 6.{index} `{flow.get('module', '')}.{trigger.get('signal', '')}`",
            "",
            f"- 确定性事实：flow_id=`{flow.get('flow_id', '')}`；title=`{flow.get('title', '')}`；manual_importance=`{flow.get('manual_importance', '')}`。",
            f"- 确定性事实：trigger_event=`{trigger.get('signal', '')}`；证据：{_refs_text(trigger)}。",
            f"- 确定性事实：payload binding：{payloads or '当前 flow context 未记录 payload'}。",
            f"- 确定性事实：ordered_path step_count={len(path_steps)}，component_step_count={len(component_steps)}；前序组件：{_format_component_steps(component_steps[:8])}。",
        ])
        if behavior:
            lines.append(
                f"- 确定性事实：branch_points={len(behavior.get('branch_points', []))}，join_points={len(behavior.get('join_points', []))}，blocking_points={len(behavior.get('blocking_points', []))}。"
            )
        effect_text = _format_effects(effects)
        if effect_text:
            lines.append(effect_text)
        if semantic.get("value"):
            lines.extend([
                f"- {_claim_label(semantic)}：{_plain(semantic.get('value'))}",
                f"  - review_status：`{semantic.get('review_status', 'unknown')}`；requires_rtl_source_review=`{semantic.get('requires_rtl_source_review', False)}`；证据：{_refs_text(semantic)}。",
            ])
        if gaps:
            lines.append("- 证据缺口：")
            for gap in gaps[:5]:
                lines.append(f"  - {_gap_text(gap)}")
        lines.append("")
    return lines


def _render_components_assignments_section(digest):
    families = digest.get("project_context", {}).get("component_families_overview", [])
    assignment_rows = _collect_assignment_rows(digest, limit=18)
    lines = [
        "## 7. 内部组件与 Assign 影响",
        "",
        "### 7.1 组件 family 概览",
        "",
        "下表只陈述 Manual Context 记录到的 family 名称和实例数量，不额外解释 family 的 RTL 行为语义。",
        "",
        "| Component family | Instance count |",
        "| --- | --- |",
    ]
    if families:
        for item in families:
            lines.append(f"| {_md_cell(_code(item.get('family')))} | {_md_cell(item.get('instance_count', 0))} |")
    else:
        lines.append("| - | evidence_gap：Manual Context 未提供 component_families_overview |")

    lines.extend([
        "",
        "### 7.2 Assign 影响样本",
        "",
        "assign 的 lhs/rhs 来自确定性解析事实；解释字段只有在 Semantic Layer 提供 claim 时才写成 AI 推断，否则写为证据缺口。",
        "",
        "| 模块 | Assign | Impact area | LHS | RHS 摘要 | 解释状态 | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ])
    if assignment_rows:
        for row in assignment_rows:
            lines.append(
                "| "
                + " | ".join([
                    _md_cell(_code(row["module"])),
                    _md_cell(_code(row["assignment_id"])),
                    _md_cell(row["impact_area"]),
                    _md_cell(_code(row["lhs"])),
                    _md_cell(_shorten(row["rhs"], 96)),
                    _md_cell(row["interpretation"]),
                    _md_cell(row["evidence"]),
                ])
                + " |"
            )
    else:
        lines.append("| - | - | - | - | - | evidence_gap：未加载 assign 样本 | - |")
    lines.append("")
    return lines


def _render_gaps_section(digest):
    validation = digest.get("validation", {})
    gaps = _collect_gap_rows(digest, limit=30)
    questions = _collect_review_questions(digest, limit=20)
    lines = [
        "## 8. 证据缺口与 Review 问题",
        "",
        f"- Validation：`{validation.get('status', 'unknown')}` / issues={validation.get('issue_count', 0)}。",
    ]
    if validation.get("issues"):
        lines.append("- Validation issues：")
        for issue in validation.get("issues", [])[:10]:
            lines.append(f"  - `{issue}`")
    else:
        lines.append("- Validation issues：0。")
    lines.extend(["", "### 8.1 Evidence gaps", ""])
    if gaps:
        for gap in gaps:
            lines.append(f"- {_gap_text(gap)}")
    else:
        lines.append("- 当前已加载 Manual Context 摘要未提供 evidence_gap。")
    lines.extend(["", "### 8.2 Review questions", ""])
    if questions:
        for question in questions:
            lines.append(f"- {_plain(question.get('question', ''))}（subject=`{question.get('subject', '')}`；evidence={_refs_text(question)}）")
    else:
        lines.append("- 当前已加载 Manual Context 摘要未提供 review_questions。")
    lines.append("")
    return lines


def _render_evidence_boundary_section(digest):
    lines = [
        "## 7. 证据边界与写作规则",
        "",
    ]
    for item in digest.get("evidence_boundary", []):
        lines.append(f"- {item}")
    policy = digest.get("manual_generation_policy", {})
    if policy:
        lines.extend([
            "",
            f"- 手册生成策略：`{policy.get('renderer', '')}`；llm_freeform_generation=`{policy.get('llm_freeform_generation')}`。",
            f"- 主输入入口：{_code_list(policy.get('allowed_main_sources', []))}。",
        ])
    lines.append("")
    return lines


def _write_module_pages(state, output_path):
    digest = state.get("evidence_digest") or {}
    modules = digest.get("modules", [])
    if not modules:
        return []
    module_dir = output_path.with_name(output_path.stem + "_modules")
    module_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for module in modules:
        module_name = module.get("module_name", "")
        if not module_name:
            continue
        path = module_dir / f"{safe_filename(module_name)}.md"
        path.write_text(_render_module_page(digest, module) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def _render_module_page(digest, module):
    module_name = module.get("module_name", "")
    policy = module.get("page_policy", {})
    detail_level = policy.get("detail_level", "standard")
    summary = _preferred_module_summary_claim(module)
    source_files = module.get("source_files", [])
    position = module.get("system_position", {})
    port_summary = module.get("port_summary", {})
    lines = [
        f"# 模块 `{module_name}`",
        "",
        f"- 源文件：{_code_list(source_files)}。",
        f"- 职责：{_claim_brief(summary, limit=220)}。",
    ]
    if summary.get("explanation") and detail_level != "compact":
        lines.append(f"- 说明：{_plain(summary.get('explanation'))}")
    lines.extend([
        "",
        "## 1. 层级位置",
        "",
        f"- Parents：{_code_list(position.get('parents', []))}。",
        f"- Children：{_code_list(position.get('children', []))}。",
        f"- Component children：{_code_list(position.get('component_children', []))}。",
        f"- Upstream modules：{_code_list(position.get('upstream_modules', []))}。",
        f"- Downstream modules：{_code_list(position.get('downstream_modules', []))}。",
    ])
    lines.extend(_render_module_structure_diagram(module))
    lines.extend([
        "",
        "## 2. 输入/输出接口摘要",
        "",
        f"- 接收：{_natural_port_side(port_summary, 'input')}。",
        f"- 输出：{_natural_port_side(port_summary, 'output')}。",
    ])
    lines.extend(_render_module_port_groups(port_summary, detail_level))
    lines.extend(_render_module_interfaces(module, detail_level))
    lines.extend(_render_module_flows(digest, module, detail_level))
    lines.extend(_render_module_components_assignments(module, detail_level))
    return "\n".join(lines).strip()


def _render_module_port_groups(port_summary, detail_level):
    groups = port_summary.get("external_port_groups", []) if isinstance(port_summary, dict) else []
    if not groups:
        return []
    limit = 99 if detail_level == "detailed" else 8 if detail_level == "standard" else 4
    lines = [
        "",
        "### 2.1 端口分组",
        "",
        "| 端口组 | 方向统计 | 代表信号 |",
        "| --- | --- | --- |",
    ]
    for group in groups[:limit]:
        direction_counts = group.get("direction_counts", {})
        direction_text = ", ".join(f"{key}:{value}" for key, value in sorted(direction_counts.items())) or "未记录"
        signals = [item.get("name", "") for item in group.get("signals", [])]
        lines.append(
            "| "
            + " | ".join([
                _md_cell(_code(group.get("group"))),
                _md_cell(direction_text),
                _md_cell(_code_list(_clip_list(signals, 10))),
            ])
            + " |"
        )
    if len(groups) > limit:
        lines.append(f"| ... | ... | 其余 {len(groups) - limit} 个端口组省略，详见 module_doc_card |")
    return lines


def _render_module_structure_diagram(module):
    module_name = module.get("module_name", "")
    position = module.get("system_position", {})
    children = [
        {"name": child, "label": child, "kind": "module"}
        for child in position.get("children", [])
        if child
    ]
    component_children = [
        {"name": child, "label": child, "kind": "component"}
        for child in position.get("component_children", [])
        if child
    ]
    primary_components = module.get("internal_components", {}).get("primary_samples", [])
    instance_nodes = []
    seen_instance_keys = set()
    for component in primary_components:
        instance_name = component.get("instance_name", "")
        module_type = component.get("module_type") or component.get("component_family") or ""
        if not instance_name:
            continue
        key = (instance_name, module_type)
        if key in seen_instance_keys:
            continue
        seen_instance_keys.add(key)
        label = f"{instance_name}: {module_type}" if module_type else instance_name
        instance_nodes.append({"name": instance_name, "label": label, "kind": "instance"})

    nodes = _dedupe_diagram_nodes(instance_nodes + children + component_children)
    lines = [
        "",
        "### 1.1 本模块结构图",
        "",
    ]
    if not nodes:
        lines.append("Manual Context 未记录本模块的内部实例或子模块结构。")
        return lines

    max_nodes = 24
    selected = nodes[:max_nodes]
    mermaid_lines = []
    for item in selected:
        edge_label = ""
        if item.get("kind") == "component":
            edge_label = "component"
        elif item.get("kind") == "instance":
            edge_label = "instance"
        mermaid_lines.append(
            _mermaid_edge(module_name, item["label"], edge_label=edge_label)
        )

    ascii_lines = [module_name]
    for index, item in enumerate(selected):
        connector = "`-- " if index == len(selected) - 1 else "|-- "
        ascii_lines.append(f"{connector}{item['label']}")

    lines.extend([
        "```mermaid",
        "flowchart TB",
        *mermaid_lines,
        "```",
        "",
        "```text",
        *ascii_lines,
        "```",
    ])
    if len(nodes) > max_nodes:
        lines.append(f"- 图中仅展示前 {max_nodes} 个结构节点，其余 {len(nodes) - max_nodes} 个节点见层级字段或组件表。")
    return lines


def _render_module_interfaces(module, detail_level):
    groups = module.get("interfaces", {}).get("interface_groups", [])
    primary = [group for group in groups if group.get("doc_priority") == "primary"]
    rows = primary or groups
    limit = 24 if detail_level == "detailed" else 12 if detail_level == "standard" else 6
    lines = [
        "",
        "## 3. Drive/Data/Free 契约",
        "",
        "| Interface | 方向 | Event | Payload | Free/backpressure |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not rows:
        lines.append("| - | - | - | - | Manual Context 未提供接口分组 |")
        return lines
    for group in rows[:limit]:
        event_signals = group.get("event_signals", [])
        event = event_signals[0].get("name", "") if event_signals else ""
        payloads = _format_signal_facts(group.get("payload_signals", []), max_items=5) or "未记录"
        free_signals = [item.get("name", "") for item in group.get("free_backpressure_signals", []) if isinstance(item, dict)]
        free_text = _code_list(free_signals) if free_signals else "未记录"
        lines.append(
            "| "
            + " | ".join([
                _md_cell(_code(group.get("interface_name"))),
                _md_cell(group.get("direction", "")),
                _md_cell(_code(event) if event else "-"),
                _md_cell(payloads),
                _md_cell(free_text),
            ])
            + " |"
        )
    if len(rows) > limit:
        lines.append(f"| ... | ... | ... | ... | 其余 {len(rows) - limit} 个接口见 Manual Context |")
    return lines


def _render_module_flows(digest, module, detail_level):
    flows = _load_module_flow_contexts(digest, module)
    limit = 12 if detail_level == "detailed" else 6 if detail_level == "standard" else 3
    lines = [
        "",
        "## 4. 主要 Drive-centered Flow",
        "",
    ]
    if not flows:
        lines.append("- 证据不足：Manual Context 未提供本模块 drive flow。")
        return lines
    for flow in flows[:limit]:
        trigger = flow.get("trigger_event", {})
        semantic = flow.get("semantic_meaning", {})
        behavior = flow.get("branch_merge_behavior", {})
        lines.extend([
            f"### `{trigger.get('signal', '')}`",
            "",
            f"- 确定性事实：`{flow.get('title', '')}`；flow_id=`{flow.get('flow_id', '')}`。",
            f"- Payload：{_format_payloads(flow.get('payloads', [])) or '未记录'}。",
            f"- 输出/影响：{_format_effects_inline(flow.get('outputs_or_effects', [])) or '未记录'}。",
            f"- 结构复杂度：branch={len(behavior.get('branch_points', []))}，join={len(behavior.get('join_points', []))}，blocking={len(behavior.get('blocking_points', []))}。",
        ])
        if semantic.get("value"):
            lines.append(f"- {_claim_label(semantic)}：{_plain(semantic.get('value'))}")
        lines.append("")
    if len(flows) > limit:
        lines.append(f"- 其余 {len(flows) - limit} 条 flow 保留在 Manual Context 的 flows 目录中。")
    return lines


def _render_module_components_assignments(module, detail_level):
    component_limit = 12 if detail_level == "detailed" else 6 if detail_level == "standard" else 3
    assignment_limit = 12 if detail_level == "detailed" else 6 if detail_level == "standard" else 3
    components = module.get("internal_components", {}).get("primary_samples", [])
    assignments = module.get("assignment_impact_summary", {}).get("primary_samples", [])
    lines = [
        "",
        "## 5. 内部组件与 assign 影响",
        "",
        "### 5.1 内部组件",
        "",
        "| 实例 | 类型 | 输入事件 | 输出事件 |",
        "| --- | --- | --- | --- |",
    ]
    if components:
        for component in components[:component_limit]:
            lines.append(
                "| "
                + " | ".join([
                    _md_cell(_code(component.get("instance_name"))),
                    _md_cell(_code(component.get("module_type") or component.get("component_family"))),
                    _md_cell(_code_list(component.get("input_events", []))),
                    _md_cell(_code_list(component.get("output_events", []))),
                ])
                + " |"
            )
        if len(components) > component_limit:
            lines.append(f"| ... | ... | ... | ... | 其余 {len(components) - component_limit} 个组件省略 |")
    else:
        lines.append("| - | - | - | Manual Context 未提供 primary internal component |")
    lines.extend([
        "",
        "### 5.2 assign 影响",
        "",
        "| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |",
        "| --- | --- | --- | --- | --- |",
    ])
    if assignments:
        for assignment in assignments[:assignment_limit]:
            interpretation = assignment.get("interpretation", {})
            if interpretation.get("certainty") == "evidence_gap":
                interpretation_text = f"证据不足：{_plain(interpretation.get('reason') or '未提供语义解释')}"
            elif interpretation.get("value"):
                interpretation_text = f"{_claim_label(interpretation)}：{_plain(interpretation.get('value'))}"
            else:
                interpretation_text = "证据不足：未提供语义解释"
            lines.append(
                "| "
                + " | ".join([
                    _md_cell(_code(assignment.get("assignment_id"))),
                    _md_cell(assignment.get("impact_area", "")),
                    _md_cell(_code(assignment.get("lhs"))),
                    _md_cell(_shorten(assignment.get("rhs", ""), 96)),
                    _md_cell(interpretation_text),
                ])
                + " |"
            )
        if len(assignments) > assignment_limit:
            lines.append(f"| ... | ... | ... | ... | 其余 {len(assignments) - assignment_limit} 条 assign 省略 |")
    else:
        lines.append("| - | - | - | - | Manual Context 未提供 primary assign 影响 |")
    return lines


def _render_module_gaps(module):
    rows = []
    for gap in module.get("evidence_gaps", []):
        rows.append(gap)
    for gap in module.get("gap_file", {}).get("gaps", []):
        rows.append(gap)
    lines = [
        "",
        "## 6. 证据缺口",
        "",
    ]
    if not rows:
        lines.append("- 当前模块页未记录 evidence_gap。")
        return lines
    for gap in rows[:20]:
        lines.append(f"- {_gap_review_question(gap)}（evidence={_refs_text(gap)}）")
    if len(rows) > 20:
        lines.append(f"- 其余 {len(rows) - 20} 个 gap 见 `gaps.json`。")
    return lines


def _load_module_flow_contexts(digest, module):
    root = Path(digest.get("manual_context_dir", ""))
    module_name = module.get("module_name", "")
    flows = []
    seen = set()
    for ref in module.get("key_drive_flows", []):
        source_file = ref.get("source_file", "")
        if not source_file:
            continue
        path = root / "modules" / safe_filename(module_name) / source_file
        if str(path) in seen or not path.exists():
            continue
        try:
            flows.append(_read_json(path))
            seen.add(str(path))
        except Exception:
            continue
    return flows


def _format_effects_inline(effects):
    if not effects:
        return ""
    deterministic = [effect.get("signal") for effect in effects if effect.get("certainty") == "deterministic_fact" and effect.get("signal")]
    gaps = [effect for effect in effects if effect.get("certainty") == "evidence_gap"]
    parts = []
    if deterministic:
        parts.append(_code_list(deterministic))
    if gaps:
        parts.append("证据不足：" + "；".join(_plain(item.get("reason", "")) for item in gaps[:2]))
    return "；".join(parts)


def _collect_interface_rows(digest, limit=20):
    rows = []
    for module in digest.get("modules", []):
        module_name = module.get("module_name", "")
        groups = module.get("interfaces", {}).get("interface_groups", [])
        for group in groups:
            if group.get("doc_priority") != "primary":
                continue
            event_signals = group.get("event_signals", [])
            if not event_signals:
                continue
            event = event_signals[0].get("name", "")
            binding = group.get("event_payload_binding", {})
            payloads = _format_signal_facts(group.get("payload_signals", []), max_items=4)
            free_signal = binding.get("free_signal", "")
            if not free_signal and group.get("free_backpressure_signals"):
                free_signal = group["free_backpressure_signals"][0].get("name", "")
            free_note = "未记录"
            if free_signal:
                free_note = f"`{free_signal}`；reference；仅在影响 drive availability/backpressure 时解释"
            rows.append({
                "module": module_name,
                "interface": group.get("interface_name", ""),
                "direction": group.get("direction", ""),
                "event": event,
                "payloads": payloads or "未记录",
                "free_note": free_note,
                "evidence": _refs_text(group),
            })
            if len(rows) >= limit:
                return rows
    return rows


def _collect_flow_contexts(digest, limit=10):
    root = Path(digest.get("manual_context_dir", ""))
    candidates = []
    for module in digest.get("modules", []):
        module_name = module.get("module_name", "")
        for flow in module.get("key_drive_flows", [])[:2]:
            candidates.append((module_name, flow.get("source_file", "")))
    for flow in digest.get("flow_index", {}).get("samples", []):
        candidates.append((flow.get("module", ""), flow.get("source_file", "")))

    result = []
    seen = set()
    for module_name, source_file in candidates:
        if not source_file:
            continue
        if source_file.startswith("modules/"):
            path = root / source_file
        else:
            path = root / "modules" / safe_filename(module_name) / source_file
        key = str(path)
        if key in seen or not path.exists():
            continue
        try:
            payload = _read_json(path)
        except Exception:
            continue
        result.append(payload)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _collect_assignment_rows(digest, limit=18):
    rows = []
    for module in digest.get("modules", []):
        module_name = module.get("module_name", "")
        assignments = module.get("assignment_impact_summary", {}).get("primary_samples", [])
        for assignment in assignments:
            interpretation = assignment.get("interpretation", {})
            if interpretation.get("certainty") == "evidence_gap":
                interpretation_text = f"证据缺口：{_plain(interpretation.get('reason') or interpretation.get('value') or '未提供语义解释')}"
            elif interpretation.get("value"):
                interpretation_text = f"{_claim_label(interpretation)}：{_plain(interpretation.get('value'))}"
            else:
                interpretation_text = "证据缺口：未提供语义解释"
            rows.append({
                "module": module_name,
                "assignment_id": assignment.get("assignment_id", ""),
                "impact_area": assignment.get("impact_area", ""),
                "lhs": assignment.get("lhs", ""),
                "rhs": assignment.get("rhs", ""),
                "interpretation": interpretation_text,
                "evidence": _refs_text(assignment),
            })
            if len(rows) >= limit:
                return rows
    return rows


def _collect_gap_rows(digest, limit=30):
    gaps = []

    def add(gap):
        if not isinstance(gap, dict):
            gap = {"reason": str(gap), "certainty": "evidence_gap"}
        key = (gap.get("field", ""), gap.get("reason", ""))
        if key not in {(item.get("field", ""), item.get("reason", "")) for item in gaps}:
            gaps.append(gap)

    for gap in digest.get("project_context", {}).get("system_level_gaps", []):
        add(gap)
    for module in digest.get("modules", []):
        for gap in module.get("evidence_gaps", []):
            add(gap)
        for gap in module.get("gap_file", {}).get("gaps", []):
            add(gap)
        if len(gaps) >= limit:
            break
    return gaps[:limit]


def _collect_review_questions(digest, limit=20):
    rows = []
    seen = set()
    for module in digest.get("modules", []):
        for question in module.get("review_questions", []):
            if not isinstance(question, dict):
                question = {"question": str(question)}
            key = (question.get("subject", ""), question.get("question", ""))
            if key in seen:
                continue
            rows.append(question)
            seen.add(key)
            if len(rows) >= limit:
                return rows
    return rows


def _format_payloads(payloads):
    return _format_signal_facts(payloads, max_items=8)


def _format_signal_facts(signals, max_items=6):
    values = []
    for signal in signals[:max_items]:
        if not isinstance(signal, dict):
            continue
        name = signal.get("name", "")
        width = signal.get("width_text", "")
        event = signal.get("event", "")
        if event:
            values.append(f"`{event}` -> `{name}{(' ' + width) if width else ''}`")
        else:
            values.append(f"`{name}{(' ' + width) if width else ''}`")
    if len(signals) > max_items:
        values.append(f"... +{len(signals) - max_items}")
    return ", ".join(values)


def _format_component_steps(steps):
    if not steps:
        return "无组件步骤"
    values = []
    for step in steps:
        name = step.get("name", "")
        module_type = step.get("module_type", "")
        family = step.get("component_family", "")
        values.append(f"`{name}`({module_type or family or 'component'})")
    return ", ".join(values)


def _format_effects(effects):
    if not effects:
        return ""
    deterministic = [effect for effect in effects if effect.get("certainty") == "deterministic_fact" and effect.get("signal")]
    gaps = [effect for effect in effects if effect.get("certainty") == "evidence_gap"]
    parts = []
    if deterministic:
        parts.append("outputs/effects=" + _code_list([effect.get("signal") for effect in deterministic]))
    if gaps:
        reasons = "；".join(_plain(effect.get("reason", "")) for effect in gaps[:3] if effect.get("reason"))
        parts.append(f"证据缺口：{reasons or 'Knowledge IR 未确认输出效果'}")
    return "- " + "；".join(parts) + "。"


def _module_summary_by_name(digest, module_name):
    for module in digest.get("modules", []):
        if module.get("module_name") == module_name:
            return module
    return {}


def _certainty_label(value):
    labels = {
        "deterministic_fact": "确定性事实",
        "derived_fact": "派生事实",
        "ai_inferred": "AI 推断",
        "human_asserted": "人工断言",
        "evidence_gap": "证据缺口",
    }
    return labels.get(value or "", value or "未标注事实等级")


def _claim_label(claim):
    return _certainty_label(claim.get("certainty", "") if isinstance(claim, dict) else "")


def _refs_text(item):
    refs = []
    if isinstance(item, dict):
        refs = item.get("evidence_refs") or []
    if not refs:
        return "未记录"
    return ", ".join(f"`{ref}`" for ref in refs[:4])


def _gap_text(gap):
    if not isinstance(gap, dict):
        return str(gap)
    field = gap.get("field", "")
    reason = gap.get("reason", "")
    certainty = _certainty_label(gap.get("certainty", "evidence_gap"))
    return f"{certainty}：field=`{field}`；reason={_plain(reason)}；evidence={_refs_text(gap)}"


def _code(value):
    if value is None or value == "":
        return "-"
    return f"`{value}`"


def _code_list(values):
    if not values:
        return "无"
    return ", ".join(_code(value) for value in values)


def _plain(value):
    return str(value or "").replace("\n", " ").strip()


def _shorten(value, limit):
    value = _plain(value)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)] + "..."


def _md_cell(value):
    return _plain(value).replace("|", "\\|") or "-"


def safe_filename(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("._") or "item"


def _review_manual_markdown(state, client, model):
    manual_path = Path(state.get("manual_output_path", ""))
    manual = manual_path.read_text(encoding="utf-8")
    module_pages = _read_module_pages_for_review(state, manual_path)
    return _build_manual_sanity_review(state, manual, module_pages)


def _read_module_pages_for_review(state, manual_path):
    module_dir = Path(state.get("manual_module_pages_dir", "")) if state.get("manual_module_pages_dir") else manual_path.with_name(manual_path.stem + "_modules")
    pages = {}
    if not module_dir.exists():
        return pages
    for path in sorted(module_dir.glob("*.md")):
        try:
            pages[path.stem] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    return pages


def _build_manual_sanity_review(state, manual, module_pages=None):
    digest = state.get("evidence_digest") or {}
    module_pages = module_pages or {}
    all_manual_text = manual + "\n" + "\n".join(module_pages.values())
    findings = []

    def add(severity, title, detail):
        findings.append({"severity": severity, "title": title, "detail": detail})

    stripped = manual.lstrip()
    if stripped.startswith(("好的", "我将", "遵照", "当然")):
        add("P1", "手册包含对话式开场", "最终 Markdown 不能包含模型对用户的寒暄或执行承诺。")
    if "manual_ir" in manual.lower() or "contextpack" in manual.lower():
        add("P1", "手册引用 legacy 主结构", "新主流程下最终手册不能把 legacy manual_ir/ContextPack 当作主证据结构。")
    if "层级样本" in manual or "主要模块摘要" in manual:
        add("P1", "手册仍使用样本式章节", "主手册必须使用完整层级和全量模块索引，不能以样本表替代。")
    if "AI 推断" not in all_manual_text and _digest_contains_ai_claims(digest):
        add("P1", "AI claim 未显式标注", "Manual Context 中存在 ai_inferred claim，最终手册必须出现 AI 推断标注。")

    public_forbidden = (
        "confidence=",
        "review_status",
        "requires_rtl_source_review",
        "| Evidence |",
        " evidence=",
        "evidence_refs",
        "详情级别",
        "关键 Drive-centered Flow 索引",
        "证据缺口与 Review 问题",
        "证据边界与写作规则",
    )
    for pattern in public_forbidden:
        if pattern in all_manual_text:
            add("P1", "公开手册泄露内部证据字段", f"公开手册或模块页中出现 `{pattern}`。")

    known_modules = digest.get("known_modules", [])
    if known_modules:
        missing_links = [
            name for name in known_modules
            if f"{safe_filename(name)}.md" not in manual
        ]
        if missing_links:
            add("P1", "主手册未覆盖全部模块入口", f"缺少 {len(missing_links)} 个模块页入口，例如：{', '.join(missing_links[:8])}")
        missing_pages = [
            name for name in known_modules
            if safe_filename(name) not in module_pages
        ]
        if missing_pages:
            add("P1", "模块页文件不完整", f"缺少 {len(missing_pages)} 个模块页文件，例如：{', '.join(missing_pages[:8])}")

    for line_no, line in enumerate(all_manual_text.splitlines(), start=1):
        stripped_line = line.strip()
        is_deterministic_claim_line = (
            stripped_line.startswith("- 确定性事实")
            or stripped_line.startswith("* 确定性事实")
            or stripped_line.startswith("| 确定性事实")
        )
        if is_deterministic_claim_line and any(word in line for word in ("可能", "推断", "猜测", "需要 review")):
            add("P1", "确定性事实行混入推断措辞", f"第 {line_no} 行：{line.strip()}")
        boundary_line = any(word in line for word in (
            "不得补写",
            "不补写",
            "不会补写",
            "禁止补写",
            "不写入",
            "不能推断",
            "证据边界",
            "请人工确认",
            "证据不足",
            "source review",
            "源码复核",
        ))
        high_risk_terms = (
            "always block",
            "always-block",
            "always 块",
            "always 过程",
            "寄存器更新语义",
            "时序保证",
        )
        if any(term in line for term in high_risk_terms) and not boundary_line:
            add("P2", "出现高风险时序/过程逻辑表述", f"第 {line_no} 行包含 `{line.strip()}`，需要确认其来自 evidence_gap 或明确禁止边界。")

    free_mentions = len(re.findall(r"\bfree\b|Free|backpressure|反压", manual))
    if free_mentions > 60:
        add("P2", "free/backpressure 描述过多", f"全文 free/backpressure 相关命中 {free_mentions} 次，可能偏离 drive-centered 主线。")

    conclusion = "通过" if not any(item["severity"] in {"P1", "P2"} for item in findings) else "不通过"
    lines = [
        "# RTL 代码手册审查报告",
        "",
        f"- 审查目标：`{state.get('top_module', '')}`",
        f"- 审查方式：Manual Context 结构化约束检查 + Source Review 承接检查",
        f"- 总体结论：{conclusion}",
        "",
        "## 检查结果",
    ]
    if findings:
        for item in findings:
            lines.append(f"- {item['severity']} {item['title']}：{item['detail']}")
    else:
        lines.append("- 未发现确定性结构检查项违规。")
    lines.extend(_render_review_source_review_section(digest))
    lines.extend(_render_review_gap_section(digest))
    lines.extend([
        "",
        "## 已检查约束",
        "- final manual 不应包含对话式开场。",
        "- final manual 不应把 `manual_ir` 或 ContextPack 作为主证据结构。",
        "- 主手册必须提供全量模块页入口，模块页文件必须覆盖 reachable modules。",
        "- 手册不应以“样本”章节替代完整层级或完整模块索引。",
        "- 公开手册不得输出 evidence refs、confidence、review_status、requires_rtl_source_review 等内部字段。",
        "- `ai_inferred` 内容在公开手册中只标注为 AI 推断。",
        "- `evidence_gap`、review questions 和 source-review 结果必须进入 review 文档。",
        "- `deterministic_fact` 行不得混入“可能/推断/需要 review”等不确定措辞。",
        "- `free` 只作为影响 drive availability/backpressure 的参考，不作为主流程解释入口。",
        "",
        "## 证据边界",
    ])
    for item in digest.get("evidence_boundary", []):
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## 剩余风险",
        "- 本审查器只做结构化和文本边界检查；复杂 RTL 语义仍以 Manual Context 的 evidence_refs 和后续人工 RTL review 为准。",
    ])
    return "\n".join(lines)


def _render_review_source_review_section(digest):
    report = digest.get("source_review_report") or {}
    lines = [
        "",
        "## Source Review 结果",
    ]
    if not report:
        lines.append("- 未发现 `source_review_report.json`；需要源码复核的项仍应由人工确认。")
    else:
        lines.extend([
            f"- 目标模块数：{report.get('target_count', 0)}",
            f"- 已复核模块数：{report.get('reviewed_modules', 0)}",
            f"- 写回 claim 数：{report.get('claim_count', 0)}",
            f"- 未解决问题数：{report.get('unresolved_count', 0)}",
        ])
        for item in report.get("modules", [])[:40]:
            lines.append(
                f"- `{item.get('module', '')}`：status=`{item.get('status', '')}`，"
                f"claims={item.get('claim_count', 0)}，open_questions={item.get('open_question_count', 0)}，"
                f"report=`{item.get('report_file', '')}`"
            )
    reviewed_claims = []
    open_questions = []
    for module in digest.get("modules", []):
        module_name = module.get("module_name", "")
        for claim in module.get("source_review_claims", []) or []:
            reviewed_claims.append((module_name, claim))
        for question in (module.get("source_review_report", {}) or {}).get("open_questions", []) or []:
            open_questions.append((module_name, question))
    if reviewed_claims:
        lines.extend(["", "### 已写回源码复核 Claim", ""])
        for module_name, claim in reviewed_claims[:60]:
            lines.append(
                f"- `{module_name}` / `{claim.get('subject', '')}`："
                f"{_certainty_label(claim.get('certainty', ''))}：{_plain(claim.get('summary', ''))}；"
                f"source={_source_refs_text(claim)}；evidence={_refs_text(claim)}"
            )
    if open_questions:
        lines.extend(["", "### 源码复核后仍需确认", ""])
        for module_name, question in open_questions[:60]:
            lines.append(
                f"- `{module_name}` / `{question.get('subject', '')}`：{_plain(question.get('question', ''))}；"
                f"source={_source_refs_text(question)}；evidence={_refs_text(question)}"
            )
    return lines


def _render_review_gap_section(digest):
    grouped = _collect_grouped_gaps(digest)
    questions = _collect_review_questions(digest, limit=80)
    lines = [
        "",
        "## 证据缺口与 Review 问题",
    ]
    if grouped:
        lines.extend(["", "### Evidence gaps", ""])
        for item in grouped[:80]:
            lines.append(
                f"- `{item.get('scope', '')}`：{item.get('question', '')}；evidence={item.get('evidence', '')}"
            )
    else:
        lines.append("- 当前 Manual Context 未记录 evidence_gap。")
    if questions:
        lines.extend(["", "### Review questions", ""])
        for question in questions:
            lines.append(
                f"- `{question.get('subject', '')}`：{_plain(question.get('question', ''))}；evidence={_refs_text(question)}"
            )
    return lines


def _source_refs_text(item):
    refs = item.get("source_refs", []) if isinstance(item, dict) else []
    if not refs:
        return "未记录"
    values = []
    for ref in refs[:4]:
        if not isinstance(ref, dict):
            continue
        file_name = ref.get("file", "")
        start = ref.get("line_start", "")
        end = ref.get("line_end", "")
        values.append(f"`{file_name}:{start}-{end}`")
    return ", ".join(values) or "未记录"


def _digest_contains_ai_claims(digest):
    if (digest.get("project_context", {}).get("system_summary") or {}).get("certainty") == "ai_inferred":
        return True
    for item in digest.get("project_context", {}).get("major_modules", []):
        if item.get("certainty") == "ai_inferred":
            return True
    for module in digest.get("modules", []):
        summary = module.get("responsibility", {}).get("short_summary", {})
        if summary.get("certainty") == "ai_inferred":
            return True
    return False


def _manual_output_path(state, text):
    if state.get("manual_output_override"):
        return Path(state["manual_output_override"])

    explicit = _match_value(
        text or "",
        (
            r"保存到\s*([^\s，,。；;]+)",
            r"输出到\s*([^\s，,。；;]+)",
            r"写入\s*([^\s，,。；;]+)",
        ),
    )
    if explicit:
        return Path(_clean_path(explicit))

    return (
        Path(state["project_root"])
        / "docs"
        / "manuals"
        / f"{state['top_module']}_generated.md"
    )


def _review_output_path(state):
    manual_output_path = state.get("manual_output_path") or state.get("manual_output_override")
    if manual_output_path:
        path = Path(manual_output_path)
        return path.with_name(path.stem + "_review.md")

    return (
        Path(state["project_root"])
        / "docs"
        / "manuals"
        / f"{state['top_module']}_review.md"
    )


def _build_manual_summary(manual, state):
    outline = state.get("outline") or []
    chapter_plan = state.get("chapter_plan") or []
    return {
        "chars": len(manual),
        "lines": len(manual.splitlines()),
        "outline_count": len(outline),
        "chapter_plan_count": len(chapter_plan),
        "evidence_mode": state.get("evidence_mode", PROJECT_EVIDENCE_MODE),
        "top_module": state.get("top_module", ""),
        "module_page_count": state.get("manual_module_page_count", 0),
        "module_pages_dir": state.get("manual_module_pages_dir", ""),
    }


def _format_manual_summary(summary):
    return "\n".join([
        "## 手册摘要",
        f"- top_module：`{summary.get('top_module', '')}`",
        f"- 主证据：`{summary.get('evidence_mode', '')}`",
        f"- 章节数：{summary.get('outline_count', 0)}",
        f"- 章节规划数：{summary.get('chapter_plan_count', 0)}",
        f"- 字符数：{summary.get('chars', 0)}",
        f"- 行数：{summary.get('lines', 0)}",
        f"- 模块页数：{summary.get('module_page_count', 0)}",
    ])


def _review_summary(review):
    lines = [line.rstrip() for line in (review or "").splitlines() if line.strip()]
    if not lines:
        return "审查报告为空。"

    selected = []
    for line in lines:
        selected.append(line)
        if len(selected) >= 12:
            break
    return "\n".join(selected)


def _format_reply(state, title, lines):
    mode = "自动连续执行" if state.get("auto_run", True) else "分阶段单步执行"
    header = [
        f"【后端固定流程：{MANUAL_SKILL_NAME}】",
        f"【执行模式：{mode}】",
        f"【当前阶段：{state.get('stage', '')}】",
        f"【project_root：{state.get('project_root', '')}】",
        f"【rtl_inputs：{state.get('rtl_inputs', '')}】",
        f"【top_module：{state.get('top_module', '') or '未设置'}】",
        f"【主证据：{state.get('evidence_mode', PROJECT_EVIDENCE_MODE)} / audience={state.get('audience', 'newcomer')}】",
        f"【语义增强：开启 / modules={state.get('enrich_modules') or '全部模块'}】",
        "",
        f"## {title}",
        "",
    ]
    return "\n".join(header + list(lines)).strip()


def _tool_failed(result):
    lower_result = (result or "").lower()
    return (
        lower_result.startswith("parser failed")
        or lower_result.startswith("knowledge tool execution failed")
        or "knowledge tool execution incomplete" in lower_result
        or "some expected artifacts are missing" in lower_result
        or "执行失败" in result
        or "不存在" in result
    )


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _clip_text(text, limit=6000):
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[已截断]"


def _mark_stage_done(state, stage):
    completed = list(state.get("completed_stages", []))
    if stage not in completed:
        completed.append(stage)
    state["completed_stages"] = completed
    force_stages = [
        item for item in state.get("force_stages", [])
        if item != stage
    ]
    state["force_stages"] = force_stages
    if not force_stages:
        state["restart_stage"] = ""
    state["last_error"] = ""
