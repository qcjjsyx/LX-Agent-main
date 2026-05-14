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
                f"Manual IR 目录：`{state.get('manual_ir_dir', '')}`",
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

    _normalize_evidence_selection(state)

    state["parser_dir"] = str(Path(state["project_root"]) / "parser_pipeline_rtl")
    if state.get("top_module"):
        state["manual_ir_dir"] = str(
            Path(state["project_root"]) / "manual_ir" / state["top_module"]
        )


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

    if any(word in lower_text for word in ("reading_path", "contextpack", "context_pack")):
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
        "3. Knowledge Tool：读取 `parser_pipeline_rtl/`，生成 `manual_ir/<top_module>/`。",
        "4. Evidence：建立 Manual IR 主证据索引。",
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


def _parser_artifacts_ready(state):
    parser_dir = Path(state["project_root"]) / "parser_pipeline_rtl"
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
    manual_ir_dir = Path(state["manual_ir_dir"])
    required_items = [
        manual_ir_dir / "manifest.json",
        manual_ir_dir / "system_views.json",
        manual_ir_dir / "validation_report.json",
        manual_ir_dir / "module_cards",
        manual_ir_dir / "channel_cards",
        manual_ir_dir / "component_contracts",
        manual_ir_dir / "flow_paths",
        manual_ir_dir / "reading_paths",
    ]
    if state.get("evidence_mode") == READING_PATH_EVIDENCE_MODE:
        required_items.append(manual_ir_dir / "context_pack.json")

    missing = [path for path in required_items if not path.exists()]
    if missing:
        return False, manual_ir_dir, missing

    try:
        manifest = _read_json(manual_ir_dir / "manifest.json")
    except Exception:
        return False, manual_ir_dir, [manual_ir_dir / "manifest.json"]

    if manifest.get("top_module") and manifest.get("top_module") != state.get("top_module"):
        return False, manual_ir_dir, [manual_ir_dir / "manifest.json"]

    return True, manual_ir_dir, []


def _run_knowledge_stage(state, event_logger=None):
    project_root = state["project_root"]
    top_module = state["top_module"]
    audience = state.get("audience", "newcomer")

    ready, manual_ir_dir, missing = _knowledge_artifacts_ready(state)
    if ready and not _force_regenerate(state):
        _log_event(
            event_logger,
            "tool_skip",
            skill=MANUAL_SKILL_NAME,
            tool="run_knowledge_tool",
            reason="manual_ir_artifacts_ready",
            output_dir=str(manual_ir_dir),
        )
        state["knowledge_result"] = f"复用已有 Manual IR 产物：{manual_ir_dir}"
        _mark_stage_done(state, "knowledge")
        state["stage"] = "evidence"
        return _format_reply(
            state,
            "阶段3：Knowledge Tool 已跳过",
            [
                "检测到已有 `manual_ir/<top_module>/` 且关键产物齐全，本次复用已有 Manual IR。",
                f"Manual IR 目录：`{manual_ir_dir}`",
                "",
                "如需重新生成，请在请求中加入 `重新生成`、`强制生成` 或 `覆盖生成`。",
                "",
                _next_stage_hint(state, "阶段4：建立 Manual IR 主证据索引"),
            ],
        )

    args = {
        "project_root": project_root,
        "top_module": top_module,
        "audience": audience,
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
                "Knowledge Tool 没有成功生成 Manual IR。",
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
            "Knowledge Tool 已完成，Manual IR 目录已经记录到状态中。",
            f"Manual IR 目录：`{state.get('manual_ir_dir', '')}`",
            "",
            _next_stage_hint(state, "阶段4：读取 Manual IR / ContextPack 证据"),
            "",
            "```text",
            _clip_text(result, 1800),
            "```",
        ],
    )


