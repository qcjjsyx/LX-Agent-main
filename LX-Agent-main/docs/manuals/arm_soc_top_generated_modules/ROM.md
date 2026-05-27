# 模块 `ROM`

- 源文件：`rtl\rtl\memory\ROM.v`。
- 职责：AI 推断：ROM 是一个只读存储器模块，根据地址输入提供指令或常量数据输出，用于 SoC 的取指或常量表访问。
- 说明：接口仅包含数据输入 `i_addr` 和数据输出 `o_data`，没有握手或控制信号，表明该模块是简单的只读存储器，典型用途为指令存储器或固定数据表。内部存储阵列 `rom_mem` 通过 `assign` 拼接两个相邻地址的数据产生 64 位输出，符合 64 位取指场景。

## 1. 层级位置

- Parents：`socmem`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`i_addr`；其他输入：`clk`。
- 输出：数据输出：`o_data`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:1 | `clk` |
| `other_ports` | input:1, output:1 | `i_addr`, `o_data` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `i_addr [11:0]` | 未记录 |
| `data_outputs` | output | - | `o_data [63:0]` | 未记录 |

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
| `assign_0` | data_path | `o_data` | {rom_mem[addr+10'd1],rom_mem[addr]} | 证据不足：No Semantic Layer assignment interpretation is available. |
