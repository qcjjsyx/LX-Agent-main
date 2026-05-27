# 模块 `spi_master_spi0`

- 源文件：`rtl\rtl\IONet\SPI\SPI0\spi_master_spi0.v`
- 职责：AI 推断：该模块是 SPI 主机控制器，负责生成 SPI 串行时钟、片选信号并管理数据收发。
- 说明：模块名称明确包含“spi_master”，接口提供 CR 控制寄存器、data_in 发送数据、data_out 接收数据，未出现事件握手信号，符合纯数据驱动的 SPI 主机结构；内部通过分频器 `clk_div_u` 产生基础时钟与片选，并由组合逻辑完成极性/相位适配及收发完成检测。

## 1. 层级位置

- Parents：`flash_state`
- Children：`clk_div_spi0`
- Component children：无
- Upstream modules：无
- Downstream modules：无

### 1.1 本模块结构图

```mermaid
flowchart TB
  spi_master_spi0["spi_master_spi0"] --> clk_div_spi0["clk_div_spi0"]
```

```text
spi_master_spi0
`-- clk_div_spi0
```

## 2. 输入/输出接口摘要

- 接收：数据输入：`CR`, `data_in`；其他输入：`DR_r`, `DR_w`, `clk`, `rst_n`, `... +2`
- 输出：数据输出：`data_out`, `sclk_cnt_div`；其他输出：`RXNE`, `TXE`, `nss_out`, `rx_done`, `... +3`

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:2, output:2 | `sclk_cnt_div`, `clk`, `rst_n`, `sclk_out` |
| `serial_boot_uart` | output:2 | `rx_done`, `tx_done` |
| `other_ports` | input:6, output:5 | `CR`, `data_in`, `data_out`, `DR_r`, `DR_w`, `rx`, `w_en`, `RXNE`, `TXE`, `nss_out`, `... +1` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `CR [7:0]`, `data_in [31:0]` | 未记录 |
| `data_outputs` | output | - | `data_out [31:0]`, `sclk_cnt_div [5:0]` | 未记录 |

## 4. 主要 Drive-centered Flow

- 证据不足：原始文档（Manual Context）未提供本模块的 drive flow 描述。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供 primary internal component |

### 5.2 assign 影响

| Assign | 影响范围 | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_1` | unknown | `rx_done` | (~rx_cnt[5]) & cnt_buf_rx | 证据不足：无可用的语义层赋值解释 |
| `assign_2` | unknown | `tx_done` | CPHA ? (~tx_cnt[5]) & cnt_buf_tx : (~tx_cnt[4]) & cnt_buf_tx | 证据不足：无可用的语义层赋值解释 |
| `assign_0` | unknown | `sclk_out` | CPOL ? ~sclk_out_div : sclk_out_div | 证据不足：无可用的语义层赋值解释 |
