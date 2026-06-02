# backend/app.py
import os
import json
import re
import threading
import uuid
import zipfile
import shutil
from dataclasses import asdict
from pathlib import Path
from datetime import datetime

import dotenv
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

try:
    from openai import OpenAI
except ImportError:  # Web routes that do not call the model should still import.
    OpenAI = None

try:
    from .agent_runner import AgentRunner, AgentSession
    from .tools import select_tools_for_task
    from .context_manager import maybe_compress_context
    from .manual_workflow import handle_manual_workflow, should_handle_manual_workflow
    from .event_logger import log_event, read_events
    from .workflows.runtime import WorkflowRuntime
    from .workflows.types import WorkflowContext
except ImportError:
    from agent_runner import AgentRunner, AgentSession
    from tools import select_tools_for_task
    from context_manager import maybe_compress_context
    from manual_workflow import handle_manual_workflow, should_handle_manual_workflow
    from event_logger import log_event, read_events
    from workflows.runtime import WorkflowRuntime
    from workflows.types import WorkflowContext

dotenv.load_dotenv()

MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


def build_model_client():
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if OpenAI is None or not api_key:
        return None
    return OpenAI(
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL,
    )


client = build_model_client()

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"

app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR / "templates"),
    static_folder=str(FRONTEND_DIR / "static")
)


# ====================== 文件上传 / 路径导入配置 ======================

IMPORT_DIR = DATA_DIR / "imports"
IMPORT_DIR.mkdir(parents=True, exist_ok=True)

ARCHIVE_DIR = IMPORT_DIR / "_archives"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

# 浏览器上传最大 100MB
# 大文件建议使用“路径导入”，不走浏览器上传
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

ALLOWED_UPLOAD_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".py",
    ".html",
    ".css",
    ".js",
    ".v",
    ".sv",
    ".vh",
    ".log",
    ".csv",
    ".zip"
}

ALLOWED_EXTRACT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".py",
    ".html",
    ".css",
    ".js",
    ".v",
    ".sv",
    ".vh",
    ".log",
    ".csv"
}

MAX_ZIP_FILES = 2000
MAX_ZIP_TOTAL_SIZE = 500 * 1024 * 1024


# ====================== 聊天记录配置 ======================

CONVERSATION_DIR = DATA_DIR / "conversations"
CONVERSATION_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "你是一个网页版 AI Agent。"
        "你可以根据用户任务调用本轮激活的工具。"
        "如果本轮已经激活了某个 skill，并且用户的问题明显可以由该 skill 的 tool 完成，必须优先调用 tool。"
        "如果没有合适工具，就直接用文字回答。"
        "回答要清晰，适合新手理解。"
    )
}

current_conversation_id = None
messages = [SYSTEM_MESSAGE]
manual_workflow_state = None
CONVERSATION_ID_RE = re.compile(r"^chat_\d{8}_\d{6}_[0-9a-f]{6}$")
STATE_LOCK = threading.RLock()
CONVERSATION_LOCKS = {}
agent_runner = AgentRunner(
    client=client,
    model=MODEL,
    base_dir=BASE_DIR,
    system_message=SYSTEM_MESSAGE,
)
workflow_runtime = WorkflowRuntime()


# ====================== 基础函数 ======================

def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def make_conversation_id():
    return "chat_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]


def validate_conversation_id(conversation_id):
    if not isinstance(conversation_id, str) or not CONVERSATION_ID_RE.fullmatch(conversation_id):
        raise ValueError("Invalid conversation_id.")
    return conversation_id


def conversation_path(conversation_id):
    conversation_id = validate_conversation_id(conversation_id)
    path = (CONVERSATION_DIR / f"{conversation_id}.json").resolve()
    base_dir = CONVERSATION_DIR.resolve()

    try:
        path.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError("Invalid conversation_id path.") from exc

    return path


def get_conversation_lock(conversation_id):
    conversation_id = validate_conversation_id(conversation_id)
    with STATE_LOCK:
        lock = CONVERSATION_LOCKS.get(conversation_id)
        if lock is None:
            lock = threading.RLock()
            CONVERSATION_LOCKS[conversation_id] = lock
        return lock


def message_to_dict(message):
    if isinstance(message, dict):
        return message

    if hasattr(message, "model_dump"):
        return message.model_dump()

    return {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", "")
    }


