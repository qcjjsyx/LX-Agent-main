from __future__ import annotations

from pathlib import Path
from typing import Any

from ..types import WorkflowActionResult, WorkflowActionSpec, WorkflowContext, WorkflowStatus
from .artifacts import load_manifest, save_manifest
from .composer import compose_final_manual
from .enhancer import enhance_main_manual, enhance_module_page, enhance_module_pages_batch
from .manifest import load_runtime_status
from .reviewer import review_final_manual
from .source_review import run_source_review
from .workflow import build_base_manual

## 工作流动作的 定义和实现
class RtlManualWorkflow:
    id = "rtl_manual"
    label = "RTL Manual Generation"
    description = "Build and compose evidence-bound RTL code manuals."

    def actions(self) -> list[WorkflowActionSpec]:
        return [
            WorkflowActionSpec(
                id="status",
                label="Status",
                description="Read manifest and artifact status.",
                required_params=["project_root", "top_module"],
            ),
            WorkflowActionSpec(
                id="build",
                label="Build Base Manual",
                description="Build deterministic base manual artifacts.",
                required_params=["project_root", "rtl_inputs", "top_module"],
                optional_params=["audience", "evidence_mode", "enrich_modules", "force"],
            ),
            WorkflowActionSpec(
                id="compose",
                label="Compose Final Manual",
                description="Compose final manual from base and enhanced fragments.",
                required_params=["project_root", "top_module"],
            ),
            WorkflowActionSpec(
                id="source_review",
                label="Source Review",
                description="Run controlled source review and mark enhanced fragments stale.",
                required_params=["project_root", "top_module"],
                optional_params=["model"],
            ),
            WorkflowActionSpec(
                id="enhance_main",
                label="Enhance Main Manual",
                description="Enhance the whole base main manual into a separate fragment.",
                required_params=["project_root", "top_module"],
                optional_params=["model"],
            ),
            WorkflowActionSpec(
                id="enhance_module",
                label="Enhance Module Page",
                description="Enhance exactly one base module page into a separate fragment.",
                required_params=["project_root", "top_module", "target_module"],
                optional_params=["model"],
            ),
            WorkflowActionSpec(
                id="enhance_modules",
                label="Enhance Module Pages",
                description="Enhance multiple base module pages into separate fragments.",
                required_params=["project_root", "top_module"],
                optional_params=["target_modules", "module_filter", "model"],
            ),
            WorkflowActionSpec(
                id="review",
                label="Review Final Manual",
                description="Review the composed final manual and module pages.",
                required_params=["project_root", "top_module"],
                optional_params=["model"],
            ),
        ]

    def run(self, action: str, params: dict[str, Any], context: WorkflowContext) -> WorkflowActionResult:
        if action == "status":
            status = self.status(params, context)
            return WorkflowActionResult(
                ok=status.ok,
                workflow_id=self.id,
                action=action,
                run_id=status.run_id,
                message="Status loaded." if status.ok else "Failed to load status.",
                artifacts=status.artifacts,
                status=status.status,
                warnings=status.warnings,
                errors=status.errors,
            )
        if action == "build":
            return self._build(params, context)
        if action == "compose":
            return self._compose(params, context)
        if action == "source_review":
            return self._source_review(params, context)
        if action == "enhance_main":
            return self._enhance_main(params, context)
        if action == "enhance_module":
            return self._enhance_module(params, context)
        if action == "enhance_modules":
            return self._enhance_modules(params, context)
        if action == "review":
            return self._review(params, context)
        error = f"Unknown action: {action}"
        return WorkflowActionResult(ok=False, workflow_id=self.id, action=action, run_id=context.run_id, message=error, errors=[error])

    def status(self, params: dict[str, Any], context: WorkflowContext) -> WorkflowStatus:
        project_root = _required(params, "project_root")
        top_module = _required(params, "top_module")
        return load_runtime_status(project_root=project_root, top_module=top_module, context=context)

    def _build(self, params: dict[str, Any], context: WorkflowContext) -> WorkflowActionResult:
        project_root = _required(params, "project_root")
        top_module = _required(params, "top_module")
        result = build_base_manual(
            project_root=project_root,
            rtl_inputs=params.get("rtl_inputs", "rtl"),
            top_module=top_module,
            audience=params.get("audience", "newcomer"),
            evidence_mode=params.get("evidence_mode", "project"),
            enrich_modules=params.get("enrich_modules", ""),
            force=_bool_param(params.get("force", False)),
            event_logger=context.event_logger,
        )
        status = self.status({"project_root": project_root, "top_module": top_module}, context)
        return WorkflowActionResult(
            ok=True,
            workflow_id=self.id,
            action="build",
            run_id=context.run_id,
            message="Base manual built.",
            artifacts={
                "base_main": str(result["base_main"]),
                "base_modules_dir": str(result["base_modules_dir"]),
                "manifest": str(result["manifest_path"]),
            },
            status=status.status,
            warnings=status.warnings,
        )

    def _source_review(self, params: dict[str, Any], context: WorkflowContext) -> WorkflowActionResult:
        project_root = _required(params, "project_root")
        top_module = _required(params, "top_module")
        result = run_source_review(
            project_root=project_root,
            top_module=top_module,
            client=context.model_client,
            model=_model(params, context),
            event_logger=context.event_logger,
        )
        _record_source_review_path(project_root, top_module, result.get("source_review_output_path", ""))
        status = self.status({"project_root": project_root, "top_module": top_module}, context)
        return WorkflowActionResult(
            ok=True,
            workflow_id=self.id,
            action="source_review",
            run_id=context.run_id,
            message="Source review complete.",
            artifacts={
                "source_review": result.get("source_review_output_path", ""),
                "manifest": status.artifacts.get("manifest", ""),
            },
            status=status.status,
            warnings=status.warnings,
        )

    def _enhance_main(self, params: dict[str, Any], context: WorkflowContext) -> WorkflowActionResult:
        project_root = _required(params, "project_root")
        top_module = _required(params, "top_module")
        client = _required_model_client(context)
        result = enhance_main_manual(
            project_root=project_root,
            top_module=top_module,
            client=client,
            model=_model(params, context, required=True), # type: ignore
            event_logger=context.event_logger,
        )
        status = self.status({"project_root": project_root, "top_module": top_module}, context)
        return WorkflowActionResult(
            ok=True,
            workflow_id=self.id,
            action="enhance_main",
            run_id=context.run_id,
            message="Main manual enhancement complete.",
            artifacts={
                "enhanced": str(result["enhanced_path"]),
                "manifest": str(result["manifest_path"]),
            },
            status=status.status,
            warnings=status.warnings,
        )

    def _enhance_module(self, params: dict[str, Any], context: WorkflowContext) -> WorkflowActionResult:
        project_root = _required(params, "project_root")
        top_module = _required(params, "top_module")
        target_module = _required(params, "target_module")
        client = _required_model_client(context)
        result = enhance_module_page(
            project_root=project_root,
            top_module=top_module,
            target_module=target_module,
            client=client,
            model=_model(params, context, required=True), # type: ignore
            event_logger=context.event_logger,
        )
        status = self.status({"project_root": project_root, "top_module": top_module}, context)
        return WorkflowActionResult(
            ok=True,
            workflow_id=self.id,
            action="enhance_module",
            run_id=context.run_id,
            message="Module page enhancement complete.",
            artifacts={
                "enhanced": str(result["enhanced_path"]),
                "manifest": str(result["manifest_path"]),
            },
            status=status.status,
            warnings=status.warnings,
        )

    def _enhance_modules(self, params: dict[str, Any], context: WorkflowContext) -> WorkflowActionResult:
        project_root = _required(params, "project_root")
        top_module = _required(params, "top_module")
        client = _required_model_client(context)
        result = enhance_module_pages_batch(
            project_root=project_root,
            top_module=top_module,
            target_modules=params.get("target_modules") or params.get("modules"),
            module_filter=params.get("module_filter", "all"),
            client=client,
            model=_model(params, context, required=True), # type: ignore
            event_logger=context.event_logger,
        )
        status = self.status({"project_root": project_root, "top_module": top_module}, context)
        failed_count = int(result.get("failed_count", 0))
        return WorkflowActionResult(
            ok=failed_count == 0,
            workflow_id=self.id,
            action="enhance_modules",
            run_id=context.run_id,
            message="Module batch enhancement complete." if failed_count == 0 else "Module batch enhancement completed with failures.",
            artifacts={
                "manifest": str(result["manifest_path"]),
            },
            status={
                **status.status,
                "target_count": len(result.get("targets", [])),
                "success_count": result.get("success_count", 0),
                "failed_count": failed_count,
                "results": result.get("results", []),
            },
            warnings=status.warnings,
            errors=[item["error"] for item in result.get("results", []) if item.get("status") == "failed" and item.get("error")],
        )

    def _review(self, params: dict[str, Any], context: WorkflowContext) -> WorkflowActionResult:
        project_root = _required(params, "project_root")
        top_module = _required(params, "top_module")
        result = review_final_manual(
            project_root=project_root,
            top_module=top_module,
            client=context.model_client,
            model=_model(params, context),
            event_logger=context.event_logger,
        )
        _record_review_path(project_root, top_module, result.get("review_output_path", ""))
        status = self.status({"project_root": project_root, "top_module": top_module}, context)
        return WorkflowActionResult(
            ok=True,
            workflow_id=self.id,
            action="review",
            run_id=context.run_id,
            message="Final manual review complete.",
            artifacts={
                "review": result.get("review_output_path", ""),
                "manifest": status.artifacts.get("manifest", ""),
            },
            status=status.status,
            warnings=status.warnings,
        )

    def _compose(self, params: dict[str, Any], context: WorkflowContext) -> WorkflowActionResult:
        project_root = _required(params, "project_root")
        top_module = _required(params, "top_module")
        result = compose_final_manual(
            project_root=project_root,
            top_module=top_module,
            event_logger=context.event_logger,
        )
        status = self.status({"project_root": project_root, "top_module": top_module}, context)
        return WorkflowActionResult(
            ok=True,
            workflow_id=self.id,
            action="compose",
            run_id=context.run_id,
            message="Final manual composed.",
            artifacts={
                "final_main": str(result["final_main"]),
                "final_modules_dir": str(result["final_modules_dir"]),
                "manifest": str(result["manifest_path"]),
            },
            status={
                **status.status,
                "enhanced_count": result["enhanced_count"],
                "fallback_count": result["fallback_count"],
                "stale_count": result["stale_count"],
                "invalid_count": result["invalid_count"],
            },
            warnings=status.warnings,
        )


