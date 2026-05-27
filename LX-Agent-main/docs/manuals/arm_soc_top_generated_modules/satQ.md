# 模块 `satQ`

- 源文件：`rtl\rtl\Execute\satQ.v`。
- 职责：AI 推断：组合逻辑饱和运算模块，根据位宽参数对输入数据进行有符号或无符号饱和处理。
- 说明：接口仅包含两个数据输入、一个数据输出以及一个 1 位控制输入，无时序逻辑或子模块实例。内部连续赋值链对 `i_oprand1_32` 进行钳位，将 `i_oprand2_32` 的低 6 位解释为位宽 n，通过 `i_satQSymbolFlag_1` 选择有符号饱和（1）或无符号饱和（0），最终输出 `o_saQResult_32`。模块承担“饱和单元”角色。

## 1. 层级位置

- Parents：`execute`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`i_oprand1_32`, `i_oprand2_32`；控制输入：`i_satQSymbolFlag_1`。
- 输出：数据输出：`o_saQResult_32`；其他输出：`sat`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `other_ports` | input:3, output:2 | `i_oprand1_32`, `i_oprand2_32`, `o_saQResult_32`, `i_satQSymbolFlag_1`, `sat` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `i_oprand1_32 [31:0]`, `i_oprand2_32 [31:0]` | 未记录 |
| `data_outputs` | output | - | `o_saQResult_32 [31:0]` | 未记录 |
| `control_inputs` | input | - | 未记录 | 未记录 |

## 4. 主要 Drive‑centered Flow

- 证据不足：Manual Context 未提供本模块 drive flow。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供 primary internal component |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_1` | data_path | `w_saturated1_32` | w_maxOprand1_32 > $signed(1<<(i_oprand2_32[5:0] - 1)-1) ? $signed(1<<(i_oprand2_32[5:0] - 1)-... | AI 推断：实现有符号饱和：将 `i_oprand1_32` 钳位在 [-2^(n-1), 2^(n-1)-1] 范围内，并产生超限标志 `w_sat1_1`。 |
| `assign_2` | data_path | `w_sat1_1` | ( i_oprand1_32 < $signed(-(1<<(i_oprand2_32[5:0]-1))) ) \|\| (i_oprand1_32 >= 1<<(i_oprand2_32[... | AI 推断：实现有符号饱和：将 `i_oprand1_32` 钳位在 [-2^(n-1), 2^(n-1)-1] 范围内，并产生超限标志 `w_sat1_1`。 |
| `assign_3` | data_path | `w_maxOprand2_32` | i_oprand1_32 > 0 ? i_oprand1_32 : 0 | AI 推断：实现无符号饱和：将 `i_oprand1_32` 钳位在 [0, 2^n-1] 范围内，并产生超限标志 `w_sat2_1`。 |
| `assign_4` | data_path | `w_satuarted2_32` | w_maxOprand2_32 > ((1<<i_oprand2_32[5:0]) - 1) ? (1<<i_oprand2_32[5:0]) - 1 : w_maxOprand2_32 | AI 推断：实现无符号饱和：将 `i_oprand1_32` 钳位在 [0, 2^n-1] 范围内，并产生超限标志 `w_sat2_1`。 |
| `assign_5` | data_path | `w_sat2_1` | (i_oprand1_32 < 0) \|\| (i_oprand1_32 >= 1<<i_oprand2_32[5:0]) | AI 推断：实现无符号饱和：将 `i_oprand1_32` 钳位在 [0, 2^n-1] 范围内，并产生超限标志 `w_sat2_1`。 |
| `assign_6` | control_path | `o_saQResult_32` | i_satQSymbolFlag_1 == 1'b1 ? w_saturated1_32 : w_satuarted2_32 | AI 推断：根据 `i_satQSymbolFlag_1` 选择有符号或无符号饱和输出，并输出饱和标志。 |
| ... | ... | ... | ... | 其余 2 条 assign 省略 |
