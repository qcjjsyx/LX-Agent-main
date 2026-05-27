# 模块 `reverse`

- 源文件：`rtl\rtl\Execute\reverse.v`。
- 职责：AI 推断：根据控制信号对输入操作数执行四种数据反转操作的组合逻辑模块。
- 说明：无事件或状态寄存器，所有输出由assign组合生成。接口仅有数据输入、控制输入和数据输出，符合纯功能单元的设计意图。

## 1. 层级位置

- Parents：`execute`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`oprand`；控制输入：`reverseType`。
- 输出：数据输出：`result`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `other_ports` | input:2, output:1 | `oprand`, `result`, `reverseType` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `oprand [31:0]` | 未记录 |
| `data_outputs` | output | - | `result [31:0]` | 未记录 |
| `control_inputs` | input | - | 未记录 | 未记录 |

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
| `assign_1` | data_path | `w_rbitResult_32[30]` | oprand[1] | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_2` | data_path | `w_rbitResult_32[29]` | oprand[2] | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_3` | data_path | `w_rbitResult_32[28]` | oprand[3] | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_4` | data_path | `w_rbitResult_32[27]` | oprand[4] | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_5` | data_path | `w_rbitResult_32[26]` | oprand[5] | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_6` | data_path | `w_rbitResult_32[25]` | oprand[6] | 证据不足：No Semantic Layer assignment interpretation is available. |
| ... | ... | ... | ... | 其余 9 条 assign 省略 |
