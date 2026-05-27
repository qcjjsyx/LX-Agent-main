# 模块 `adder32`

- 源文件：`rtl\rtl\Execute\adder32.v`。
- 职责：AI 推断：此模块是一个组合逻辑的32位加法器，支持通过 `symbol` 控制位在无符号与带符号算术间切换，并生成进位输出与有符号溢出标志。
- 说明：所有输出均由连续赋值产生，无内部时序元件或子实例。接口包含两个32位操作数输入，一个32位结果输出，以及控制输入 `symbol`、进位输入 `carry_in`、进位输出 `carry_out` 和溢出输出 `overflow`。这些信号在赋值依赖关系中明确参与运算。

## 1. 层级位置

- Parents：`adder`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`oprand1`, `oprand2`；其他输入：`carry_in`, `symbol`。
- 输出：数据输出：`result`；其他输出：`carry_out`, `overflow`。

| 端口名 | 方向 | 位宽 | 描述 |
| --- | --- | --- | --- |
| `oprand1` | input | 32 | 操作数1 |
| `oprand2` | input | 32 | 操作数2 |
| `carry_in` | input | 1 | 进位输入 |
| `symbol` | input | 1 | 控制位：0=带符号运算，1=无符号运算 |
| `result` | output | 32 | 加法结果 |
| `carry_out` | output | 1 | 进位输出（仅在无符号模式有效） |
| `overflow` | output | 1 | 带符号溢出标志 |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `oprand1 [31:0]`, `oprand2 [31:0]` | 未记录 |
| `data_outputs` | output | - | `result [31:0]` | 未记录 |

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
| `assign_0` | unknown | `unsignedSum` | `{1'b0, oprand1} + {1'b0, oprand2} + carry_in` | AI 推断：无符号加法，生成33位结果用于进位和最终选择。 |
| `assign_1` | unknown | `signedSum` | `$signed({oprand1[31],oprand1}) + $signed({oprand2[31],oprand2}) + $signed({1'b0,carry_in})` | AI 推断：带符号加法，通过符号扩展生成33位结果，用于进位捕获和低位和。 |
| `assign_2` | data_path | `result` | `symbol ? unsignedSum[31:0] : signedSum[31:0]` | AI 推断：根据 `symbol` 选择无符号或带符号加法的低32位作为最终结果。 |
| `assign_3` | unknown | `carry_out` | `symbol ? unsignedSum[32] : 1'b0` | AI 推断：仅在无符号模式下输出进位，否则为0。 |
| `assign_4` | data_path | `overflow` | `symbol ? 1'b0 : (oprand1[31] == oprand2[31]) && (oprand1[31] != result[31])` | 证据不足：No Semantic Layer assignment interpretation is available. |