def sanitize_messages_for_api(raw_messages):
    """
    清洗 messages，避免出现孤立 tool 消息导致 400 错误。
    """
    clean_messages = []
    pending_tool_call_ids = set()

    for raw_msg in raw_messages:
        msg = message_to_dict(raw_msg)
        role = msg.get("role")

        if role in ["system", "user"]:
            clean_messages.append(msg)
            pending_tool_call_ids = set()
            continue

        if role == "assistant":
            clean_messages.append(msg)
            pending_tool_call_ids = set()

            tool_calls = msg.get("tool_calls") or []

            for tool_call in tool_calls:
                if isinstance(tool_call, dict):
                    tool_call_id = tool_call.get("id")
                else:
                    tool_call_id = getattr(tool_call, "id", None)

                if tool_call_id:
                    pending_tool_call_ids.add(tool_call_id)

            continue

        if role == "tool":
            tool_call_id = msg.get("tool_call_id")

            if tool_call_id in pending_tool_call_ids:
                clean_messages.append(msg)
                pending_tool_call_ids.remove(tool_call_id)
            else:
                print(f"⚠️ 跳过孤立 tool 消息：{tool_call_id}")

            continue

    return clean_messages


def visible_messages_only(raw_messages):
    result = []

    for msg in raw_messages:
        msg = message_to_dict(msg)

        role = msg.get("role")
        content = msg.get("content") or ""

        if role in ["user", "assistant"] and content.strip():
            result.append({
                "role": role,
                "content": content
            })

    return result


def get_title_from_messages(raw_messages):
    for msg in raw_messages:
        msg = message_to_dict(msg)

        if msg.get("role") == "user":
            text = msg.get("content", "").strip()

            if text:
                return text[:24] + ("..." if len(text) > 24 else "")

    return "新对话"


def create_new_conversation():
    global current_conversation_id, messages, manual_workflow_state

    with STATE_LOCK:
        previous_conversation_id = current_conversation_id
        current_conversation_id = make_conversation_id()
        messages = [SYSTEM_MESSAGE]
        manual_workflow_state = None

    save_conversation_state(current_conversation_id, messages, manual_workflow_state)
    log_event(
        current_conversation_id,
        "conversation_created",
        previous_conversation_id=previous_conversation_id,
    )

    return current_conversation_id


def save_conversation_state(conversation_id, conversation_messages, workflow_state):
    conversation_id = validate_conversation_id(conversation_id)
    path = conversation_path(conversation_id)
    created_at = now_text()
    title = get_title_from_messages(conversation_messages)
    manual_title = False

    if path.exists():
        try:
            old_data = json.loads(path.read_text(encoding="utf-8"))
            created_at = old_data.get("created_at", created_at)

            if old_data.get("manual_title"):
                title = old_data.get("title", title)
                manual_title = True

        except Exception:
            pass

    safe_messages = sanitize_messages_for_api(conversation_messages)

    data = {
        "id": conversation_id,
        "title": title,
        "manual_title": manual_title,
        "created_at": created_at,
        "updated_at": now_text(),
        "messages": [message_to_dict(m) for m in safe_messages],
        "manual_workflow_state": workflow_state
    }

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def load_conversation_state(conversation_id):
    conversation_id = validate_conversation_id(conversation_id)
    path = conversation_path(conversation_id)

    if not path.exists():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))

    workflow_state = data.get("manual_workflow_state")
    loaded_messages = data.get("messages", [])

    if not loaded_messages:
        loaded_messages = [SYSTEM_MESSAGE]
    else:
        loaded_messages = sanitize_messages_for_api(loaded_messages)

        if not loaded_messages or loaded_messages[0].get("role") != "system":
            loaded_messages.insert(0, SYSTEM_MESSAGE)

    return loaded_messages, workflow_state


def save_current_conversation():
    global current_conversation_id, messages, manual_workflow_state

    with STATE_LOCK:
        if current_conversation_id is None:
            return
        conversation_id = current_conversation_id
        conversation_messages = list(messages)
        workflow_state = manual_workflow_state

    save_conversation_state(conversation_id, conversation_messages, workflow_state)


def load_conversation(conversation_id):
    global current_conversation_id, messages, manual_workflow_state

    with get_conversation_lock(conversation_id):
        loaded = load_conversation_state(conversation_id)
        if loaded is None:
            return False
        loaded_messages, workflow_state = loaded

    with STATE_LOCK:
        current_conversation_id = validate_conversation_id(conversation_id)
        messages = loaded_messages
        manual_workflow_state = workflow_state

    log_event(
        current_conversation_id,
        "conversation_loaded",
        message_count=len(messages),
        has_manual_workflow=bool(manual_workflow_state),
        workflow_stage=(manual_workflow_state or {}).get("stage"),
    )

    return True


