# 模块 `adder5`

- 源文件：`rtl\rtl\Execute\adder5.v`
- 职责：**AI 推断**：组合逻辑 5 位双模加法器，根据 `symbol` 信号选择无符号或有符号运算，提供进位输入/输出和溢出检测。
- 说明：紧凑的纯组合逻辑接口，提供两个 5 位操作数输入和一个 5 位结果输出；内部通过 assign 链实现两种运算模式，`carry_in` 参与扩展加法，`carry_out` 和 `overflow` 标志根据模式和操作数动态产生，无时钟或复位。

## 1. 层级位置

- Parents：`adder`
- Children：无
- Component children：无
- Upstream modules：无
- Downstream modules：无

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入 `oprand1`、`oprand2`；其他输入 `carry_in`、`symbol`
- 输出：数据输出 `result`；其他输出 `carry_out`、`overflow`

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `other_ports` | input:4, output:3 | `oprand1`, `oprand2`, `result`, `carry_in`, `symbol`, `carry_out`, `overflow` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `oprand1 [4:0]`, `oprand2 [4:0]` | 未记录 |
| `data_outputs` | output | - | `result [4:0]` | 未记录 |

## 4. 主要 Drive-centered Flow

- **证据不足**：Manual Context 未提供本模块 drive flow。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供 primary internal component |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_0` | unknown | `unsignedSum` | `{1'b0, oprand1} + {1'b0, oprand2} + carry_in` | **AI 推断**：无符号和计算，将 `oprand1`、`oprand2` 零扩展为 6 位并加上 `carry_in`，产生 6 位结果 `unsignedSum` |
| `assign_1` | data_path | `signedSum` | `$signed({oprand1[4], oprand1}) + $signed({oprand2[4], oprand2}) + $signed({1'b0,carry_in})` | **AI 推断**：有符号和计算，将 `oprand1`、`oprand2` 符号扩展为 6 位并加上 `carry_in`，产生 6 位结果 `signedSum` |
| `assign_2` | data_path | `result` | `symbol ? unsignedSum[4:0] : signedSum[4:0]` | **AI 推断**：结果选择，根据 `symbol` 选择 `unsignedSum` 或 `signedSum` 的低 5 位作为 `result`。当 `symbol` 为真时选无符号和，否则选有符号和 |
| `assign_3` | unknown | `carry_out` | `symbol ? unsignedSum[5] : 1'b0` | **AI 推断**：进位输出生成，仅当 `symbol` 选择无符号模式时输出 `unsignedSum` 的第 5 位，否则为 0 |
| `assign_4` | data_path | `overflow` | `symbol ? 1'b0 : (oprand1[4] == oprand2[4]) && (oprand1[4] != result[4])` | **AI 推断**：有符号溢出标志计算，仅在 `symbol` 为假（有符号模式）时根据操作数和结果符号判断，否则固定为 0 |
