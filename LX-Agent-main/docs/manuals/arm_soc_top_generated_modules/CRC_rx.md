# 模块 `CRC_rx`

- 源文件：`rtl\rtl\IONet\SPI\SPI1\CRC_rx.v`。
- 职责：AI 推断：该模块根据输入数据和多项式并行计算 CRC 值，并通过选择信号在 16 位和 8 位 CRC 结果间切换，最终输出到 `CRC_out`。
- 说明：接口包含 16 位的 `datain` 和 `poly` 输入，以及 16 位的 `CRC_out` 输出。从可见的连续赋值中，`CRC_out` 由内部信号 `DFF` 选择 `CRC16_reg` 或零扩展的 `CRC8_reg`。这表明模块内部同时计算两种宽度的 CRC，并由 `DFF` 决定输出格式，符合接收端校验的用途。由于源码中未暴露内部计算逻辑和 `DFF` 的产生来源，上述结论基于端口合约推断，AI 认为模块承担数据驱动的 CRC 生成角色。

## 1. 层级位置

- Parents：`SPI_control`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 输入（共 8 个）：`datain`、`poly`、`CRC_en`、`CRC_next`、`DFF`、`RXNE`、`clk`、`rst_n`。
- 输出（共 3 个）：`CRC_out`、`CRCERR`、`CRC_busy`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:2 | `clk`, `rst_n` |
| `other_ports` | input:6, output:3 | `datain`, `poly`, `CRC_out`, `CRC_en`, `CRC_next`, `DFF`, `RXNE`, `CRCERR`, `CRC_busy` |

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
| `assign_0` | unknown | `CRC_out` | `DFF ? CRC16_reg : {8'b0,CRC8_reg}` | AI 推断：该赋值实现 16 位 CRC 直通或 8 位 CRC 零扩展至 16 位的选择输出，满足统一总线宽度要求。 |
