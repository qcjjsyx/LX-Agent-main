# 模块 `decoder_32`

- 源文件：`rtl/rtl/Decode/decoder_32.v`。
- 职责：AI 推断：32位Thumb指令解码器，将输入的64位指令包解码为187位发射数据和控制信号。。
- 说明：模块接收64位指令数据，通过大量组合逻辑解码出指令类型、操作数、立即数、条件码等，并打包成187位的发射数据结构，同时生成异常编号和NZCV写使能信号。

## 1. 层级位置

- Parents：`decoder`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：drive 输入：`i_drive`；数据输入：`i_data_64`；free 输入：`i_free`。
- 输出：drive 输出：`o_drive`；数据输出：`o_blImm9_9`, `o_data_187`, `o_excNum_4`；控制输出：`o_nzcvWen_4`；free 输出：`o_free`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `drive_event` | input:1, output:1 | `i_drive`, `o_drive` |
| `free_backpressure` | input:1, output:1 | `i_free`, `o_free` |
| `other_ports` | input:1, output:4 | `i_data_64`, `o_blImm9_9`, `o_data_187`, `o_excNum_4`, `o_nzcvWen_4` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `i_drive` | input | `i_drive` | `i_data_64 [63:0]` | 未记录 |
| `o_drive` | output | `o_drive` | 未记录 | 未记录 |

## 4. 主要 Drive-centered Flow

### `i_drive`

- 确定性事实：`i_drive to o_drive`；flow_id=`flow_000_decoder_32_i_drive`。
- Payload：`i_drive` -> `i_data_64 [63:0]`。
- 输出/影响：`o_drive`。
- 结构复杂度：branch=0，join=0，blocking=0。
- AI 推断：最终手册应强调该流为纯事件传递路径，并说明数据负载的拆分独立于事件流。


## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供 primary internal component |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_0` | data_path | `{w_pc_32, w_int_32}` | i_data_64 | 证据不足：No Semantic Layer assignment interpretation is available. |
