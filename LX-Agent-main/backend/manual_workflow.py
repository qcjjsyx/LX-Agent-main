import json
import re
from pathlib import Path

try:
    from .tools import run_knowledge_tool, run_parser_tool
except ImportError:
    from tools import run_knowledge_tool, run_parser_tool


MANUAL_SKILL_NAME = "rtl-manual-generation"

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
    if stage == "references":
        return _run_reference_stage(state, base_dir, event_logger)
    if stage == "parser":
        return _run_parser_stage(state, event_logger)
    if stage == "knowledge":
        return _run_knowledge_stage(state, event_logger)
    if stage == "evidence":
        return _run_evidence_stage(state, event_logger)
    if stage == "outline":
        return _run_outline_stage(state, event_logger)
    if stage == "chapter_plan":
        return _run_chapter_plan_stage(state, event_logger)
    if stage == "manual":
        return _run_manual_stage(state, client, model, user_input, event_logger)
    if stage == "review":
        return _run_review_stage(state, client, model, event_logger)
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
            "last_error": "",
            "manual_output_path": "",
            "auto_run": True,
            "force_regenerate": False,
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
    state.setdefault("last_error", "")
    state.setdefault("manual_output_path", "")
    state.setdefault("auto_run", True)
    state.setdefault("force_regenerate", False)
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

    if _wants_regenerate(user_input):
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
        "5. Outline：根据证据生成完整手册目录。",
        "6. Chapter Plan：生成每章大致内容与证据来源。",
        "7. Manual：生成 Markdown 代码手册正文。",
        "8. Review：审查手册是否越过证据边界。",
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
    if ready and not _force_regenerate(state):
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
    if ready and not _force_regenerate(state):
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
    manual_context_dir = Path(state["manual_context_dir"])
    manifest_path = manual_context_dir / "manifest.json"
    project_context_path = manual_context_dir / "project_context.json"
    system_topology_path = manual_context_dir / "system_topology.json"
    interface_index_path = manual_context_dir / "interface_index.json"
    flow_index_path = manual_context_dir / "flow_index.json"
    evidence_index_path = manual_context_dir / "evidence_index.json"
    validation_report_path = manual_context_dir / "validation_report.json"

    missing = [
        str(path)
        for path in (
            manifest_path,
            project_context_path,
            system_topology_path,
            interface_index_path,
            flow_index_path,
            evidence_index_path,
            validation_report_path,
        )
        if not path.exists()
    ]
    if missing:
        _log_event(
            event_logger,
            "manual_evidence_missing",
            skill=MANUAL_SKILL_NAME,
            missing=[str(item) for item in missing],
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
    state["stage"] = "outline"

    return _format_reply(
        state,
        "阶段4：证据读取完成",
        [
            "我已建立 Manual Context 主证据索引。后续目录、章节规划和手册内容只会基于这些证据生成。",
            "",
            _format_digest(digest),
            "",
            _next_stage_hint(state, "阶段5：根据证据生成完整手册目录"),
        ],
    )


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
        "阶段5完成：已根据 Manual Context 证据生成手册目录。",
        "",
        "## 拟定目录",
    ]
    for index, item in enumerate(outline, start=1):
        lines.append(f"{index}. {item['title']}")
        if item.get("evidence"):
            lines.append(f"   证据：{', '.join(item['evidence'])}")

    lines.extend([
        "",
        _next_stage_hint(state, "阶段6：生成每章大致内容规划"),
    ])
    return _format_reply(state, "阶段5：规划目录", lines)


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
        "阶段6完成：已生成每章大致内容和证据来源。",
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
        _next_stage_hint(state, "阶段7：生成完整 Markdown 手册"),
    ])
    return _format_reply(state, "阶段6：章节内容规划", lines)


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
        ("项目总览", "建立完整工程的系统边界、对象规模和文档焦点。", ["说明 top module", "列出 Manual Context 对象数量", "概括一级模块和主要事件模式"]),
        ("顶层模块", "解释顶层模块在系统中的职责和直接结构。", ["说明 top module 摘要", "列出直接一级子模块", "区分确定事实和 AI 推断"]),
        ("模块层级", "让读者看到模块之间的父子关系和结构展开方式。", ["按 parent/child 关系组织模块", "列出关键子模块和结构子", "提示证据来自 system_topology 和 module_context"]),
        ("关键模块职责", "解释主要模块各自承担的功能角色。", ["逐个概括 major module", "列出 module_responsibility 和 documentation_focus", "保留 review_status"]),
        ("接口", "说明接口边界、数据事件绑定和主次文档优先级。", ["汇总 primary interfaces", "说明 payload/free 与 drive 的关系", "free 仅在影响 backpressure 时重点解释"]),
        ("Drive-centered Flow", "说明以 drive 为核心的事件/数据/控制路径。", ["列出 trigger_event、payload、endpoint", "说明 branch/join/blocking 点", "标注 requires_review 和 evidence_gap"]),
        ("内部组件", "说明结构子 family 和 assign 对手册解释的影响。", ["按 component_family 分组", "解释 primary component role", "说明 assignment impact 的 certainty"]),
        ("证据缺口", "给维护者和审查者提供待确认项。", ["汇总 evidence_gaps", "列出 review_questions", "结合 validation_report 判断风险"]),
        ("证据边界", "明确哪些内容由 Manual Context 支持，哪些不能推断。", ["列出 evidence_boundary", "说明 certainty 写作规则", "说明 parser 当前不证明 FSM/always/register 行为"]),
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
    if ready and not _force_regenerate(state):
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
            "阶段7：手册生成已跳过",
            [
                "检测到已有 Markdown 代码手册文件，本次复用已有手册。",
                f"手册路径：`{state['manual_output_path']}`",
                "",
                _format_manual_summary(state["manual_summary"]),
                "",
                "如需重新生成，请在请求中加入 `重新生成`、`强制生成` 或 `覆盖生成`。",
                "",
                _next_stage_hint(state, "阶段8：审查或复用审查报告"),
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
            "阶段7：生成手册失败",
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

    state["manual_output_path"] = str(output_path)
    state["manual_summary"] = _build_manual_summary(manual, state)
    _mark_stage_done(state, "manual")
    state["stage"] = "review"

    lines = [
        "阶段7完成：完整 Markdown 手册已生成并保存。",
        "",
        f"保存路径：`{state['manual_output_path']}`",
        "",
        _format_manual_summary(state["manual_summary"]),
        "",
        _next_stage_hint(state, "阶段8：审查手册"),
    ]

    return _format_reply(state, "阶段7：生成手册", lines)


def _run_review_stage(state, client, model, event_logger=None):
    manual_path = Path(state.get("manual_output_path", ""))
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
            "阶段8：审查失败",
            [
                "没有找到可审查的手册文件，流程停在 `review` 阶段。",
                f"期望路径：`{manual_path}`",
            ],
        )

    review_output_path = _review_output_path(state)
    if review_output_path.exists() and review_output_path.is_file() and not _force_regenerate(state):
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
            "阶段8：审查已跳过",
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
            "阶段8：审查失败",
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
        "阶段8：审查完成",
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
    flow_samples = flow_index.get("flows", [])[:80]
    primary_interfaces = [
        item for item in interface_index.get("interfaces", [])
        if item.get("doc_priority") == "primary"
    ][:100]
    evidence_policy = evidence_index.get("evidence_policy", {})

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
            "system_summary": project_context.get("system_summary", {}),
            "top_level": project_context.get("top_level", {}),
            "major_modules": project_major_modules[:30],
            "component_families_overview": project_context.get("component_families_overview", [])[:30],
            "system_level_gaps": project_context.get("system_level_gaps", [])[:40],
        },
        "known_modules": sorted((manifest.get("files", {}).get("modules") or {}).keys()),
        "system_topology": _summarize_manual_context_topology(system_topology, top_module),
        "interface_index": {
            "counts": interface_index.get("counts", {}),
            "primary_samples": primary_interfaces,
            "all_samples": interface_index.get("interfaces", [])[:80],
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
        "evidence_policy": evidence_policy,
        "evidence_samples": evidence_index.get("evidence", [])[:80],
        "evidence_boundary": [
            "主证据为 Manual Context；最终手册不要直接把 parser JSON、Knowledge IR、AI Context 或 Semantic Layer 当作主输入。",
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
                "modules/<module>/interfaces.json",
                "modules/<module>/flows/<flow_id>.json",
            ],
            "forbidden_promotions": [
                "ai_inferred_to_deterministic_fact",
                "evidence_gap_to_confirmed_behavior",
                "free_signal_to_main_protocol_without_backpressure_evidence",
            ],
        },
    }


