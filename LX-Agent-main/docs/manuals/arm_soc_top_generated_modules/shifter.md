# 模块 `shifter`

- 源文件：`rtl\rtl\Execute\shifter.v`
- AI 推断职责：组合逻辑移位器与旋转器，支持多种移位类型，并能根据控制标志进行符号/零扩展及按位取反。
- 功能说明：该模块以操作数 `oprand` 和移位量 `i_shiftNumber_8` 为输入，独立计算出逻辑左移 (LSL)、逻辑右移 (LSR)、算术右移 (ASR)、右旋转 (ROR)、带进位右移 (RRX) 及左旋转 (ROL) 的结果与进位。随后由控制信号 `i_shiftType_3` 选择移位类型，`i_shiftOpcode_3` 与 `i_xtFlag_1` 控制字节/半字大小的零扩展或符号扩展，最后通过 `i_notFlag_1` 可选地按位取反，输出最终的 `result`。该设计使其成为执行阶段中一个可灵活配置的移位数据通路。

## 1. 层级位置

- Parents：`execute`
- Children：无
- Component children：无
- Upstream modules：无
- Downstream modules：无

### 1.1 内部结构

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入 / 输出接口摘要

### 2.1 端口列表

**输入**
- `i_carryIn_1`：进位输入
- `i_notFlag_1`：取反使能
- `i_shiftNumber_8`：移位量
- `i_shiftOpcode_3`：操作码（控制扩展方式）
- `i_shiftType_3`：移位类型选择
- `i_xtFlag_1`：符号/零扩展控制
- `oprand`：操作数数据

**输出**
- `o_carryOut_1`：进位输出
- `result`：移位/旋转/扩展/取反后的结果

### 2.2 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `other_ports` | input:7, output:2 | `i_shiftNumber_8`, `oprand`, `result`, `i_notFlag_1`, `i_shiftOpcode_3`, `i_shiftType_3`, `i_xtFlag_1`, `i_carryIn_1`, `o_carryOut_1` |

## 3. Drive / Data / Free 契约

| Interface | 方向 | Event | Payload | Free / backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `i_shiftNumber_8 [7:0]`, `oprand [31:0]` | 未记录 |
| `data_outputs` | output | - | `result [31:0]` | 未记录 |
| `control_inputs` | input | - | 未记录 | 未记录 |

## 4. 主要 Drive‑centered Flow

- 证据不足：Manual Context 未提供本模块的 drive flow。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供 primary internal component |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_1` | data_path | `{w_lsrResult_32,w_lsrCarryOut_1}` | `i_shiftNumber_8 == 8'b0 ? {oprand,1'b0} : {oprand >> i_shiftNumber_8,oprand[i_shiftNumber_8-1]}` | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_2` | unknown | `w_asrCarryOut_1` | `i_shiftNumber_8 == 8'b0 ? 1'b0 : (oprand >> ( i_shiftNumber_8 - 1))` | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_3` | data_path | `w_asrResult_32` | `oprand[31] == 1'b1 ? ((32'hffff_ffff << (32 - i_shiftNumber_8[4:0])) \| (oprand >> i_shiftNumb...` | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_4` | unknown | `w_shiftActRorNumber_5` | `i_shiftNumber_8 % 32` | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_5` | data_path | `w_rorResult_32` | `w_shiftActRorNumber_5 == 5'b0 ? oprand : ((oprand >> w_shiftActRorNumber_5) \| (oprand << (32 ...` | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_7` | unknown | `w_shiftActRolNumber_5` | `i_shiftNumber_8 % 32` | 证据不足：No Semantic Layer assignment interpretation is available. |
| ... | ... | ... | ... | 其余 8 条 assign 省略 |
