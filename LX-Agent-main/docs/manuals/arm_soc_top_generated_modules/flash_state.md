# 模块 `flash_state`

- 源文件：`rtl\rtl\IONet\SPI\SPI0\flash_state.v`
- 职责（AI 推断）：该模块是 SPI 主控的结构化状态机封装层，负责管理面向 SPI Flash 的读写传输状态与使能时序。
- 说明：模块内部实例化 `spi_master_spi0`，通过状态机（`r_state`）控制 SPI 启动条件（由 `assign_0` 表达的 `w_spi_en` 逻辑），并利用片选信号产生完成指示（由 `assign_2` 表达的 `o_finish`）。外部通过 `i_ctl` 与 `i_data2spi` 提供命令与写数据，读取数据由 `o_dataFspi` 输出，实现了对 Flash 协议端的封装。

## 1. 层级位置

- Parents：`SPI02NoC`
- Children：`spi_master_spi0`
- Component children：无

### 1.1 本模块结构图

```mermaid
flowchart TB
  flash_state["flash_state"] --> spi_master_spi0["spi_master_spi0"]
```

```text
flash_state
`-- spi_master_spi0
```

## 2. 输入/输出接口摘要

- 输入：
  - 数据输入：`i_ctl`, `i_data2spi`
  - 控制输入：`i_readflag`
  - 其他输入：`clk`, `i_miso`, `i_startRead`, `i_w_en`, `... +1`
- 输出：
  - 数据输出：`o_dataFspi`
  - 其他输出：`o_RXNE`, `o_TXE`, `o_busy`, `o_cs_n`, `... +3`

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:2, output:1 | `clk`, `rst_n`, `o_sclk` |
| `other_ports` | input:6, output:7 | `i_ctl`, `i_data2spi`, `o_dataFspi`, `i_readflag`, `i_miso`, `i_startRead`, `i_w_en`, `o_RXNE`, `o_TXE`, `o_busy`, `... +3` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `i_ctl [7:0]`, `i_data2spi [31:0]` | 未记录 |
| `data_outputs` | output | - | `o_dataFspi [31:0]` | 未记录 |
| `control_inputs` | input | - | 未记录 | 未记录 |

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
| `assign_2` | unknown | `o_finish` | w_spi_cs_n | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_0` | unknown | `w_spi_en` | (r_state == READ \| r_state == PAGE_PRO) ? (i_startRead \| ((~r_start_spi_buf) & r_start_spi)) ... | 证据不足：No Semantic Layer assignment interpretation is available. |
