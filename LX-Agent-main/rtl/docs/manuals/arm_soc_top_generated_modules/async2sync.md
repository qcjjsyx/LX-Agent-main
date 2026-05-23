# 模块 `async2sync`

- 源文件：`rtl\rtl\SoC\async2sync.v`。
- 职责：AI 推断：异步复位同步释放模块，用于将异步复位信号同步到目标时钟域。
- 说明：模块名暗示异步到同步转换，assign依赖显示rst_sync_n由rst_s2驱动，表明复位同步功能

## 1. 层级位置

- Parents：`arm_soc_top`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：其他输入：`clk`, `rst_async_n`。
- 输出：其他输出：`rst_sync_n`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:2, output:1 | `clk`, `rst_async_n`, `rst_sync_n` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| - | - | - | - | Manual Context 未提供接口分组 |

## 4. 主要 Drive-centered Flow

- 证据不足：Manual Context 未提供本模块 drive flow。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供 primary internal component |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_0` | unknown | `rst_sync_n` | rst_s2 | AI 推断：同步后的复位输出，由两级同步器第二级输出驱动 |
