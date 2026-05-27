# 模块 `adder`

- **源文件**：`rtl\rtl\Execute\adder.v`
- **职责**（AI 推断）：模块对输入操作数进行位宽预处理，并根据 `i_adderType_2` 选择对应的加法器子模块结果输出。其中 `adder5` 例化使用的 `w_oprand1_5` 和 `w_oprand2_5` 为5位宽线网，由 `i_oprand1_64[31:0]` 和 `i_oprand2_64[31:0]` 经 assign 赋值（发生高位截断，仅保留低5位），位宽与 `adder5` 端口匹配。
- **设计说明**：源码第19‑25行声明了 `wire [4:0] w_oprand1_5, w_oprand2_5`，并通过 assign 将64位输入的低32位分别赋值给这两个5位线网（自动截断为低5位）。第39‑41行 `adder5` 实例化明确使用了这两个5位线网，连接正确，无位宽不匹配问题。

## 1. 层级位置

- **Parents**：`execute`
- **Children**：`adder32`, `adder5`, `adder64`
- **Component children**：无
- **Upstream modules**：无
- **Downstream modules**：无

### 1.1 本模块结构图

```mermaid
flowchart TB
  adder["adder"] --> adder32["adder32"]
  adder["adder"] --> adder5["adder5"]
  adder["adder"] --> adder64["adder64"]
```

```text
adder
|-- adder32
|-- adder5
`-- adder64
```

## 2. 输入/输出接口摘要

- **接收**：数据输入 `i_oprand1_64`, `i_oprand2_64`；控制输入 `i_addSymbolFlag_1`, `i_adderType_2`, `i_carryInType_1`。
- **输出**：数据输出 `o_adderResult_64`；其他输出 `o_adderCarryOut_1`, `o_adderOverFlow_1`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| ------ | -------- | -------- |
| `other_ports` | input:5, output:3 | `i_oprand1_64`, `i_oprand2_64`, `o_adderResult_64`, `i_addSymbolFlag_1`, `i_adderType_2`, `i_carryInType_1`, `o_adderCarryOut_1`, `o_adderOverFlow_1` |

## 3. Drive/Data/Free 契约

| Interface      | 方向   | Event | Payload                                          | Free/backpressure |
| -------------- | ------ | ----- | ------------------------------------------------ | ----------------- |
| `data_inputs`  | input  | -     | `i_oprand1_64 [63:0]`, `i_oprand2_64 [63:0]`     | 未记录            |
| `data_outputs` | output | -     | `o_adderResult_64 [63:0]`                        | 未记录            |
| `control_inputs` | input | -     | 未记录                                           | 未记录            |

## 4. 主要 Drive-centered Flow

- **证据不足**：Manual Context 未提供本模块 drive flow。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| ---- | ---- | -------- | -------- |
| -    | -    | -        | Manual Context 未提供 primary internal component |

### 5.2 assign 影响

| Assign    | Impact area | LHS                | RHS 摘要                                                                                                       | 解释状态                                                     |
| --------- | ----------- | ------------------ | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `assign_0` | data_path   | `w_oprand1_32`     | i_oprand1_64[31:0]                                                                                             | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_1` | data_path   | `w_oprand2_32`     | i_oprand2_64[31:0]                                                                                             | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_2` | data_path   | `w_oprand1_5`      | i_oprand1_64[31:0]                                                                                             | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_3` | data_path   | `w_oprand2_5`      | i_oprand2_64[31:0]                                                                                             | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_4` | data_path   | `o_adderResult_64` | i_adderType_2 == 2'b00 ? w_adder32Result_32 : (i_adderType_2==2'b01 ? w_adder5Result_5 :(i_ad...              | AI 推断：根据 `i_adderType_2` 选择对应加法器结果输出至 `o_adderResult_64`。 |
| `assign_5` | unknown     | `o_adderCarryOut_1`| i_adderType_2 == 2'b00 ? w_adder32CarryOut_1 : (i_adderType_2==2'b01 ? w_adder5CarryOut_1 :(i...              | AI 推断：根据 `i_adderType_2` 选择对应进位输出。               |
| `assign_6` | data_path   | `o_adderOverFlow_1`| i_adderType_2 == 2'b00 ? w_adder32OverFlow_1 : (i_adderType_2==2'b01 ? w_adder5OverFlow_1 :(i...             | AI 推断：根据 `i_adderType_2` 选择对应溢出标志输出。           |
