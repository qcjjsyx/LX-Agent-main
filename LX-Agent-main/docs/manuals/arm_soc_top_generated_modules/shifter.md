# 模块 `shifter`

- 源文件：`rtl/rtl/Execute/shifter.v`。
- 职责：AI 推断：执行多种移位和扩展操作的组合逻辑数据通路模块。
- 说明：模块通过组合逻辑实现左移、右移、算术右移、循环左移、循环右移、带进位循环右移六种移位操作，以及零扩展和符号扩展功能，最终根据控制信号选择输出结果。

## 1. 层级位置

- Parents：`execute`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`i_shiftNumber_8`, `oprand`；控制输入：`i_notFlag_1`, `i_shiftOpcode_3`, `i_shiftType_3`, `i_xtFlag_1`；其他输入：`i_carryIn_1`。
- 输出：数据输出：`result`；其他输出：`o_carryOut_1`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `other_ports` | input:7, output:2 | `i_shiftNumber_8`, `oprand`, `result`, `i_notFlag_1`, `i_shiftOpcode_3`, `i_shiftType_3`, `i_xtFlag_1`, `i_carryIn_1`, `o_carryOut_1` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `i_shiftNumber_8 [7:0]`, `oprand [31:0]` | 未记录 |
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
| `assign_1` | data_path | `{w_lsrResult_32,w_lsrCarryOut_1}` | i_shiftNumber_8 == 8'b0 ? {oprand,1'b0} : {oprand >> i_shiftNumber_8,oprand[i_shiftNumber_8-1]} | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_2` | unknown | `w_asrCarryOut_1` | i_shiftNumber_8 == 8'b0 ? 1'b0 : (oprand >> ( i_shiftNumber_8 - 1)) | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_3` | data_path | `w_asrResult_32` | oprand[31] == 1'b1 ? ((32'hffff_ffff << (32 - i_shiftNumber_8[4:0])) \| (oprand >> i_shiftNumb... | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_4` | unknown | `w_shiftActRorNumber_5` | i_shiftNumber_8 % 32 | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_5` | data_path | `w_rorResult_32` | w_shiftActRorNumber_5 == 5'b0 ? oprand : ((oprand >> w_shiftActRorNumber_5) \| (oprand << (32 ... | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_7` | unknown | `w_shiftActRolNumber_5` | i_shiftNumber_8 % 32 | 证据不足：No Semantic Layer assignment interpretation is available. |
| ... | ... | ... | ... | 其余 8 条 assign 省略 |