def list_conversations():
    items = []

    for path in CONVERSATION_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            items.append({
                "id": data.get("id", path.stem),
                "title": data.get("title", "未命名对话"),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
            })

        except Exception:
            continue

    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    return items


# ====================== 上传 / 解压辅助函数 ======================

def is_allowed_upload(filename):
    suffix = Path(filename).suffix.lower()
    return suffix in ALLOWED_UPLOAD_EXTENSIONS


def is_allowed_extract_file(filename):
    suffix = Path(filename).suffix.lower()
    return suffix in ALLOWED_EXTRACT_EXTENSIONS


def make_safe_upload_name(original_filename):
    suffix = Path(original_filename).suffix.lower()
    stem = Path(original_filename).stem

    safe_stem = secure_filename(stem)

    if not safe_stem:
        safe_stem = "uploaded_file"

    unique_id = uuid.uuid4().hex[:8]

    return f"{safe_stem}_{unique_id}{suffix}"


def make_safe_folder_name(original_filename):
    stem = Path(original_filename).stem
    safe_stem = secure_filename(stem)

    if not safe_stem:
        safe_stem = "uploaded_folder"

    unique_id = uuid.uuid4().hex[:8]

    return f"{safe_stem}_{unique_id}"


def safe_join(base_dir, relative_path):
    """
    安全拼接路径，防止 zip slip。
    """
    base_dir = Path(base_dir).resolve()
    target_path = (base_dir / relative_path).resolve()

    if not str(target_path).startswith(str(base_dir)):
        raise ValueError("检测到危险路径，已阻止解压。")

    return target_path


def sanitize_zip_member_path(member_name):
    """
    清洗 zip 内部路径。
    """
    parts = []

    for part in Path(member_name).parts:
        if part in ["", ".", ".."]:
            continue

        safe_part = secure_filename(part)

        if safe_part:
            parts.append(safe_part)

    if not parts:
        return None

    return Path(*parts)


def extract_zip_safely(zip_path, extract_dir):
    """
    安全解压 zip 文件。
    """
    extracted_files = []
    skipped_files = []

    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    if not zipfile.is_zipfile(zip_path):
        return {
            "ok": False,
            "error": "这不是有效的 zip 文件。",
            "extracted_files": [],
            "skipped_files": []
        }

    total_size = 0

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            members = zip_ref.infolist()

            if len(members) > MAX_ZIP_FILES:
                return {
                    "ok": False,
                    "error": f"zip 内文件数量过多，最多允许 {MAX_ZIP_FILES} 个文件。",
                    "extracted_files": [],
                    "skipped_files": []
                }

            for member in members:
                if member.is_dir():
                    continue

                original_name = member.filename

                if original_name.startswith("__MACOSX/"):
                    skipped_files.append({
                        "filename": original_name,
                        "reason": "系统隐藏文件，已跳过"
                    })
                    continue

                total_size += member.file_size

                if total_size > MAX_ZIP_TOTAL_SIZE:
                    return {
                        "ok": False,
                        "error": "zip 解压后文件总大小超过限制。",
                        "extracted_files": extracted_files,
                        "skipped_files": skipped_files
                    }

                if not is_allowed_extract_file(original_name):
                    skipped_files.append({
                        "filename": original_name,
                        "reason": "zip 内文件类型不支持，已跳过"
                    })
                    continue

                safe_relative_path = sanitize_zip_member_path(original_name)

                if safe_relative_path is None:
                    skipped_files.append({
                        "filename": original_name,
                        "reason": "文件名无效，已跳过"
                    })
                    continue

                try:
                    target_path = safe_join(extract_dir, safe_relative_path)
                except Exception as e:
                    skipped_files.append({
                        "filename": original_name,
                        "reason": str(e)
                    })
                    continue

                target_path.parent.mkdir(parents=True, exist_ok=True)

                with zip_ref.open(member, "r") as source:
                    with open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)

                extracted_files.append({
                    "original_name": original_name,
                    "saved_path": str(target_path).replace("\\", "/")
                })

        return {
            "ok": True,
            "error": "",
            "extracted_files": extracted_files,
            "skipped_files": skipped_files
        }

    except Exception as e:
        return {
            "ok": False,
            "error": f"zip 解压失败：{str(e)}",
            "extracted_files": extracted_files,
            "skipped_files": skipped_files
        }


def copy_file_to_imports(source_path):
    """
    通过路径导入普通文件。
    """
    safe_name = make_safe_upload_name(source_path.name)
    target_path = IMPORT_DIR / safe_name

    with open(source_path, "rb") as src:
        with open(target_path, "wb") as dst:
            shutil.copyfileobj(src, dst)

    return target_path


