# RTL Manual Scripts

从仓库根目录执行这些脚本。

```bash
scripts/run_rtl_manual_full.sh
```

完整链路：`status -> build --force -> enhance main -> enhance modules -> compose -> status`。

```bash
scripts/run_rtl_manual_build_only.sh
```

只运行 build：`status -> build --force -> status`，用于重新生成 parser / knowledge / manual_context / base。

```bash
scripts/run_rtl_manual_base.sh
```

只做基础手册：`status -> build --force -> compose -> status`，跳过主手册增强和模块增强。

```bash
scripts/run_rtl_manual_source_review_only.sh
```

只运行源码复核：依赖已有 `manual_context`，只对 `evidence_gap` / `needs_review` / `requires_rtl_source_review` 显式标记项写回 `source_review_claims` / `source_review_report` 并标记已有增强 stale；之后应重新运行 enhance / compose，不要立刻跑完整 build 覆盖 Manual Context。

```bash
scripts/run_rtl_manual_full_with_review.sh
```

带源码复核：`build --force -> source-review -> enhance main（注入 Manual Context 摘要）-> enhance modules -> compose`。

```bash
scripts/run_rtl_manual_retry_modules.sh
```

断点续跑模块增强：跳过 build 和主手册增强，只增强 `retryable` 模块后 compose。

```bash
scripts/run_rtl_manual_main_only.sh
```

只增强主手册：跳过 build 和模块增强，完成后 compose。

```bash
scripts/run_rtl_manual_selected_modules.sh decode,writeback
```

只增强指定模块，完成后 compose。

```bash
scripts/run_rtl_manual_compose_only.sh
```

只根据已有 base/enhanced fragments 重新 compose 和 review。

```bash
scripts/watch_rtl_manual_semantic_progress.sh
```

查看 Knowledge Semantic Layer 进度日志。

所有运行脚本都可以继续传递通用参数，例如：

```bash
--project-root ./rtl
--rtl-inputs rtl
--top-module arm_soc_top
--model deepseek-v4-pro
--review-model deepseek-v4-flash
--knowledge-timeout 10800
--python /opt/anaconda3/envs/ML/bin/python
```
