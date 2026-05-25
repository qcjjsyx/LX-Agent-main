from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from .context_manager import maybe_compress_context
    from .manual_workflow import handle_manual_workflow, should_handle_manual_workflow
    from .tools import select_tools_for_task
except ImportError:  # pragma: no cover - supports direct script execution
    from context_manager import maybe_compress_context
    from manual_workflow import handle_manual_workflow, should_handle_manual_workflow
    from tools import select_tools_for_task


@dataclass
class AgentSession:
    messages: list[Any] = field(default_factory=list)
    manual_workflow_state: dict[str, Any] | None = None


@dataclass
class AgentRunResult:
    reply: str
    messages: list[Any]
    manual_workflow_state: dict[str, Any] | None
    skills: list[str] = field(default_factory=list)
    used_tools: list[str] = field(default_factory=list)


def message_to_dict(message):
    if isinstance(message, dict):
        return message

    if hasattr(message, "model_dump"):
        return message.model_dump()

    return {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", ""),
    }


def sanitize_messages_for_api(raw_messages):
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

            for tool_call in msg.get("tool_calls") or []:
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

    return clean_messages


def build_debug_tip(active_skill_names, used_tools):
    lines = []

    if active_skill_names:
        lines.append(f"[Skills: {', '.join(active_skill_names)}]")
    else:
        lines.append("[Skills: none]")

    if used_tools:
        lines.append(f"[Tools: {', '.join(used_tools)}]")
    else:
        lines.append("[Tools: none]")

    return "\n".join(lines)


def build_skill_context(active_skill_instructions, active_reference_files):
    if not active_skill_instructions and not active_reference_files:
        return None

    parts = []

    if active_skill_instructions:
        parts.extend(active_skill_instructions)

    if active_reference_files:
        reference_text = "Reference files for the selected skill:\n"

        for path in active_reference_files:
            reference_text += f"- {path}\n"

        reference_text += (
            "\nRead these reference files with read_file before using the selected "
            "skill tools when they are relevant to the task."
        )

        parts.append(reference_text)

    return "\n\n".join(parts)