def _run_evidence_stage(state, event_logger=None):
    manual_ir_dir = Path(state["manual_ir_dir"])
    context_pack_path = manual_ir_dir / "context_pack.json"
    manifest_path = manual_ir_dir / "manifest.json"
    system_views_path = manual_ir_dir / "system_views.json"

    missing = [
        str(path)
        for path in (manifest_path, system_views_path)
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
                "Manual IR 关键证据文件缺失，因此我不会继续生成项目结构。",
                "缺失文件：",
                *[f"- `{item}`" for item in missing],
            ],
        )

    context_pack = _read_json(context_pack_path) if context_pack_path.exists() else {}
    manifest = _read_json(manifest_path)
    system_views = _read_json(system_views_path)
    digest = _build_manual_evidence_digest(
        manual_ir_dir=manual_ir_dir,
        manifest=manifest,
        system_views=system_views,
        context_pack=context_pack,
        state=state,
    )

    state["evidence_digest"] = digest
    _log_event(
        event_logger,
        "manual_evidence_indexed",
        skill=MANUAL_SKILL_NAME,
        evidence_mode=digest.get("evidence_mode"),
        counts=digest.get("counts"),
        manual_ir_dir=str(manual_ir_dir),
    )
    _mark_stage_done(state, "evidence")
    state["stage"] = "outline"

    return _format_reply(
        state,
        "阶段4：证据读取完成",
        [
            "我已建立 Manual IR 主证据索引。后续目录、章节规划和手册内容只会基于这些证据生成。",
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
        "阶段5完成：已根据 Manual IR 证据生成手册目录。",
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
                "不推断 Manual IR 未提供的 always/FSM/寄存器更新语义。",
                "缺少字段时写明当前 Manual IR 未提供足够证据。",
            ],
        })
    return plan


