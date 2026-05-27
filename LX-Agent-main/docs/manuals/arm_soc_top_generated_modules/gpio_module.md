# 模块 `gpio_module`

- 源文件：`rtl\rtl\IONet\GPIO\gpio_module.v`。
- 职责：AI 推断：该模块是一个基于地址译码的 GPIO 寄存器外设，通过总线接口提供 GPIO 控制、数据与中断管理功能。
- 说明：接口包含地址、数据输入和数据输出通路，内部定义了多个控制/状态寄存器（如 `GPIO_CTRL`、`GPIO_DATA`、中断使能、边沿使能等）。组合逻辑依赖分析显示，`data_o` 根据 `addr_i[7:0]` 选择对应的内部寄存器输出，同时生成 `irq` 中断信号，呈现典型的内存映射外设行为。因此推断本模块为系统总线上的 GPIO 从设备。

## 1. 层级位置

- Parents：`gpio_slot`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：
  - 数据输入：`addr_i`、`data_i`、`io_pin_i`
  - 其他输入：`clk`、`we_i`
- 输出：
  - 数据输出：`data_o`、`gpio_ctrl_o`、`gpio_data_o`
  - 其他输出：`irq`

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:1 | `clk` |
| `gpio` | input:1, output:2 | `io_pin_i`, `gpio_ctrl_o`, `gpio_data_o` |
| `other_ports` | input:3, output:2 | `addr_i`, `data_i`, `data_o`, `we_i`, `irq` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `addr_i [31:0]`, `data_i [31:0]`, `io_pin_i [GPIO_NUM-1:0]` | 未记录 |
| `data_outputs` | output | - | `data_o [31:0]`, `gpio_ctrl_o [31:0]`, `gpio_data_o [31:0]` | 未记录 |

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
| `assign_1` | data_path | `gpio_data_o` | gpio_data | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_2` | data_path | `data_o` | (addr_i[7:0] == GPIO_CTRL) ? gpio_ctrl : (addr_i[7:0] == GPIO_DATA) ? gpio_data : (addr_i[7:0... | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_3` | unknown | `irq` | \|(int_status & int_enable) | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_0` | unknown | `gpio_ctrl_o` | gpio_ctrl | 证据不足：No Semantic Layer assignment interpretation is available. |