class AgentRunner:
    def __init__(self, client, model: str, base_dir: str | Path, system_message: dict[str, Any]):
        self.client = client
        self.model = model
        self.base_dir = Path(base_dir)
        self.system_message = system_message

    def ensure_messages(self, messages):
        clean_messages = sanitize_messages_for_api(messages or [])
        if not clean_messages or clean_messages[0].get("role") != "system":
            clean_messages.insert(0, self.system_message)
        return clean_messages

    def call_model(self, active_messages, active_tools):
        if self.client is None:
            raise RuntimeError(
                "模型客户端不可用：请安装 openai 依赖并配置 DEEPSEEK_API_KEY，"
                "或使用不需要模型调用的手册 workflow 阶段。"
            )

        safe_messages = sanitize_messages_for_api(active_messages)
        params = {
            "model": self.model,
            "messages": safe_messages,
        }

        if active_tools:
            params["tools"] = active_tools
            params["tool_choice"] = "auto"

        return self.client.chat.completions.create(**params)

    def run(self, user_input: str, session: AgentSession, conversation_id=None, event_logger=None):
        if not user_input.strip():
            return AgentRunResult(
                reply="Please enter a message.",
                messages=self.ensure_messages(session.messages),
                manual_workflow_state=session.manual_workflow_state,
            )

        messages = self.ensure_messages(session.messages)
        manual_state = session.manual_workflow_state
        log_event = event_logger or (lambda _event_type, **_payload: None)

        log_event("chat_request", message=user_input)

        if should_handle_manual_workflow(user_input, manual_state):
            return self._run_manual_workflow(
                user_input=user_input,
                messages=messages,
                manual_state=manual_state,
                conversation_id=conversation_id,
                log_event=log_event,
            )

        return self._run_tool_calling_agent(
            user_input=user_input,
            messages=messages,
            manual_state=manual_state,
            log_event=log_event,
        )

    def _run_manual_workflow(self, user_input, messages, manual_state, conversation_id, log_event):
        log_event(
            "skill_selected",
            skill="rtl-manual-generation",
            reason="manual_workflow",
            current_stage=(manual_state or {}).get("stage"),
        )

        messages.append({
            "role": "user",
            "content": user_input,
        })

        reply, manual_state = handle_manual_workflow(
            user_input=user_input,
            state=manual_state,
            base_dir=self.base_dir,
            client=self.client,
            model=self.model,
            event_logger=lambda event_type, **payload: log_event(event_type, **payload),
        )

        messages.append({
            "role": "assistant",
            "content": reply,
        })

        log_event(
            "assistant_response",
            skills=["rtl-manual-generation"],
            used_tools=[],
            workflow_stage=manual_state.get("stage") if manual_state else None,
            reply_preview=reply[:1200],
        )

        return AgentRunResult(
            reply=reply,
            messages=messages,
            manual_workflow_state=manual_state,
            skills=["rtl-manual-generation"],
            used_tools=[],
        )

    def _run_tool_calling_agent(self, user_input, messages, manual_state, log_event):
        (
            active_tools,
            active_handlers,
            active_skill_names,
            active_skill_instructions,
            active_reference_files,
        ) = select_tools_for_task(user_input)

        active_tool_names = [tool["function"]["name"] for tool in active_tools]

        log_event(
            "skill_selection",
            skills=active_skill_names,
            tools=active_tool_names,
            reference_files=active_reference_files,
        )

        used_tools = []

        messages.append({
            "role": "user",
            "content": user_input,
        })

        skill_context = build_skill_context(
            active_skill_instructions,
            active_reference_files,
        )

        if skill_context:
            messages.append({
                "role": "system",
                "content": skill_context,
            })

        while True:
            messages = sanitize_messages_for_api(messages)
            messages = maybe_compress_context(self.client, self.model, messages)
            messages = sanitize_messages_for_api(messages)

            log_event(
                "model_start",
                skills=active_skill_names,
                tools=active_tool_names,
                message_count=len(messages),
            )

            try:
                response = self.call_model(messages, active_tools)
            except Exception as e:
                log_event(
                    "model_end",
                    skills=active_skill_names,
                    status="error",
                    error=str(e),
                )
                raise

            msg = response.choices[0].message
            msg_dict = message_to_dict(msg)
            tool_calls = msg.tool_calls or []

            log_event(
                "model_end",
                skills=active_skill_names,
                status="success",
                has_tool_calls=bool(tool_calls),
                response_preview=(msg.content or "")[:1200],
            )

            messages.append(msg_dict)

            if msg.content and not tool_calls:
                reply = msg.content or ""
                final_reply = build_debug_tip(active_skill_names, used_tools) + "\n\n" + reply
                messages[-1] = {
                    "role": "assistant",
                    "content": final_reply,
                }

                log_event(
                    "assistant_response",
                    skills=active_skill_names,
                    used_tools=used_tools,
                    reply_preview=final_reply[:1200],
                )

                return AgentRunResult(
                    reply=final_reply,
                    messages=messages,
                    manual_workflow_state=manual_state,
                    skills=list(active_skill_names),
                    used_tools=used_tools,
                )

            if not tool_calls:
                final_reply = build_debug_tip(active_skill_names, used_tools)
                messages[-1] = {
                    "role": "assistant",
                    "content": final_reply,
                }
                log_event(
                    "assistant_response",
                    skills=active_skill_names,
                    used_tools=used_tools,
                    reply_preview=final_reply[:1200],
                )
                return AgentRunResult(
                    reply=final_reply,
                    messages=messages,
                    manual_workflow_state=manual_state,
                    skills=list(active_skill_names),
                    used_tools=used_tools,
                )

            for tool_call in tool_calls:
                name = tool_call.function.name

                try:
                    args = json.loads(tool_call.function.arguments)
                except Exception as e:
                    result = f"Tool argument parse failed: {str(e)}"
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": result,
                    })
                    continue

                if name not in active_handlers:
                    result = f"Tool call blocked: {name} is not active for this task."
                    log_event(
                        "tool_blocked",
                        tool=name,
                        args=args,
                        reason="tool_not_active",
                    )
                else:
                    try:
                        log_event("tool_start", tool=name, args=args)
                        used_tools.append(name)
                        result = active_handlers[name](**args)
                        log_event(
                            "tool_end",
                            tool=name,
                            status="success",
                            result_preview=result[:1200] if isinstance(result, str) else str(result)[:1200],
                        )
                    except Exception as e:
                        result = f"Tool execution failed: {str(e)}"
                        log_event(
                            "tool_end",
                            tool=name,
                            status="error",
                            error=str(e),
                        )

                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": result,
                })