def _select_manual_context_modules(top_module, manifest, project_context, system_topology):
    selected = []

    def add(name):
        if name and name not in selected:
            selected.append(name)

    add(top_module)
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
    return [name for name in selected if name in known_modules][:30]


def _read_manual_context_module(manual_context_dir, module_name):
    module_dir = Path(manual_context_dir) / "modules" / module_name
    module_context_path = module_dir / "module_context.json"
    if not module_context_path.exists():
        return {}
    payload = _read_json(module_context_path)
    payload["_interfaces"] = _read_json(module_dir / "interfaces.json") if (module_dir / "interfaces.json").exists() else {}
    payload["_gaps"] = _read_json(module_dir / "gaps.json") if (module_dir / "gaps.json").exists() else {}
    return payload


def _summarize_manual_context_module(item):
    identity = item.get("module_identity", {})
    position = item.get("system_position", {})
    responsibility = item.get("module_responsibility", {})
    interface_summary = item.get("interface_summary", {})
    gaps_payload = item.get("_gaps", {})
    interfaces_payload = item.get("_interfaces", {})
    components = item.get("internal_components", [])
    assignments = item.get("assignment_impact_summary", [])

    return {
        "module_name": identity.get("module_name", ""),
        "module_role": identity.get("module_role", ""),
        "source_files": identity.get("source_files", []),
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
        "edge_samples": edges[:120],
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
            {"title": "项目总览", "evidence": ["project_context", "manifest.counts", "doc_focus"]},
            {"title": f"顶层模块 {top_module}", "evidence": ["project_context.top_level", f"modules.{top_module}.module_context"]},
            {"title": "模块层级结构", "evidence": ["system_topology.hierarchy_edges", "modules.system_position"]},
            {"title": "关键模块职责", "evidence": ["project_context.major_modules", "modules.module_responsibility"]},
            {"title": "接口与数据事件契约", "evidence": ["interface_index", "modules.interfaces"]},
            {"title": "Drive-centered Flow", "evidence": ["flow_index", "modules.key_drive_flows"]},
            {"title": "内部组件与 Assign 影响", "evidence": ["modules.internal_components", "modules.assignment_impact_summary"]},
            {"title": "证据缺口与 Review 问题", "evidence": ["modules.evidence_gaps", "modules.review_questions", "validation"]},
            {"title": "证据边界与写作规则", "evidence": ["evidence_policy", "evidence_boundary"]},
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

    lines = [
        f"# {top_module} RTL 代码手册",
        "",
        "本手册由 `manual_context` 结构化证据渲染生成。确定性事实、派生事实、AI 推断和证据缺口按字段原样分级，手册不补写 Manual Context 中没有的连接、接口、flow、时序保证、always/FSM 行为或寄存器更新语义。",
        "",
    ]
    lines.extend(_render_project_overview_section(digest))
    lines.extend(_render_top_module_section(digest, top_module))
    lines.extend(_render_hierarchy_section(digest))
    lines.extend(_render_responsibility_section(digest))
    lines.extend(_render_interfaces_section(digest))
    lines.extend(_render_flows_section(digest))
    lines.extend(_render_components_assignments_section(digest))
    lines.extend(_render_gaps_section(digest))
    lines.extend(_render_evidence_boundary_section(digest))
    return "\n".join(lines).strip()


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
            _md_cell(edge.get("certainty", "")),
            _md_cell(_refs_text(edge)),
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
        "## 9. 证据边界与写作规则",
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
    certainty = _certainty_label(claim.get("certainty", "") if isinstance(claim, dict) else "")
    extras = []
    if isinstance(claim, dict):
        if claim.get("confidence"):
            extras.append(f"confidence={claim.get('confidence')}")
        if claim.get("review_status"):
            extras.append(f"review_status={claim.get('review_status')}")
        if claim.get("requires_rtl_source_review"):
            extras.append("requires_rtl_source_review=true")
    return certainty if not extras else f"{certainty}（{', '.join(extras)}）"


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
    return _build_manual_sanity_review(state, manual)


def _build_manual_sanity_review(state, manual):
    digest = state.get("evidence_digest") or {}
    findings = []

    def add(severity, title, detail):
        findings.append({"severity": severity, "title": title, "detail": detail})

    stripped = manual.lstrip()
    if stripped.startswith(("好的", "我将", "遵照", "当然")):
        add("P1", "手册包含对话式开场", "最终 Markdown 不能包含模型对用户的寒暄或执行承诺。")
    if "manual_ir" in manual.lower() or "contextpack" in manual.lower():
        add("P1", "手册引用 legacy 主结构", "新主流程下最终手册不能把 legacy manual_ir/ContextPack 当作主证据结构。")
    if "Validation" not in manual and "validation" not in manual:
        add("P2", "缺少 validation 结果", "手册必须写入 validation_report 的 status 和 issue_count。")
    if "证据缺口" not in manual:
        add("P2", "缺少 evidence_gap 章节或标注", "手册必须显式呈现 Manual Context 中的 evidence gaps。")
    if "AI 推断" not in manual and _digest_contains_ai_claims(digest):
        add("P1", "AI claim 未显式标注", "Manual Context 中存在 ai_inferred claim，最终手册必须出现 AI 推断标注。")

    for line_no, line in enumerate(manual.splitlines(), start=1):
        stripped_line = line.strip()
        is_deterministic_claim_line = (
            stripped_line.startswith("- 确定性事实")
            or stripped_line.startswith("* 确定性事实")
            or stripped_line.startswith("| 确定性事实")
        )
        if is_deterministic_claim_line and any(word in line for word in ("可能", "推断", "猜测", "需要 review")):
            add("P1", "确定性事实行混入推断措辞", f"第 {line_no} 行：{line.strip()}")
        boundary_line = any(word in line for word in ("不得补写", "不补写", "禁止补写", "证据边界"))
        if any(term in line for term in ("always", "寄存器更新语义", "时序保证")) and not boundary_line:
            add("P2", "出现高风险时序/过程逻辑表述", f"第 {line_no} 行包含 `{line.strip()}`，需要确认其来自 evidence_gap 或明确禁止边界。")

    free_mentions = len(re.findall(r"\bfree\b|Free|backpressure|反压", manual))
    if free_mentions > 60:
        add("P2", "free/backpressure 描述过多", f"全文 free/backpressure 相关命中 {free_mentions} 次，可能偏离 drive-centered 主线。")

    conclusion = "通过" if not any(item["severity"] in {"P1", "P2"} for item in findings) else "不通过"
    lines = [
        "# RTL 代码手册审查报告",
        "",
        f"- 审查目标：`{state.get('top_module', '')}`",
        f"- 审查方式：Manual Context 结构化约束检查",
        f"- 总体结论：{conclusion}",
        "",
        "## 检查结果",
    ]
    if findings:
        for item in findings:
            lines.append(f"- {item['severity']} {item['title']}：{item['detail']}")
    else:
        lines.append("- 未发现确定性结构检查项违规。")
    lines.extend([
        "",
        "## 已检查约束",
        "- final manual 不应包含对话式开场。",
        "- final manual 不应把 `manual_ir` 或 ContextPack 作为主证据结构。",
        "- `ai_inferred` 内容必须在手册中标注为 AI 推断。",
        "- `evidence_gap` 必须进入证据缺口或 review 章节。",
        "- `deterministic_fact` 行不得混入“可能/推断/需要 review”等不确定措辞。",
        "- `free` 只作为影响 drive availability/backpressure 的参考，不作为主流程解释入口。",
        "",
        "## 剩余风险",
        "- 本审查器只做结构化和文本边界检查；复杂 RTL 语义仍以 Manual Context 的 evidence_refs 和后续人工 RTL review 为准。",
    ])
    return "\n".join(lines)


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
    manual_output_path = state.get("manual_output_path")
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
    state["last_error"] = ""
