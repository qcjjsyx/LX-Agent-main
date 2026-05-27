# 模块 `async2sync`

- **源文件**：`rtl\rtl\SoC\async2sync.v`
- **功能**（AI 推断）：该模块是一个异步复位同步器（异步复位、同步释放），产生与时钟同步的复位输出 `rst_sync_n`。
- **实现细节**：源码定义了输入端口 `clk`、`rst_async_n`，输出端口 `rst_sync_n`。内部包含两级同步寄存器 `rst_s1` 和 `rst_s2`：在时钟上升沿且异步复位 `rst_async_n` 无效（高电平）时，传递高电平；当异步复位有效（低电平）时，两级寄存器立即清零。最终通过 `assign` 将 `rst_s2` 的值驱动至 `rst_sync_n`。该结构完全符合异步复位同步释放的经典设计。

## 1. 层级位置

- **Parents**：`arm_soc_top`
- **Children**：无
- **Component children**：无
- **Upstream modules**：无
- **Downstream modules**：无

### 1.1 本模块结构图

本模块不包含子模块或内部实例，仅由两级寄存器和一根 assign 线构成。

## 2. 输入/输出接口摘要

- **输入**：`clk`, `rst_async_n`
- **输出**：`rst_sync_n`

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | 输入:2, 输出:1 | `clk`, `rst_async_n`, `rst_sync_n` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| - | - | - | - | Manual Context 未提供接口分组 |

> **证据不足**：Manual Context 未定义任何接口级契约。

## 4. 主要 Drive‑centered Flow

- **证据不足**：Manual Context 未提供本模块的 drive flow。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供主要内部组件 |

### 5.2 assign 影响

| Assign | 影响区域 | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_0` | unknown | `rst_sync_n` | rst_s2 | **证据不足**：缺少语义层 assign 解释 |
