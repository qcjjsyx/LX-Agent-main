from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 工作流中单个动作的元数据和参数规范
@dataclass
class WorkflowActionSpec:
    id: str
    label: str
    description: str = ""
    required_params: list[str] = field(default_factory=list)
    optional_params: list[str] = field(default_factory=list)
    destructive: bool = False
    user_facing: bool = True


# 工作流运行时的上下文信息
@dataclass
class WorkflowContext:
    session_id: str = ""
    user_id: str = ""
    run_id: str = ""
    event_logger: Any = None
    model_client: Any = None
    model: str | None = None

# 工作流运行引用
@dataclass
class WorkflowRunRef:
    workflow_id: str
    run_id: str = ""
    project_root: str = ""
    top_module: str = ""

# 工作流运行结果
@dataclass
class WorkflowActionResult:
    ok: bool
    workflow_id: str
    action: str
    run_id: str = ""
    message: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)
    status: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

# 工作流运行状态
@dataclass
class WorkflowStatus:
    workflow_id: str
    ok: bool
    run_id: str = ""
    status: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