def _chapter_intent(title, mode):
    if mode == READING_PATH_EVIDENCE_MODE:
        return (
            "按照选定 ReadingPath 给目标读者提供阅读顺序和证据说明。",
            ["说明本章覆盖的 Manual IR 对象", "概括对象职责和风险", "标注 unresolved covers 或证据不足"],
        )

    rules = [
        ("项目总览", "建立完整工程的系统边界、对象规模和全局风险。", ["说明 top module", "列出对象数量", "概括一级模块、组件家族和外部依赖"]),
        ("顶层模块", "解释顶层模块在系统中的职责和直接结构。", ["说明 top module 摘要", "列出直接一级子模块", "说明顶层风险和外部依赖"]),
        ("模块层级", "让读者看到模块之间的父子关系和结构展开方式。", ["按 parent/child 关系组织模块", "列出关键子模块和结构子", "提示证据来自 ModuleCard"]),
        ("一级子模块", "解释主要模块各自承担的功能角色。", ["逐个概括 primary module", "列出 responsibilities/key_interfaces", "列出风险点和待确认项"]),
        ("端口", "说明接口边界、关键 ingress/egress 和外部依赖。", ["汇总 key_interfaces", "说明 external dependencies", "标注 interface_only 边界"]),
        ("Channel", "说明事件、payload、free/backpressure 的通道事实。", ["按 scope_module 分组", "说明 producer/consumer/payload/handshake", "保留 warning"]),
        ("Flow Path", "说明关键事件/数据/控制路径。", ["列出 startpoints/steps/endpoints", "说明 branch/join/blocking 点", "标注 partial 或 low-confidence flow"]),
        ("Component Contract", "说明结构子 family 的协议和阻塞规则。", ["按 family 分组", "解释 role_mapping/semantic_contract/release_rule", "说明 backpressure behavior"]),
        ("阅读路径", "把 Manual IR 中的 reading_paths 作为附录建议，而不是主结构。", ["列出 newcomer/maintainer/reviewer 目标", "说明各路径适用场景", "提示 defer/risk reminders"]),
        ("维护", "给维护者和审查者提供修改影响面与风险入口。", ["汇总 module risk_points", "汇总 warning/low-confidence flow", "给出回归关注点"]),
        ("证据边界", "明确哪些内容由 Manual IR 支持，哪些不能推断。", ["列出 evidence_boundary", "列出 global_risks", "说明 parser 当前不证明 FSM/always/register 行为"]),
    ]
    for keyword, purpose, points in rules:
        if keyword in title:
            return purpose, points
    return "基于 Manual IR 证据解释本章主题。", ["概括相关对象", "说明关键字段", "标注证据不足"]


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
            "model_start",
            skill=MANUAL_SKILL_NAME,
            stage="manual",
            model=model,
        )
        manual = _generate_manual_markdown(state, client, model)
    except Exception as exc:
        _log_event(
            event_logger,
            "model_end",
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
                "模型生成 Markdown 手册时失败，流程已停在 `manual` 阶段。",
                "Manual IR 证据和目录规划已经保存在会话状态中，修正模型/API 问题后可以发送 `继续` 重试。",
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
        "model_end",
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
            "model_start",
            skill=MANUAL_SKILL_NAME,
            stage="review",
            model=model,
            manual_path=str(manual_path),
        )
        review = _review_manual_markdown(state, client, model)
    except Exception as exc:
        _log_event(
            event_logger,
            "model_end",
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
                "模型审查手册时失败，流程已停在 `review` 阶段。",
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
        "model_end",
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


def _build_manual_evidence_digest(manual_ir_dir, manifest, system_views, context_pack, state):
    if state.get("evidence_mode") == READING_PATH_EVIDENCE_MODE:
        return _build_reading_path_evidence_digest_from_split(
            manual_ir_dir=manual_ir_dir,
            manifest=manifest,
            system_views=system_views,
            context_pack=context_pack,
            audience=state.get("audience", "newcomer"),
        )

    return _build_project_evidence_digest(
        manual_ir_dir=manual_ir_dir,
        manifest=manifest,
        system_views=system_views,
        context_pack=context_pack,
    )


def _build_project_evidence_digest(manual_ir_dir, manifest, system_views, context_pack):
    module_cards = _load_split_group(manual_ir_dir, manifest, "module_cards")
    channel_cards = _load_split_group(manual_ir_dir, manifest, "channel_cards")
    component_contracts = _load_split_group(manual_ir_dir, manifest, "component_contracts")
    flow_paths = _load_split_group(manual_ir_dir, manifest, "flow_paths")
    reading_paths = _load_split_group(manual_ir_dir, manifest, "reading_paths")
    semantic_module_cards = _load_split_group(manual_ir_dir, manifest, "semantic_module_cards")
    system_view = system_views[0] if isinstance(system_views, list) and system_views else {}

    return {
        "evidence_mode": PROJECT_EVIDENCE_MODE,
        "manual_kind": "complete_project_code_manual",
        "top_module": manifest.get("top_module", ""),
        "manual_ir_dir": str(manual_ir_dir),
        "counts": manifest.get("counts", {}),
        "system_view": _summarize_system_view(system_view),
        "modules": [_summarize_module_card(item) for item in module_cards],
        "semantic_modules": [_summarize_semantic_module_card(item) for item in semantic_module_cards],
        "channels": {
            "count": len(channel_cards),
            "by_scope_module": _count_by(channel_cards, "scope_module"),
            "samples": [_summarize_channel_card(item) for item in channel_cards[:40]],
        },
        "component_contracts": {
            "count": len(component_contracts),
            "by_family": _count_by(component_contracts, "family"),
            "representatives": _representative_contracts(component_contracts),
        },
        "flow_paths": {
            "count": len(flow_paths),
            "by_scope_module": _count_by(flow_paths, "scope_module"),
            "samples": [_summarize_flow_path(item) for item in flow_paths[:60]],
            "warning_or_low_confidence": [
                _summarize_flow_path(item)
                for item in flow_paths
                if item.get("warnings") or item.get("confidence") == "low"
            ][:40],
        },
        "reading_paths": [_summarize_reading_path(item) for item in reading_paths],
        "context_pack_reference": {
            "reading_path": (context_pack or {}).get("reading_path", {}),
            "warnings": (context_pack or {}).get("warnings", []),
        },
        "warnings": manifest.get("warnings", []),
        "evidence_boundary": [
            "主证据为完整 split Manual IR，不以 newcomer ContextPack 作为手册主结构。",
            "可以使用 ReadingPath 作为阅读建议章节，但不能把 ReadingPath 当作项目总目录。",
            "不得补写 Manual IR 中不存在的模块、接口、通道、FSM、always 行为或寄存器更新条件。",
            "遇到 partial/low-confidence/warnings 必须保留证据边界。",
        ],
    }


def _build_reading_path_evidence_digest_from_split(
    manual_ir_dir,
    manifest,
    system_views,
    context_pack,
    audience,
):
    reading_paths = _load_split_group(manual_ir_dir, manifest, "reading_paths")
    selected = next(
        (item for item in reading_paths if item.get("audience") == audience),
        reading_paths[0] if reading_paths else {},
    )

    if context_pack and context_pack.get("reading_path", {}).get("audience") == audience:
        return _build_evidence_digest(context_pack, manifest, system_views)

    catalog = _build_manifest_catalog(manual_ir_dir, manifest, system_views)
    sections = []
    for section in selected.get("ordered_sections", []):
        covered = []
        unresolved = []
        for object_id in section.get("covers", []):
            obj = catalog.get(object_id)
            if obj:
                covered.append(_summarize_manual_object(obj))
            else:
                unresolved.append(object_id)
        sections.append({
            "section_id": section.get("section_id", ""),
            "title": section.get("title", ""),
            "covers": section.get("covers", []),
            "covered_objects": covered,
            "warnings": [],
            "unresolved_covers": unresolved,
        })

    system_view = system_views[0] if isinstance(system_views, list) and system_views else {}
    return {
        "evidence_mode": READING_PATH_EVIDENCE_MODE,
        "manual_kind": f"{audience}_reading_guide",
        "top_module": manifest.get("top_module", ""),
        "manual_ir_dir": str(manual_ir_dir),
        "counts": manifest.get("counts", {}),
        "reading_path": _summarize_reading_path(selected),
        "system_view": _summarize_system_view(system_view),
        "sections": sections,
        "warnings": [],
        "evidence_boundary": [
            f"主证据为 {audience} ReadingPath，只适合生成阅读指南或局部指南。",
            "不得把阅读路径指南伪装成完整项目代码手册。",
        ],
    }


def _build_evidence_digest(context_pack, manifest, system_views):
    system_view = system_views[0] if isinstance(system_views, list) and system_views else {}
    reading_path = context_pack.get("reading_path", {})
    sections = []

    for item in context_pack.get("sections", []):
        section = item.get("section", {})
        covered = []
        for obj in item.get("covered_objects", []):
            covered.append({
                "id": obj.get("id", ""),
                "kind": obj.get("kind", ""),
                "title": obj.get("title", ""),
                "summary": obj.get("summary", ""),
                "module_name": obj.get("module_name", ""),
                "component_name": obj.get("component_name", ""),
                "family": obj.get("family", ""),
                "confidence": obj.get("confidence", ""),
                "warnings": obj.get("warnings", []),
            })
        semantic_overlays = [
            _summarize_semantic_module_card(obj)
            for obj in item.get("semantic_overlays", [])
            if isinstance(obj, dict)
        ]

        sections.append({
            "section_id": section.get("section_id", ""),
            "title": section.get("title", ""),
            "covers": section.get("covers", []),
            "covered_objects": covered,
            "semantic_overlays": semantic_overlays,
            "warnings": item.get("warnings", []),
            "unresolved_covers": item.get("unresolved_covers", []),
        })

    return {
        "top_module": context_pack.get("top_module") or manifest.get("top_module", ""),
        "manual_ir_dir": context_pack.get("manual_ir_dir", ""),
        "counts": manifest.get("counts", {}),
        "reading_path": {
            "id": reading_path.get("id", ""),
            "audience": reading_path.get("audience", ""),
            "title": reading_path.get("title", ""),
            "summary": reading_path.get("summary", ""),
            "goals": reading_path.get("goals", []),
            "must_cover": reading_path.get("must_cover", []),
            "defer_sections": reading_path.get("defer_sections", []),
            "risk_reminders": reading_path.get("risk_reminders", []),
        },
        "system_view": {
            "id": system_view.get("id", ""),
            "summary": system_view.get("summary", ""),
            "primary_modules": system_view.get("primary_modules", []),
            "primary_components": system_view.get("primary_components", []),
            "families_used": system_view.get("families_used", []),
            "external_dependencies": system_view.get("external_dependencies", []),
            "global_risks": system_view.get("global_risks", []),
            "confidence": system_view.get("confidence", ""),
        },
        "sections": sections,
        "warnings": context_pack.get("warnings", []),
        "evidence_boundary": context_pack.get("evidence_boundary", []),
    }


def _load_split_group(manual_ir_dir, manifest, group):
    files = manifest.get("files", {}).get(group, {})
    if not isinstance(files, dict):
        return []

    items = []
    for _, rel_path in sorted(files.items()):
        if isinstance(rel_path, str):
            path = Path(manual_ir_dir) / rel_path
            if path.exists():
                items.append(_read_json(path))
    return items


def _build_manifest_catalog(manual_ir_dir, manifest, system_views):
    catalog = {}
    for item in system_views if isinstance(system_views, list) else []:
        if item.get("id"):
            catalog[item["id"]] = item
    for group in ("module_cards", "semantic_module_cards", "channel_cards", "component_contracts", "flow_paths", "reading_paths"):
        for item in _load_split_group(manual_ir_dir, manifest, group):
            if item.get("id"):
                catalog[item["id"]] = item
    return catalog


def _summarize_manual_object(obj):
    kind = obj.get("kind", "")
    if kind == "module_card":
        return _summarize_module_card(obj)
    if kind == "semantic_module_card":
        return _summarize_semantic_module_card(obj)
    if kind == "channel_card":
        return _summarize_channel_card(obj)
    if kind == "component_contract":
        return _summarize_component_contract(obj)
    if kind == "flow_path":
        return _summarize_flow_path(obj)
    if kind == "system_view":
        return _summarize_system_view(obj)
    if kind == "reading_path":
        return _summarize_reading_path(obj)
    return {
        "id": obj.get("id", ""),
        "kind": kind,
        "title": obj.get("title", ""),
        "summary": obj.get("summary", ""),
        "confidence": obj.get("confidence", ""),
        "warnings": obj.get("warnings", []),
    }


def _summarize_system_view(item):
    return {
        "id": item.get("id", ""),
        "summary": item.get("summary", ""),
        "primary_modules": item.get("primary_modules", []),
        "primary_components": item.get("primary_components", []),
        "families_used": item.get("families_used", []),
        "external_dependencies": item.get("external_dependencies", []),
        "global_risks": item.get("global_risks", []),
        "confidence": item.get("confidence", ""),
    }


def _summarize_module_card(item):
    return {
        "id": item.get("id", ""),
        "kind": item.get("kind", ""),
        "module_name": item.get("module_name", ""),
        "title": item.get("title", ""),
        "summary": item.get("summary", ""),
        "module_role": item.get("module_role", ""),
        "document_role": item.get("document_role", ""),
        "parent_modules": item.get("parent_modules", []),
        "responsibilities": item.get("responsibilities", []),
        "key_interfaces": item.get("key_interfaces", {}),
        "child_modules": item.get("child_modules", []),
        "child_components": item.get("child_components", []),
        "key_component_roles": item.get("key_component_roles", []),
        "internal_flow_paths": item.get("internal_flow_paths", []),
        "backpressure_points": item.get("backpressure_points", []),
        "risk_points": item.get("risk_points", []),
        "confidence": item.get("confidence", ""),
        "warnings": item.get("warnings", []),
    }


def _summarize_semantic_module_card(item):
    return {
        "id": item.get("id", ""),
        "kind": item.get("kind", ""),
        "module_name": item.get("module_name", ""),
        "purpose": item.get("purpose", {}),
        "key_behaviors": item.get("key_behaviors", []),
        "important_signals": item.get("important_signals", []),
        "payload_semantics": item.get("payload_semantics", []),
        "handshake_notes": item.get("handshake_notes", []),
        "control_flow_notes": item.get("control_flow_notes", []),
        "state_or_register_behavior": item.get("state_or_register_behavior", []),
        "evidence_gaps": item.get("evidence_gaps", []),
        "input_hash": item.get("input_hash", ""),
    }


def _summarize_channel_card(item):
    return {
        "id": item.get("id", ""),
        "scope_module": item.get("scope_module", ""),
        "channel_name": item.get("channel_name", ""),
        "channel_type": item.get("channel_type", ""),
        "summary": item.get("summary", ""),
        "producer": item.get("producer", {}),
        "consumer": item.get("consumer", {}),
        "payload": item.get("payload", {}),
        "handshake": item.get("handshake", {}),
        "conditioning": item.get("conditioning", {}),
        "related_flow_paths": item.get("related_flow_paths", []),
        "confidence": item.get("confidence", ""),
        "warnings": item.get("warnings", []),
    }


def _summarize_component_contract(item):
    return {
        "id": item.get("id", ""),
        "component_name": item.get("component_name", ""),
        "family": item.get("family", ""),
        "instance_scope": item.get("instance_scope", ""),
        "summary": item.get("summary", ""),
        "role_mapping": item.get("role_mapping", {}),
        "semantic_contract": item.get("semantic_contract", {}),
        "release_rule": item.get("release_rule", {}),
        "backpressure_behavior": item.get("backpressure_behavior", {}),
        "family_invariants": item.get("family_invariants", []),
        "used_in_channels": item.get("used_in_channels", []),
        "confidence": item.get("confidence", ""),
        "warnings": item.get("warnings", []),
    }


def _summarize_flow_path(item):
    return {
        "id": item.get("id", ""),
        "scope_module": item.get("scope_module", ""),
        "path_type": item.get("path_type", ""),
        "title": item.get("title", ""),
        "summary": item.get("summary", ""),
        "startpoints": item.get("startpoints", []),
        "endpoints": item.get("endpoints", []),
        "steps": item.get("steps", []),
        "branch_points": item.get("branch_points", []),
        "join_points": item.get("join_points", []),
        "blocking_points": item.get("blocking_points", []),
        "covered_channels": item.get("covered_channels", []),
        "confidence": item.get("confidence", ""),
        "warnings": item.get("warnings", []),
    }


def _summarize_reading_path(item):
    return {
        "id": item.get("id", ""),
        "audience": item.get("audience", ""),
        "title": item.get("title", ""),
        "summary": item.get("summary", ""),
        "goals": item.get("goals", []),
        "ordered_sections": item.get("ordered_sections", []),
        "must_cover": item.get("must_cover", []),
        "defer_sections": item.get("defer_sections", []),
        "risk_reminders": item.get("risk_reminders", []),
    }


def _representative_contracts(contracts):
    reps = []
    counts = {}
    for item in contracts:
        family = item.get("family", "unknown")
        if counts.get(family, 0) >= 3:
            continue
        reps.append(_summarize_component_contract(item))
        counts[family] = counts.get(family, 0) + 1
    return reps


def _count_by(items, key):
    counts = {}
    for item in items:
        value = item.get(key) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def _format_digest(digest):
    counts = digest.get("counts", {})
    system_view = digest.get("system_view", {})
    reading_path = digest.get("reading_path", {})
    primary_modules = system_view.get("primary_modules", [])
    families = system_view.get("families_used", [])

    lines = [
        "## 证据摘要",
        f"- 主证据模式：`{digest.get('evidence_mode', PROJECT_EVIDENCE_MODE)}` / `{digest.get('manual_kind', '')}`",
        f"- top_module：`{digest.get('top_module', '')}`",
        f"- 对象数量：{json.dumps(counts, ensure_ascii=False)}",
        f"- 一级模块：{', '.join(_name_of(item, 'module') for item in primary_modules) or '证据未提供'}",
        f"- 组件家族：{', '.join(families) or '证据未提供'}",
    ]
    if reading_path:
        lines.append(f"- reading_path：`{reading_path.get('id', '')}` / `{reading_path.get('audience', '')}`")
    if digest.get("modules"):
        lines.append(f"- 模块卡片摘要：{len(digest.get('modules', []))} 个")
    if digest.get("sections"):
        lines.append(f"- 阅读路径章节数量：{len(digest.get('sections', []))}")
    risks = system_view.get("global_risks", [])
    if risks:
        lines.append("- 风险/边界：" + "；".join(risks[:5]))
    return "\n".join(lines)


def _build_outline(digest):
    if digest.get("evidence_mode") == PROJECT_EVIDENCE_MODE:
        top_module = digest.get("top_module", "top_module")
        return [
            {"title": "项目总览", "evidence": ["system_view", "manifest.counts"]},
            {"title": f"顶层模块 {top_module}", "evidence": ["system_view.primary_modules", f"module:{top_module}"]},
            {"title": "模块层级结构", "evidence": ["modules.parent_modules", "modules.child_modules", "modules.child_components"]},
            {"title": "一级子模块与关键功能模块", "evidence": ["system_view.primary_modules", "modules.responsibilities"]},
            {"title": "端口、接口与边界依赖", "evidence": ["modules.key_interfaces", "system_view.external_dependencies"]},
            {"title": "Channel 与握手机制", "evidence": ["channels.samples", "channels.by_scope_module"]},
            {"title": "Flow Path 数据流与控制流", "evidence": ["flow_paths.samples", "flow_paths.warning_or_low_confidence"]},
            {"title": "Component Contract 组件协议", "evidence": ["component_contracts.representatives", "component_contracts.by_family"]},
            {"title": "阅读路径建议", "evidence": ["reading_paths"]},
            {"title": "维护建议与审查重点", "evidence": ["modules.risk_points", "flow_paths.warning_or_low_confidence"]},
            {"title": "证据边界与风险点", "evidence": ["evidence_boundary", "system_view.global_risks", "warnings"]},
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
            "evidence": ["context_pack.evidence_boundary", "system_view.global_risks"],
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
    digest = state.get("evidence_digest") or {}
    outline = state.get("outline") or _build_outline(digest)
    chapter_plan = state.get("chapter_plan") or _build_chapter_plan(outline, digest)

    prompt = (
        "你是 RTL 项目代码手册写作助手。必须只使用用户提供的 JSON 证据摘要写作，"
        "不得编造模块、目录、接口、通道、状态机、寄存器行为或项目结构。"
        "如果证据不足，明确写“当前 Manual IR 未提供足够证据”。"
        "如果 evidence_mode=project，必须生成完整项目代码手册，不要写成 newcomer/maintainer/reviewer 阅读指南；"
        "ReadingPath 只能作为“阅读路径建议”章节使用。"
        "输出 Markdown。\n\n"
        "【证据摘要 JSON】\n"
        f"{json.dumps(digest, ensure_ascii=False, indent=2)}\n\n"
        "【目录 JSON】\n"
        f"{json.dumps(outline, ensure_ascii=False, indent=2)}\n\n"
        "【每章内容规划 JSON】\n"
        f"{json.dumps(chapter_plan, ensure_ascii=False, indent=2)}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你根据结构化证据写完整 RTL 项目代码手册。"
                    "没有证据的内容必须标注证据不足，禁止补全不存在的工程结构。"
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return response.choices[0].message.content or ""


def _review_manual_markdown(state, client, model):
    digest = state.get("evidence_digest") or {}
    outline = state.get("outline") or []
    chapter_plan = state.get("chapter_plan") or []
    manual_path = Path(state.get("manual_output_path", ""))
    manual = manual_path.read_text(encoding="utf-8")

    prompt = (
        "请审查下面这份 RTL 代码手册。审查目标：\n"
        "1. 是否只基于 Manual IR 证据写作；\n"
        "2. 是否错误地把 ReadingPath/newcomer 指南当成完整项目手册；\n"
        "3. 是否编造了模块、接口、通道、FSM、always、寄存器更新条件；\n"
        "4. 是否遗漏 warnings、external_dependencies、partial/low-confidence flow；\n"
        "5. 每章是否符合章节规划。\n\n"
        "请输出 Markdown 审查报告，包含：总体结论、发现的问题、建议修正、剩余风险。\n\n"
        "【证据摘要 JSON】\n"
        f"{json.dumps(digest, ensure_ascii=False, indent=2)}\n\n"
        "【目录 JSON】\n"
        f"{json.dumps(outline, ensure_ascii=False, indent=2)}\n\n"
        "【章节规划 JSON】\n"
        f"{json.dumps(chapter_plan, ensure_ascii=False, indent=2)}\n\n"
        "【待审查手册 Markdown】\n"
        f"{manual}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是严格的技术手册审查器。只根据给定证据审查，不新增手册事实。"
                    "发现没有证据支撑的内容必须指出。"
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return response.choices[0].message.content or ""


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
        "",
        f"## {title}",
        "",
    ]
    return "\n".join(header + list(lines)).strip()


def _tool_failed(result):
    lower_result = (result or "").lower()
    return (
        "failed" in lower_result
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


def _name_of(item, key):
    if isinstance(item, dict):
        return str(item.get(key, ""))
    return str(item)
