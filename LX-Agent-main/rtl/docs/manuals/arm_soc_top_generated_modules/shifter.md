# 模块 `shifter`

- 源文件：`rtl\rtl\Execute\shifter.v`。
- 职责：AI 推断：移位与扩展单元，根据操作码和类型选择执行逻辑/算术移位、循环移位或位扩展，并输出移位结果和进位。。
- 说明：模块接收32位操作数oprand和8位移位数i_shiftNumber_8，通过i_shiftType_3选择六种移位类型（LSL/LSR/ASR/ROR/RRX/ROL），通过i_shiftOpcode_3和i_xtFlag_1控制零扩展或符号扩展，最终通过i_notFlag_1决定是否取反输出。

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
| `assign_1` | data_path | `{w_lsrResult_32,w_lsrCarryOut_1}` | i_shiftNumber_8 == 8'b0 ? {oprand,1'b0} : {oprand >> i_shiftNumber_8,oprand[i_shiftNumber_8-1]} | AI 推断：逻辑右移进位，当移位数为0时进位为0，否则为移出的最低位。 |
| `assign_2` | unknown | `w_asrCarryOut_1` | i_shiftNumber_8 == 8'b0 ? 1'b0 : (oprand >> ( i_shiftNumber_8 - 1)) | AI 推断：算术右移进位，当移位数为0时进位为0，否则为移出的最低位。 |
| `assign_3` | data_path | `w_asrResult_32` | oprand[31] == 1'b1 ? ((32'hffff_ffff << (32 - i_shiftNumber_8[4:0])) \| (oprand >> i_shiftNumb... | AI 推断：算术右移结果，根据操作数最高位决定是否进行符号扩展。 |
| `assign_4` | unknown | `w_shiftActRorNumber_5` | i_shiftNumber_8 % 32 | AI 推断：循环右移和循环左移结果，通过取模32后的实际移位数实现。 |
| `assign_5` | data_path | `w_rorResult_32` | w_shiftActRorNumber_5 == 5'b0 ? oprand : ((oprand >> w_shiftActRorNumber_5) \| (oprand << (32 ... | AI 推断：循环右移和循环左移结果，通过取模32后的实际移位数实现。 |
| `assign_7` | unknown | `w_shiftActRolNumber_5` | i_shiftNumber_8 % 32 | AI 推断：循环右移和循环左移结果，通过取模32后的实际移位数实现。 |
| ... | ... | ... | ... | 其余 8 条 assign 省略 |