# ====================== 模型调用 ======================

def call_model(active_messages, active_tools):
    safe_messages = sanitize_messages_for_api(active_messages)

    params = {
        "model": MODEL,
        "messages": safe_messages
    }

    if active_tools:
        params["tools"] = active_tools
        params["tool_choice"] = "auto"

    return client.chat.completions.create(**params) # type: ignore


def build_debug_tip(active_skill_names, used_tools):
    lines = []

    if active_skill_names:
        lines.append(f"【已激活 Skill：{', '.join(active_skill_names)}】")
    else:
        lines.append("【未激活 Skill】")

    if used_tools:
        lines.append(f"【已使用 Tool：{', '.join(used_tools)}】")
    else:
        lines.append("【未使用 Tool：模型直接回答】")

    return "\n".join(lines)


def build_skill_context(active_skill_instructions, active_reference_files):
    if not active_skill_instructions and not active_reference_files:
        return None

    parts = []

    if active_skill_instructions:
        parts.extend(active_skill_instructions)

    if active_reference_files:
        reference_text = "本轮触发的 skill 需要优先读取以下 reference 文件：\n"

        for path in active_reference_files:
            reference_text += f"- {path}\n"

        reference_text += (
            "\n请先使用 read_file 逐个读取这些 reference 文件。"
            "如果文件不存在，请说明缺失并继续读取其他 reference。"
            "读取完成后，再根据这些文档理解 parser tool 和 knowledge tool 的职责。"
        )

        parts.append(reference_text)

    return "\n\n".join(parts)


# ====================== Agent 单轮执行 ======================

def _legacy_run_agent_once(user_input):
    global messages, manual_workflow_state

    if not user_input.strip():
        return "请输入内容。"

    if current_conversation_id is None:
        create_new_conversation()

    log_event(
        current_conversation_id,
        "chat_request",
        message=user_input,
    )

    if should_handle_manual_workflow(user_input, manual_workflow_state):
        log_event(
            current_conversation_id,
            "skill_selected",
            skill="rtl-manual-generation",
            reason="manual_workflow",
            current_stage=(manual_workflow_state or {}).get("stage"),
        )

        messages.append({
            "role": "user",
            "content": user_input
        })

        reply, manual_workflow_state = handle_manual_workflow(
            user_input=user_input,
            state=manual_workflow_state,
            base_dir=BASE_DIR,
            client=client,
            model=MODEL,
            event_logger=lambda event_type, **payload: log_event(
                current_conversation_id,
                event_type,
                **payload
            ),
        )

        messages.append({
            "role": "assistant",
            "content": reply
        })

        save_current_conversation()

        log_event(
            current_conversation_id,
            "assistant_response",
            skills=["rtl-manual-generation"],
            used_tools=[],
            workflow_stage=manual_workflow_state.get("stage") if manual_workflow_state else None,
            reply_preview=reply[:1200],
        )

        return reply

    (
        active_tools,
        active_handlers,
        active_skill_names,
        active_skill_instructions,
        active_reference_files
    ) = select_tools_for_task(user_input)

    log_event(
        current_conversation_id,
        "skill_selection",
        skills=active_skill_names,
        tools=[tool["function"]["name"] for tool in active_tools],
        reference_files=active_reference_files,
    )

    used_tools = []

    print("\n🧩 Reference Skill Selector")

    if active_skill_names:
        print(f"本轮激活 Skill：{', '.join(active_skill_names)}")
    else:
        print("本轮未激活 Skill")

    messages.append({
        "role": "user",
        "content": user_input
    })

    skill_context = build_skill_context(
        active_skill_instructions,
        active_reference_files
    )

    if skill_context:
        messages.append({
            "role": "system",
            "content": skill_context
        })

    while True:
        messages = sanitize_messages_for_api(messages)
        messages = maybe_compress_context(client, MODEL, messages)
        messages = sanitize_messages_for_api(messages)

        log_event(
            current_conversation_id,
            "model_start",
            skills=active_skill_names,
            tools=[tool["function"]["name"] for tool in active_tools],
            message_count=len(messages),
        )

        try:
            response = call_model(messages, active_tools)
        except Exception as e:
            log_event(
                current_conversation_id,
                "model_end",
                skills=active_skill_names,
                status="error",
                error=str(e),
            )
            raise

        msg = response.choices[0].message
        msg_dict = message_to_dict(msg)

        log_event(
            current_conversation_id,
            "model_end",
            skills=active_skill_names,
            status="success",
            has_tool_calls=bool(msg.tool_calls),
            response_preview=(msg.content or "")[:1200],
        )

        messages.append(msg_dict)

        if msg.content:
            print(f"\n💬 助手：{msg.content}")

            if not msg.tool_calls:
                reply = msg.content or ""

                final_reply = build_debug_tip(active_skill_names, used_tools) + "\n\n" + reply

                messages[-1] = {
                    "role": "assistant",
                    "content": final_reply
                }

                save_current_conversation()

                log_event(
                    current_conversation_id,
                    "assistant_response",
                    skills=active_skill_names,
                    used_tools=used_tools,
                    reply_preview=final_reply[:1200],
                )

                return final_reply

        for tool_call in msg.tool_calls:
            name = tool_call.function.name

            try:
                args = json.loads(tool_call.function.arguments)
            except Exception as e:
                result = f"工具参数解析失败：{str(e)}"

                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": result
                })

                continue

            print(f"⚙️ 网页版调用工具：{name}")

            if name not in active_handlers:
                result = f"工具调用失败：当前任务没有激活 {name} 这个工具。"
                log_event(
                    current_conversation_id,
                    "tool_blocked",
                    tool=name,
                    args=args,
                    reason="tool_not_active",
                )
            else:
                try:
                    log_event(
                        current_conversation_id,
                        "tool_start",
                        tool=name,
                        args=args,
                    )
                    used_tools.append(name)
                    result = active_handlers[name](**args)
                    log_event(
                        current_conversation_id,
                        "tool_end",
                        tool=name,
                        status="success",
                        result_preview=result[:1200] if isinstance(result, str) else str(result)[:1200],
                    )
                except Exception as e:
                    result = f"工具执行失败：{str(e)}"
                    log_event(
                        current_conversation_id,
                        "tool_end",
                        tool=name,
                        status="error",
                        error=str(e),
                    )

            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": result
            })


