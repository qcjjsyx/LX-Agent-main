# 模块 `async2sync`

- 源文件：`rtl/rtl/SoC/async2sync.v`。
- 职责：AI 推断：确认模块为异步复位同步释放电路，输出同步复位信号。
- 说明：切片第2-7行声明clk、rst_async_n、rst_sync_n端口；第9-18行定义两級寄存器链，posedge clk与negedge rst_async_n触发，异步复位时清零，释放后级联传递1'b1；第20行assign将第二级rst_s2连至输出rst_sync_n，构成典型异步复位同步释放（双触发器同步器）

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
| `assign_0` | unknown | `rst_sync_n` | rst_s2 | AI 推断：将内部同步后的复位信号rst_s2直接赋值给输出复位信号rst_sync_n |
