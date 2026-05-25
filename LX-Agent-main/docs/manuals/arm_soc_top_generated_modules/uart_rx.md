# 模块 `uart_rx`

- 源文件：`rtl/rtl/memory/uart_rx.v`。
- 职责：AI 推断：UART接收模块，负责将串行输入数据转换为并行数据并输出。
- 说明：模块接收rx_data_ready作为数据输入，输出8位并行数据rx_data和有效信号rx_data_valid，符合UART接收器的基本功能定义

## 1. 层级位置

- Parents：`data_init`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`rx_data_ready`；其他输入：`clk`, `rx_pin`。
- 输出：数据输出：`rx_data`, `rx_data_valid`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:1 | `clk` |
| `serial_boot_uart` | input:2, output:2 | `rx_data_ready`, `rx_data`, `rx_data_valid`, `rx_pin` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `rx_data_ready 1` | 未记录 |
| `data_outputs` | output | - | `rx_data [7:0]`, `rx_data_valid 1` | 未记录 |

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
| - | - | - | - | Manual Context 未提供 primary assign 影响 |
