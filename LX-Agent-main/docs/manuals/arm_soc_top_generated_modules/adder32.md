# 模块 `adder32`

- 源文件：`rtl/rtl/Execute/adder32.v`。
- 职责：AI 推断：32位加法器模块，支持有符号和无符号加法运算，并生成进位和溢出标志。。
- 说明：模块通过assign语句实现两种加法路径（无符号和有符号），并通过symbol信号选择输出结果、进位和溢出标志。无事件输入或控制输入，是一个纯组合逻辑数据通路模块。

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

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `other_ports` | input:4, output:3 | `oprand1`, `oprand2`, `result`, `carry_in`, `symbol`, `carry_out`, `overflow` |

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
| `assign_1` | unknown | `signedSum` | $signed({oprand1[31],oprand1}) + $signed({oprand2[31],oprand2}) + $signed({1'b0,carry_in}) | AI 推断：计算有符号32位加法结果，通过符号扩展防止溢出。 |
| `assign_2` | data_path | `result` | symbol ? unsignedSum[31:0] : signedSum[31:0] | AI 推断：根据symbol信号选择最终加法结果。 |
| `assign_3` | unknown | `carry_out` | symbol ? unsignedSum[32] : 1'b0 | AI 推断：无符号模式下的进位输出。 |
| `assign_4` | data_path | `overflow` | symbol ? 1'b0 : (oprand1[31] == oprand2[31]) && (oprand1[31] != result[31]) | AI 推断：有符号模式下的溢出标志。 |
| `assign_0` | unknown | `unsignedSum` | {1'b0, oprand1} + {1'b0, oprand2} + carry_in | AI 推断：计算无符号32位加法结果，扩展至33位以捕获进位。 |
