# 模块 `SPI2NoC`

- 源文件：`rtl\rtl\IONet\SPI\SPI1\SPI2NoC.v`
- 职责：AI 推断：`i_drvFNoc` 与 `i_dataFNoc_51` 可推断为同时有效，数据随驱动事件被捕获到模块内部，形成关联。
- 说明：`cfifo0` 的 `fire` 输出 `w_firefifo0[0]`（第84行）用于在上升沿将 `i_dataFNoc_51` 锁存到 `r_dataFNoc_51`（第89‑96行）。该 `fire` 信号由 `cfifo0` 内部根据 `i_drvFNoc` 产生，表明数据负载与驱动事件相关联。数据随事件进入模块内部寄存器，可视为负载进入了“FIFO”概念（即控制 FIFO 触发下的数据捕获），但具体 FIFO 行为由 `cfifo0` 内部定义，所提供的 RTL 未显示其内部结构，因此该推断为 AI 推理结果。

## 1. 层级位置

- Parents：`IONet_slot`
- Children：`SPI_control`
- Component children：`cFifo3_spi1`
- Upstream modules：无
- Downstream modules：无

### 1.1 本模块结构图

```mermaid
flowchart TB
  SPI2NoC["SPI2NoC"] -->|instance| cfifo0_cFifo3_spi1["cfifo0: cFifo3_spi1"]
  SPI2NoC["SPI2NoC"] -->|instance| cfifo1_cFifo3_spi1["cfifo1: cFifo3_spi1"]
  SPI2NoC["SPI2NoC"] --> SPI_control["SPI_control"]
  SPI2NoC["SPI2NoC"] -->|component| cFifo3_spi1["cFifo3_spi1"]
```

```text
SPI2NoC
|-- cfifo0: cFifo3_spi1
|-- cfifo1: cFifo3_spi1
|-- SPI_control
`-- cFifo3_spi1
```

## 2. 输入/输出接口摘要

- 接收：drive 输入 `i_drvFNoc`；数据输入 `i_dataFNoc_51`；free 输入 `i_freeFNoc`；其他输入 `clk`、`miso_in`、`mosi_in`、`nss_in`、`... +2`
- 输出：drive 输出 `o_drv2Noc`；数据输出 `o_data2Noc_51`；free 输出 `o_free2Noc`；其他输出 `SPI_IRQ`、`io_ctl_miso`、`io_ctl_mosi`、`io_ctl_nss`、`... +5`

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:3, output:2 | `clk`、`rst_finish`、`sclk_in`、`io_ctl_sclk`、`sclk_out` |
| `drive_event` | input:1, output:1 | `i_drvFNoc`、`o_drv2Noc` |
| `free_backpressure` | input:1, output:1 | `i_freeFNoc`、`o_free2Noc` |
| `other_ports` | input:4, output:8 | `i_dataFNoc_51`、`o_data2Noc_51`、`miso_in`、`mosi_in`、`nss_in`、`SPI_IRQ`、`io_ctl_miso`、`io_ctl_mosi`、`io_ctl_nss`、`miso_out`、`... +2` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `i_drvFNoc` | input | `i_drvFNoc` | `i_dataFNoc_51 [50:0]` | 未记录 |
| `o_drv2Noc` | output | `o_drv2Noc` | `o_data2Noc_51 [50:0]` | 未记录 |

## 4. 主要 Drive‑centered Flow

### `i_drvFNoc`

- 确定性事实：`SPI2NoC flow from i_drvFNoc`；flow_id=`flow_000_SPI2NoC_i_drvFNoc`
- Payload：`i_drvFNoc` → `i_dataFNoc_51 [50:0]`
- 输出/影响：证据不足：Knowledge IR did not find a module output endpoint for this flow.
- 结构复杂度：branch=0，join=0，blocking=1
- AI 推断：驱动事件与 51 位数据负载同时有效，负载内容可能为 SPI 帧数据，随事件进入 FIFO。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| `cfifo0` | `cFifo3_spi1` | `i_drvFNoc` | `w_drvnext_fifo1` |
| `cfifo1` | `cFifo3_spi1` | `r_drv2fifo1` | `o_drv2Noc` |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_0` | data_path | `o_data2Noc_51` | {r_dataFNoc_51[50], r_dataFNoc_51[49:42], r_apbrdata, r_X, r_Y} | AI 推断：该持续赋值将多个内部寄存器拼接为发往 NoC 的输出载荷，解释为携带路由字段、APB 读数据和坐标字段的数据包头。 |
