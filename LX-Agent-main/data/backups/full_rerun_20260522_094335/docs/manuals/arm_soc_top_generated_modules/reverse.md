# 模块 `reverse`

- 源文件：`rtl/rtl/Execute/reverse.v`。
- 职责：AI 推断：该模块根据reverseType选择四种位反转/字节交换操作之一，将输入oprand转换为输出result。。
- 说明：模块无事件接口，仅通过组合逻辑实现数据转换。assign依赖显示w_rbitResult_32、w_revResult_32、w_rev16Result_32、w_revshResult_32四个中间结果，最终由reverseType多路选择输出。

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
| `assign_1` | data_path | `w_rbitResult_32[30]` | oprand[1] | AI 推断：对oprand进行逐位反转，bit[31]对应oprand[0]，bit[0]对应oprand[31]。 |
| `assign_2` | data_path | `w_rbitResult_32[29]` | oprand[2] | AI 推断：对oprand进行逐位反转，bit[31]对应oprand[0]，bit[0]对应oprand[31]。 |
| `assign_3` | data_path | `w_rbitResult_32[28]` | oprand[3] | AI 推断：对oprand进行逐位反转，bit[31]对应oprand[0]，bit[0]对应oprand[31]。 |
| `assign_4` | data_path | `w_rbitResult_32[27]` | oprand[4] | AI 推断：对oprand进行逐位反转，bit[31]对应oprand[0]，bit[0]对应oprand[31]。 |
| `assign_5` | data_path | `w_rbitResult_32[26]` | oprand[5] | AI 推断：对oprand进行逐位反转，bit[31]对应oprand[0]，bit[0]对应oprand[31]。 |
| `assign_6` | data_path | `w_rbitResult_32[25]` | oprand[6] | AI 推断：对oprand进行逐位反转，bit[31]对应oprand[0]，bit[0]对应oprand[31]。 |
| ... | ... | ... | ... | 其余 9 条 assign 省略 |
