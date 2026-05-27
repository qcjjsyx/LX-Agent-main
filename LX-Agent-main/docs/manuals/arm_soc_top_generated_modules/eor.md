# 模块 `eor`

- 源文件：`rtl\rtl\Execute\eor.v`
- 职责：AI 推断：该模块是一个纯组合逻辑的位异或运算单元，用于数据通路中的算术或逻辑运算。
- 说明：模块仅有两个 32 位数据输入 `oprand1` 和 `oprand2`，以及一个 32 位数据输出 `result`。通过组合赋值 `result = oprand1 ^ oprand2` 直接驱动，表明其为一个完全无状态的按位异或单元，可能作为 ALU 的一部分或执行阶段的辅助逻辑使用。

## 1. 层级位置

- **Parents**：`execute`
- **Children**：无
- **Component children**：无
- **Upstream modules**：无
- **Downstream modules**：无

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`oprand1`、`oprand2`
- 输出：数据输出：`result`

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `other_ports` | input:2, output:1 | `oprand1`, `oprand2`, `result` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `oprand1 [31:0]`, `oprand2 [31:0]` | 未记录 |
| `data_outputs` | output | - | `result [31:0]` | 未记录 |

## 4. 主要 Drive-centered Flow

- 证据不足：Manual Context 未提供本模块的 drive flow。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供主要内部组件 |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_0` | data_path | `result` | oprand1^oprand2 | 证据不足：No Semantic Layer assignment interpretation is available. |
