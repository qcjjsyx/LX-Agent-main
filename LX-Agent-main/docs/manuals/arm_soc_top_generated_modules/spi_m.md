# 模块 `spi_m`

- 源文件：`rtl\rtl\IONet\SPI\SPI1\spi_m.v`。
- 职责：**AI 推断**：该模块实现了带 CRC 计算/校验功能的 SPI 主机控制器，负责数据的收发和传输完成状态管理。
- 说明：在 compact 上下文中，数据输入包括发送数据 `data_in` 与 CRC 校验值 `TXCRC`，数据输出为 `data_out`；assign 依赖中出现的 `busy`、`rx_done`、`tx_done`、`crc_done` 等信号表明模块内部生成传输状态，并控制数据帧完成判断。无内部实例化，推测逻辑均由本模块实现，承担完整的 SPI 主设备功能和 CRC 处理。

## 1. 层级位置

- Parents：`SPI_control`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- **接收（输入）**：数据输入为 `TXCRC`、`data_in`；其他输入包括 `CPHA`、`CRC_next`、`DFF`、`DR_r` 等（共 14 个输入端口）。
- **发送（输出）**：数据输出为 `data_out`；其他输出包括 `OVR`、`RXNE`、`TXE`、`busy` 等（共 8 个输出端口）。

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

- **证据不足**：Manual Context 未提供本模块 drive flow。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供 primary internal component |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_1` | unknown | `rx_done` | (rxonly^DFF) ? (DFF ? ((~rx_cnt[4]) & cnt_buf_rx) : (~rx_cnt[2]) & cnt_buf_rx) : ((~rx_cnt[3]... | **证据不足**：缺少语义层赋值解释。 |
| `assign_2` | unknown | `tx_done` | (CPHA^DFF) ? ((~tx_cnt[3]) & cnt_buf_tx) : (DFF ? ((~tx_cnt[4]) & cnt_buf_tx) : (~tx_cnt[2]) ... | **证据不足**：缺少语义层赋值解释。 |
| `assign_3` | unknown | `crc_done` | (CPHA^DFF) ? ((~crc_cnt[3]) & cnt_buf_crc) : (DFF ? ((~crc_cnt[4]) & cnt_buf_crc) : (~crc_cnt... | **证据不足**：缺少语义层赋值解释。 |
| `assign_0` | unknown | `busy` | enable \| !TXE \| crc_en | **证据不足**：缺少语义层赋值解释。 |
