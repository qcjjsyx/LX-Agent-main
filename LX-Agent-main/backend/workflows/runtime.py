from __future__ import annotations

from dataclasses import asdict

from .registry import get_workflow, list_workflows
from .types import WorkflowActionResult, WorkflowContext, WorkflowStatus

'''
工作流运行时管理器 提供了操作工作流的接口
list_workflows() 获取系统中所有已注册的工作流列表 
get_actions(workflow_id) 获取指定工作流支持的所有动作（调用工作流的 actions() 方法） 
run_action(workflow_id, action, params, context) 执行 指定的工作流动作 
get_status(workflow_id, params, context) 获取工作流的当前状态
'''

class WorkflowRuntime:
    def list_workflows(self) -> list[dict]:
        return [
            {
                "id": workflow.id,
                "label": getattr(workflow, "label", workflow.id),
                "description": getattr(workflow, "description", ""),
            }
            for workflow in list_workflows()
        ]

    def get_actions(self, workflow_id: str) -> list[dict]:
        workflow = get_workflow(workflow_id)
        if not workflow:
            return []
        return [asdict(action) for action in workflow.actions()]

    def run_action(
        self,
        workflow_id: str,
        action: str,
        params: dict | None,
        context: WorkflowContext | None = None,
    ) -> WorkflowActionResult:
        workflow = get_workflow(workflow_id)
        if not workflow:
            error = f"Unknown workflow: {workflow_id}"
            return WorkflowActionResult(ok=False, workflow_id=workflow_id, action=action, message=error, errors=[error])

        context = context or WorkflowContext()
        try:
            return workflow.run(action=action, params=params or {}, context=context)
        except Exception as exc:
            return WorkflowActionResult(
                ok=False,
                workflow_id=workflow_id,
                action=action,
                run_id=context.run_id,
                message=f"Workflow action failed: {exc}",
                errors=[str(exc)],
            )

    def get_status(
        self,
        workflow_id: str,
        params: dict | None,
        context: WorkflowContext | None = None,
    ) -> WorkflowStatus:
        workflow = get_workflow(workflow_id)
        if not workflow:
            error = f"Unknown workflow: {workflow_id}"
            return WorkflowStatus(ok=False, workflow_id=workflow_id, errors=[error])

        context = context or WorkflowContext()
        try:
            return workflow.status(params or {}, context)
        except Exception as exc:
            return WorkflowStatus(ok=False, workflow_id=workflow_id, run_id=context.run_id, errors=[str(exc)])
