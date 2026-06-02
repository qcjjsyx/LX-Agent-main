"""Compatibility entrypoint for the layered RTL manual workflow CLI."""

from __future__ import annotations

import os

try:
    from .workflows.rtl_manual.cli import (
        _load_dotenv,
        apply_runtime_env,
        build_event_logger,
        build_model_client,
        build_parser,
        main,
        print_build_summary,
        print_compose_summary,
        print_enhance_summary,
        print_source_review_summary,
    )
except ImportError:  # pragma: no cover - supports direct script execution
    from workflows.rtl_manual.cli import (
        _load_dotenv,
        apply_runtime_env,
        build_event_logger,
        build_model_client,
        build_parser,
        main,
        print_build_summary,
        print_compose_summary,
        print_enhance_summary,
        print_source_review_summary,
    )


__all__ = [
    "_load_dotenv",
    "apply_runtime_env",
    "build_event_logger",
    "build_model_client",
    "build_parser",
    "main",
    "os",
    "print_build_summary",
    "print_compose_summary",
    "print_enhance_summary",
    "print_source_review_summary",
]


if __name__ == "__main__":
    raise SystemExit(main())
