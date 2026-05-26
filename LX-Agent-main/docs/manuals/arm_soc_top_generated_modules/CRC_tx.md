# 模块 `CRC_tx`

- 源文件：`rtl/rtl/IONet/SPI/SPI1/CRC_tx.v`。
- 职责：AI 推断：该模块根据输入数据计算并输出CRC校验值，支持16位和8位两种模式。。
- 说明：模块接收16位数据输入datain和多项式poly，输出16位CRC结果CRC_out。通过assign依赖中DFF信号选择CRC16_reg或CRC8_reg，表明模块内部存在一个16位/8位CRC计算状态机或寄存器组，由DFF信号控制输出模式。

## 1. 层级位置

- Parents：`SPI_control`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`datain`, `poly`；其他输入：`CRC_en`, `DFF`, `clk`, `crc_en`, `... +2`。
- 输出：数据输出：`CRC_out`；其他输出：`CRC_busy`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:2 | `clk`, `rst_n` |
| `other_ports` | input:6, output:2 | `datain`, `poly`, `CRC_out`, `CRC_en`, `DFF`, `crc_en`, `enable`, `CRC_busy` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `datain [15:0]`, `poly [15:0]` | 未记录 |
| `data_outputs` | output | - | `CRC_out [15:0]` | 未记录 |

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
| `assign_1` | unknown | `enable_rise` | (~enable_buf) & enable | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_0` | unknown | `CRC_out` | DFF ? CRC16_reg : {8'b0,CRC8_reg} | 证据不足：No Semantic Layer assignment interpretation is available. |