# ====================== Flask 路由 ======================

def activate_conversation(conversation_id=None):
    global current_conversation_id

    if conversation_id:
        conversation_id = validate_conversation_id(conversation_id)
        if conversation_path(conversation_id).exists():
            load_conversation(conversation_id)
            return conversation_id

    with STATE_LOCK:
        active_id = current_conversation_id

    if active_id is None:
        active_id = create_new_conversation()

    return active_id


def run_agent_once(user_input, conversation_id=None):
    global current_conversation_id, messages, manual_workflow_state

    active_id = activate_conversation(conversation_id)

    with get_conversation_lock(active_id):
        loaded = load_conversation_state(active_id)
        if loaded is None:
            loaded_messages = [SYSTEM_MESSAGE]
            loaded_workflow_state = None
            save_conversation_state(active_id, loaded_messages, loaded_workflow_state)
        else:
            loaded_messages, loaded_workflow_state = loaded

        session = AgentSession(
            messages=loaded_messages,
            manual_workflow_state=loaded_workflow_state,
        )

        result = agent_runner.run(
            user_input=user_input,
            session=session,
            conversation_id=active_id,
            event_logger=lambda event_type, **payload: log_event(
                active_id,
                event_type,
                **payload
            ),
        )

        save_conversation_state(active_id, result.messages, result.manual_workflow_state)

    with STATE_LOCK:
        current_conversation_id = active_id
        messages = result.messages
        manual_workflow_state = result.manual_workflow_state

    return result.reply


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    user_input = data.get("message", "")
    conversation_id = data.get("conversation_id")

    try:
        reply = run_agent_once(user_input, conversation_id=conversation_id)

        return jsonify({
            "reply": reply,
            "conversation_id": current_conversation_id,
            "conversations": list_conversations()
        })

    except ValueError as e:
        return jsonify({
            "reply": str(e),
            "error": str(e)
        }), 400

    except Exception as e:
        log_event(
            current_conversation_id,
            "chat_error",
            error=str(e),
            message=user_input,
        )
        return jsonify({
            "reply": f"出错了：{str(e)}"
        })


def workflow_context_for_request(payload=None):
    payload = payload or {}
    conversation_id = payload.get("conversation_id") or request.args.get("conversation_id") or current_conversation_id or "workflow_api"
    return WorkflowContext(
        session_id=str(conversation_id),
        run_id=str(conversation_id),
        event_logger=lambda event_type, **event_payload: log_event(conversation_id, event_type, **event_payload),
        model_client=client,
        model=MODEL,
    )


@app.route("/api/workflows", methods=["GET"])
def api_list_workflows():
    return jsonify({"workflows": workflow_runtime.list_workflows()})


