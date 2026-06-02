from __future__ import annotations

from .rtl_manual.actions import RtlManualWorkflow

'''
工作流注册器 注册了系统中所有已加载的工作流
'''

WORKFLOWS = {
    "rtl_manual": RtlManualWorkflow(),
}


def get_workflow(workflow_id: str):
    return WORKFLOWS.get(workflow_id)


def list_workflows():
    return list(WORKFLOWS.values())
