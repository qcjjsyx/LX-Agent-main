# RTL 手册生成重构计划

## Summary
- 当前问题主要不在 `manual_context` 完全缺信息，而在最终 renderer 做了大量抽样：模块最多 30 个、接口 24 行、flow 10 个、层级是样本，导致手册不像“代码手册”。
- 采用你的选择：**全量分层覆盖**、**主手册 + 模块页**、**允许受控读取 RTL**。
- 规则 6 调整为：最终手册以 `manual_context` 为主，但允许通过白名单式 `source_review_context` 读取 RTL 片段补证；AI 从 RTL 得出的解释仍必须标为 `ai_inferred` 或 `evidence_gap`，不能升格为确定事实。

## Key Changes
- 固化 Skill 章节规则：项目总览只写一句项目用途推断、RTL 目录、顶层文件；删除 Manual Context 数量统计、validation 统计等读者无关内容。
- 增强 `manual_context`：加入顶层外部端口/Pad 分组摘要、每个模块的 `module_doc_card`、完整层级索引、每模块接口/flow/gap 的可读摘要。
- 重写手册结构：
  - 主手册包含项目总览、顶层模块、完整模块层级、子系统/模块索引、关键跨模块 flow、全局证据缺口、证据边界。
  - 每个 reachable module 都有模块页；关键模块详写，helper/leaf/证据少的模块用压缩卡片。
  - 每个模块页固定包含：职责、父子位置、输入/输出自然语言摘要、drive/data/free 契约、主要 flow、内部组件/assign 影响、证据缺口。
- 改造证据缺口展示：按模块和主题聚合，翻译成可人工 review 的问题；避免直接照搬 `field=... reason=... evidence=...`。
- 受控 RTL 读取只用于补足读者必须知道但 `manual_context` 当前压缩掉的信息，例如顶层 Pad 分组、模块用途一句话、端口分组；读取结果要带源码路径/行锚点或 review 标记。
- 不采用“整本手册一次性 LLM 生成”。采用按模块生成/缓存语义卡片，再由确定性 renderer 组装，token 成本随模块分批增长，可控且可复用。

## Interfaces / Types
- 在 `manual_context` 增加或扩展：
  - `project_context.project_purpose`
  - `modules/<module>/module_doc_card.json` 或等价字段
  - `external_port_groups`
  - `module_page_policy`
  - `source_review_context`
- Skill 中明确每章“写什么/不写什么”，并把“样本表”“主要模块摘要”改为“完整索引 + 分层详写”。
- Checker 增加覆盖检查：所有 reachable modules 必须在索引或模块页出现；不得出现“样本”替代完整结构；所有 `evidence_gap` 必须进入对应模块页或全局 gap 汇总。

## Test Plan
- 用 `arm_soc_top` 做 smoke：主手册能列出 106 个模块入口，模块页覆盖全部 reachable modules。
- 检查顶层章节：只含一句项目用途、`rtl/rtl` 目录、`rtl/rtl/SoC/arm_soc_top.v` 顶层文件、顶层组成与端口分组摘要。
- 检查模块页：`IONet_slot`、`cpu_slot`、`cpu_top_all`、`execute`、`timer_module`、`contTap` 分别覆盖关键/叶子/helper 场景。
- 检查 evidence：`ai_inferred` 不写成确定事实，`evidence_gap` 不丢失，受控 RTL 补证内容带来源或 review 标记。
- 检查输出形态：主手册不被 100+ 模块细节淹没，模块页可单独阅读。

## Assumptions
- 手册目标是工程师可读、可查、可 review，而不是 JSON 证据转储。
- “全量模块”指所有 reachable RTL module 都有入口，但不是所有模块等深展开。
- 受控读取 RTL 是补证机制，不恢复自由 LLM 直接写整本手册。