@app.route("/api/workflows/<workflow_id>/actions", methods=["GET"])
def api_workflow_actions(workflow_id):
    actions = workflow_runtime.get_actions(workflow_id)
    if not actions:
        return jsonify({"workflow_id": workflow_id, "actions": []}), 404
    return jsonify({"workflow_id": workflow_id, "actions": actions})


@app.route("/api/workflows/<workflow_id>/status", methods=["GET"])
def api_workflow_status(workflow_id):
    params = dict(request.args.items())
    status = workflow_runtime.get_status(workflow_id, params, workflow_context_for_request())
    return jsonify(asdict(status)), 200 if status.ok else 400


@app.route("/api/workflows/<workflow_id>/actions/<action>", methods=["POST"])
def api_run_workflow_action(workflow_id, action):
    payload = request.get_json() or {}
    params = dict(payload)
    params.pop("conversation_id", None)
    result = workflow_runtime.run_action(workflow_id, action, params, workflow_context_for_request(payload))
    return jsonify(asdict(result)), 200 if result.ok else 400


@app.route("/upload", methods=["POST"])
def upload_file():
    """
    浏览器上传文件。
    小文件用这个。
    大文件建议用 /import_path。
    """
    activate_conversation(request.form.get("conversation_id"))

    if "files" not in request.files:
        log_event(current_conversation_id, "upload_end", status="error", error="no_files_field")
        return jsonify({
            "error": "没有收到文件。"
        }), 400

    files = request.files.getlist("files")

    if not files:
        log_event(current_conversation_id, "upload_end", status="error", error="no_files_selected")
        return jsonify({
            "error": "没有选择文件。"
        }), 400

    log_event(
        current_conversation_id,
        "upload_start",
        file_count=len(files),
        filenames=[file.filename for file in files if file.filename],
    )

    saved_files = []
    extracted_zip_files = []
    rejected_files = []

    for file in files:
        original_name = file.filename

        if not original_name:
            continue

        if not is_allowed_upload(original_name):
            rejected_files.append({
                "filename": original_name,
                "reason": "不支持的文件类型"
            })
            continue

        suffix = Path(original_name).suffix.lower()

        if suffix != ".zip":
            safe_name = make_safe_upload_name(original_name)
            save_path = IMPORT_DIR / safe_name

            try:
                file.save(save_path)

                saved_files.append({
                    "original_name": original_name,
                    "saved_name": safe_name,
                    "saved_path": str(save_path).replace("\\", "/"),
                    "type": "file"
                })

            except Exception as e:
                rejected_files.append({
                    "filename": original_name,
                    "reason": str(e)
                })

            continue

        safe_zip_name = make_safe_upload_name(original_name)
        zip_save_path = ARCHIVE_DIR / safe_zip_name

        try:
            file.save(zip_save_path)

            extract_folder_name = make_safe_folder_name(original_name)
            extract_dir = IMPORT_DIR / extract_folder_name

            result = extract_zip_safely(zip_save_path, extract_dir)

            if not result["ok"]:
                rejected_files.append({
                    "filename": original_name,
                    "reason": result["error"]
                })
                continue

            saved_files.append({
                "original_name": original_name,
                "saved_name": safe_zip_name,
                "saved_path": str(zip_save_path).replace("\\", "/"),
                "extract_dir": str(extract_dir).replace("\\", "/"),
                "type": "zip"
            })

            extracted_zip_files.append({
                "zip_name": original_name,
                "extract_dir": str(extract_dir).replace("\\", "/"),
                "files": result["extracted_files"],
                "skipped_files": result["skipped_files"]
            })

        except Exception as e:
            rejected_files.append({
                "filename": original_name,
                "reason": str(e)
            })

    if not saved_files and not extracted_zip_files and rejected_files:
        log_event(
            current_conversation_id,
            "upload_end",
            status="error",
            saved_count=0,
            extracted_zip_count=0,
            rejected_count=len(rejected_files),
            rejected_files=rejected_files,
        )
        return jsonify({
            "error": "文件上传失败。",
            "rejected_files": rejected_files
        }), 400

    log_event(
        current_conversation_id,
        "upload_end",
        status="success",
        saved_count=len(saved_files),
        extracted_zip_count=len(extracted_zip_files),
        rejected_count=len(rejected_files),
        saved_files=saved_files,
        extracted_dirs=[item.get("extract_dir") for item in extracted_zip_files],
    )

    return jsonify({
        "message": "文件上传完成。",
        "files": saved_files,
        "extracted_zip_files": extracted_zip_files,
        "rejected_files": rejected_files
    })


