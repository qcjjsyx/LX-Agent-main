# 模块 `spi_m`

- 源文件：`rtl/rtl/IONet/SPI/SPI1/spi_m.v`。
- 职责：AI 推断：SPI主设备控制器，负责管理SPI总线的发送、接收和CRC校验时序。
- 说明：模块通过内部计数器（tx_cnt、rx_cnt、crc_cnt）和状态信号（busy、tx_done、rx_done、crc_done）控制SPI数据传输的完整流程，支持可配置的时钟相位（CPHA）和数据帧格式（DFF）

## 1. 层级位置

- Parents：`SPI_control`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`TXCRC`, `data_in`；其他输入：`CPHA`, `CRC_next`, `DFF`, `DR_r`, `... +8`。
- 输出：数据输出：`data_out`；其他输出：`OVR`, `RXNE`, `TXE`, `busy`, `... +3`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:4 | `LSBFIRST`, `clk`, `rst_n`, `sclk` |
| `other_ports` | input:10, output:8 | `TXCRC`, `data_in`, `data_out`, `CPHA`, `CRC_next`, `DFF`, `DR_r`, `DR_w`, `M_en`, `rx`, `... +8` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `TXCRC [15:0]`, `data_in [15:0]` | 未记录 |
| `data_outputs` | output | - | `data_out [15:0]` | 未记录 |

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
| `assign_1` | unknown | `rx_done` | (rxonly^DFF) ? (DFF ? ((~rx_cnt[4]) & cnt_buf_rx) : (~rx_cnt[2]) & cnt_buf_rx) : ((~rx_cnt[3]... | AI 推断：接收完成条件根据rxonly模式和DFF配置动态选择不同位宽的计数器比较 |
| `assign_2` | unknown | `tx_done` | (CPHA^DFF) ? ((~tx_cnt[3]) & cnt_buf_tx) : (DFF ? ((~tx_cnt[4]) & cnt_buf_tx) : (~tx_cnt[2]) ... | AI 推断：发送完成条件由CPHA和DFF共同决定计数器位宽选择 |
| `assign_3` | unknown | `crc_done` | (CPHA^DFF) ? ((~crc_cnt[3]) & cnt_buf_crc) : (DFF ? ((~crc_cnt[4]) & cnt_buf_crc) : (~crc_cnt... | AI 推断：CRC校验完成条件与发送完成逻辑结构相同，使用独立的CRC计数器 |
| `assign_0` | unknown | `busy` | enable \| !TXE \| crc_en | AI 推断：模块忙状态由使能信号、发送FIFO空标志和CRC使能共同决定 |