def _required(params: dict[str, Any], key: str) -> Any:
    value = params.get(key)
    if value in (None, ""):
        raise ValueError(f"missing required workflow parameter: {key}")
    if key == "project_root":
        return str(Path(value).expanduser())
    return value


def _required_model_client(context: WorkflowContext) -> Any:
    if context.model_client is None:
        raise ValueError("model client is required for this workflow action")
    return context.model_client


def _model(params: dict[str, Any], context: WorkflowContext, *, required: bool = False) -> str | None:
    model = params.get("model") or context.model
    if required and not model:
        raise ValueError("model is required for this workflow action")
    return model


def _bool_param(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "force"}
    return bool(value)


def _record_source_review_path(project_root: str | Path, top_module: str, report_path: str) -> None:
    manifest = load_manifest(project_root, top_module)
    source_review = manifest.setdefault("source_review", {})
    source_review["status"] = source_review.get("status") or "updated_manual_context"
    source_review["report_path"] = _artifact_path_text(project_root, report_path)
    save_manifest(project_root, top_module, manifest)


def _record_review_path(project_root: str | Path, top_module: str, report_path: str) -> None:
    manifest = load_manifest(project_root, top_module)
    manifest["review"] = {
        "status": "success",
        "report_path": _artifact_path_text(project_root, report_path),
        "error": "",
    }
    save_manifest(project_root, top_module, manifest)


def _artifact_path_text(project_root: str | Path, path_text: str) -> str:
    if not path_text:
        return ""
    root = Path(project_root).expanduser().resolve()
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
