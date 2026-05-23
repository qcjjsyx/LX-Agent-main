# 模块 `CRC_rx`

- 源文件：`rtl\rtl\IONet\SPI\SPI1\CRC_rx.v`。
- 职责：AI 推断：该模块根据输入数据流和多项式配置计算并输出CRC校验值。。
- 说明：模块接收16位数据输入(datain)和16位多项式(poly)，通过内部寄存器(CRC16_reg, CRC8_reg)计算CRC，最终通过选择器(DFF)输出16位CRC结果(CRC_out)。无事件接口，表明其为纯组合或时序计算单元。

## 1. 层级位置

- Parents：`SPI_control`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`datain`, `poly`；其他输入：`CRC_en`, `CRC_next`, `DFF`, `RXNE`, `... +2`。
- 输出：数据输出：`CRC_out`；其他输出：`CRCERR`, `CRC_busy`。

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
| `assign_0` | unknown | `CRC_out` | DFF ? CRC16_reg : {8'b0,CRC8_reg} | AI 推断：该赋值实现CRC结果的多路选择输出，根据DFF信号在16位和8位CRC之间切换。 |