@app.route("/import_path", methods=["POST"])
def import_path():
    """
    通过本机路径导入文件、zip 或文件夹。

    适合大文件：
    - 不经过浏览器上传
    - 由 Flask 后端直接读取本机路径

    支持：
    - 文件夹：直接返回路径，不复制
    - 普通文件：复制到 data/imports/
    - zip：复制到 data/imports/_archives/ 并解压到 data/imports/<zip_name_xxxxxxxx>/
    """
    data = request.get_json() or {}
    activate_conversation(data.get("conversation_id"))
    source_path_text = data.get("path", "").strip()

    log_event(
        current_conversation_id,
        "import_path_start",
        source_path=source_path_text,
    )

    if not source_path_text:
        log_event(current_conversation_id, "import_path_end", status="error", error="empty_path")
        return jsonify({
            "error": "请输入本机文件、zip 或文件夹路径。"
        }), 400

    source_path = Path(source_path_text)

    if not source_path.exists():
        log_event(
            current_conversation_id,
            "import_path_end",
            status="error",
            error="path_not_found",
            source_path=source_path_text,
        )
        return jsonify({
            "error": f"路径不存在：{source_path_text}"
        }), 400

    # 1. 文件夹：不复制，直接返回原路径
    if source_path.is_dir():
        log_event(
            current_conversation_id,
            "import_path_end",
            status="success",
            import_type="folder",
            source_path=str(source_path.resolve()).replace("\\", "/"),
        )
        return jsonify({
            "message": "文件夹路径已导入。",
            "type": "folder",
            "source_path": str(source_path.resolve()).replace("\\", "/"),
            "tip": "这是一个文件夹，不需要复制。Agent 可以直接读取或解析这个目录。"
        })

    if not source_path.is_file():
        log_event(
            current_conversation_id,
            "import_path_end",
            status="error",
            error="not_file_or_folder",
            source_path=source_path_text,
        )
        return jsonify({
            "error": f"该路径不是有效文件或文件夹：{source_path_text}"
        }), 400

    suffix = source_path.suffix.lower()

    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        log_event(
            current_conversation_id,
            "import_path_end",
            status="error",
            error="unsupported_extension",
            suffix=suffix,
            source_path=source_path_text,
        )
        return jsonify({
            "error": f"不支持的文件类型：{suffix}"
        }), 400

    # 2. 普通文件
    if suffix != ".zip":
        try:
            target_path = copy_file_to_imports(source_path)

            log_event(
                current_conversation_id,
                "import_path_end",
                status="success",
                import_type="file",
                original_path=str(source_path.resolve()).replace("\\", "/"),
                saved_path=str(target_path).replace("\\", "/"),
            )

            return jsonify({
                "message": "文件已通过路径导入。",
                "type": "file",
                "original_path": str(source_path.resolve()).replace("\\", "/"),
                "saved_path": str(target_path).replace("\\", "/")
            })

        except Exception as e:
            log_event(
                current_conversation_id,
                "import_path_end",
                status="error",
                error=str(e),
                source_path=source_path_text,
            )
            return jsonify({
                "error": f"文件导入失败：{str(e)}"
            }), 500

    # 3. zip 文件
    safe_zip_name = make_safe_upload_name(source_path.name)
    zip_save_path = ARCHIVE_DIR / safe_zip_name

    try:
        with open(source_path, "rb") as src:
            with open(zip_save_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

        extract_folder_name = make_safe_folder_name(source_path.name)
        extract_dir = IMPORT_DIR / extract_folder_name

        result = extract_zip_safely(zip_save_path, extract_dir)

        if not result["ok"]:
            log_event(
                current_conversation_id,
                "import_path_end",
                status="error",
                import_type="zip",
                error=result["error"],
                source_path=str(source_path.resolve()).replace("\\", "/"),
            )
            return jsonify({
                "error": result["error"]
            }), 400

        log_event(
            current_conversation_id,
            "import_path_end",
            status="success",
            import_type="zip",
            original_path=str(source_path.resolve()).replace("\\", "/"),
            saved_zip=str(zip_save_path).replace("\\", "/"),
            extract_dir=str(extract_dir).replace("\\", "/"),
            extracted_count=len(result["extracted_files"]),
            skipped_count=len(result["skipped_files"]),
        )

        return jsonify({
            "message": "zip 已通过路径导入并解压。",
            "type": "zip",
            "original_path": str(source_path.resolve()).replace("\\", "/"),
            "saved_zip": str(zip_save_path).replace("\\", "/"),
            "extract_dir": str(extract_dir).replace("\\", "/"),
            "files": result["extracted_files"],
            "skipped_files": result["skipped_files"]
        })

    except Exception as e:
        log_event(
            current_conversation_id,
            "import_path_end",
            status="error",
            import_type="zip",
            error=str(e),
            source_path=source_path_text,
        )
        return jsonify({
            "error": f"zip 路径导入失败：{str(e)}"
        }), 500


@app.route("/conversations", methods=["GET"])
def get_conversations():
    return jsonify({
        "current_id": current_conversation_id,
        "conversations": list_conversations()
    })


@app.route("/logs/current", methods=["GET"])
def get_current_logs():
    limit = int(request.args.get("limit", 200))
    return jsonify({
        "conversation_id": current_conversation_id,
        "events": read_events(current_conversation_id, limit=limit)
    })


@app.route("/logs/<conversation_id>", methods=["GET"])
def get_logs(conversation_id):
    try:
        conversation_id = validate_conversation_id(conversation_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    limit = int(request.args.get("limit", 200))
    return jsonify({
        "conversation_id": conversation_id,
        "events": read_events(conversation_id, limit=limit)
    })


@app.route("/conversation/<conversation_id>", methods=["GET"])
def get_conversation(conversation_id):
    try:
        ok = load_conversation(conversation_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not ok:
        return jsonify({
            "error": "聊天记录不存在"
        }), 404

    return jsonify({
        "conversation_id": current_conversation_id,
        "messages": visible_messages_only(messages),
        "conversations": list_conversations()
    })


@app.route("/conversation/<conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id):
    global current_conversation_id, messages, manual_workflow_state

    try:
        conversation_id = validate_conversation_id(conversation_id)
        path = conversation_path(conversation_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not path.exists():
        return jsonify({
            "error": "聊天记录不存在"
        }), 404

    try:
        path.unlink()
        log_event(
            conversation_id,
            "conversation_deleted",
            deleted_conversation_id=conversation_id,
        )

        with STATE_LOCK:
            deleting_current = current_conversation_id == conversation_id

        if deleting_current:
            with STATE_LOCK:
                current_conversation_id = None
                messages = [SYSTEM_MESSAGE]
                manual_workflow_state = None

        return jsonify({
            "message": "聊天记录已删除。",
            "current_id": current_conversation_id,
            "messages": visible_messages_only(messages),
            "conversations": list_conversations()
        })

    except Exception as e:
        return jsonify({
            "error": f"删除失败：{str(e)}"
        }), 500


@app.route("/conversation/<conversation_id>/rename", methods=["POST"])
def rename_conversation(conversation_id):
    data = request.get_json()
    new_title = data.get("title", "").strip()

    if not new_title:
        return jsonify({
            "error": "标题不能为空"
        }), 400

    try:
        conversation_id = validate_conversation_id(conversation_id)
        path = conversation_path(conversation_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not path.exists():
        return jsonify({
            "error": "聊天记录不存在"
        }), 404

    try:
        conversation_data = json.loads(path.read_text(encoding="utf-8"))

        conversation_data["title"] = new_title
        conversation_data["manual_title"] = True
        conversation_data["updated_at"] = now_text()

        path.write_text(
            json.dumps(conversation_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        log_event(
            conversation_id,
            "conversation_renamed",
            title=new_title,
        )

        return jsonify({
            "message": "标题已重命名。",
            "conversations": list_conversations()
        })

    except Exception as e:
        return jsonify({
            "error": f"重命名失败：{str(e)}"
        }), 500


@app.route("/new_chat", methods=["POST"])
def new_chat():
    global current_conversation_id, messages, manual_workflow_state

    with STATE_LOCK:
        current_conversation_id = None
        messages = [SYSTEM_MESSAGE]
        manual_workflow_state = None

    return jsonify({
        "conversation_id": None,
        "messages": visible_messages_only(messages),
        "conversations": list_conversations()
    })


@app.route("/reset", methods=["POST"])
def reset():
    global messages, manual_workflow_state

    with STATE_LOCK:
        active_id = current_conversation_id
        messages = [SYSTEM_MESSAGE]
        manual_workflow_state = None

    if active_id:
        save_conversation_state(active_id, messages, manual_workflow_state)
        log_event(active_id, "conversation_reset")

    return jsonify({
        "message": "当前聊天已清空。",
        "messages": visible_messages_only(messages),
        "conversations": list_conversations()
    })

## 调试使用，不要在生产环境中运行
if __name__ == "__main__":
    app.run(debug=True)
