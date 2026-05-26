# 模块 `decoder_16`

- 源文件：`rtl/rtl/Decode/decoder_16.v`。
- 职责：AI 推断：16位Thumb指令解码器，将16位指令字解码为187位内部微操作控制字。
- 说明：模块接收64位数据输入，其中包含16位指令字，通过大量组合逻辑解码出指令类型、操作数、标志位等控制信号，最终打包成187位宽的解码数据发送到执行阶段

## 1. 层级位置

- Parents：`decoder`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：drive 输入：`i_drive`；数据输入：`i_data_64`；free 输入：`i_free`；其他输入：`i_isInInt`。
- 输出：drive 输出：`o_drive1`；数据输出：`o_data_187`, `o_excNum_4`；控制输出：`o_nzcvWen_4`；free 输出：`o_free`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `drive_event` | input:1, output:1 | `i_drive`, `o_drive1` |
| `free_backpressure` | input:1, output:1 | `i_free`, `o_free` |
| `other_ports` | input:2, output:3 | `i_data_64`, `o_data_187`, `o_excNum_4`, `o_nzcvWen_4`, `i_isInInt` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `i_drive` | input | `i_drive` | `i_data_64 [63:0]` | 未记录 |
| `o_drive1` | output | `o_drive1` | 未记录 | 未记录 |

## 4. 主要 Drive-centered Flow

### `i_drive`

- 确定性事实：`decoder_16 flow from i_drive`；flow_id=`flow_000_decoder_16_i_drive`。
- Payload：`i_drive` -> `i_data_64 [63:0]`。
- 输出/影响：证据不足：Knowledge IR did not find a module output endpoint for this flow.。
- 结构复杂度：branch=0，join=0，blocking=0。


## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供 primary internal component |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_1` | control_path | `o_free` | i_free | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_2` | data_path | `{w_pc_32, w_zero_16, w_int_16}` | i_data_64 | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_0` | control_path | `o_drive1` | i_drive | 证据不足：No Semantic Layer assignment interpretation is available. |
