# 模块 `gpio_module`

- 源文件：`rtl/rtl/IONet/GPIO/gpio_module.v`。
- 职责：AI 推断：通用输入输出控制模块，提供寄存器映射的GPIO引脚控制和中断管理功能。
- 说明：模块通过地址映射的寄存器接口（addr_i/data_i）实现对GPIO引脚的控制和状态读取，并产生中断请求信号irq，表明其作为APB/AXI总线从设备与外部处理器交互

## 1. 层级位置

- Parents：`gpio_slot`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`addr_i`, `data_i`, `io_pin_i`；其他输入：`clk`, `we_i`。
- 输出：数据输出：`data_o`, `gpio_ctrl_o`, `gpio_data_o`；其他输出：`irq`。

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
| `assign_1` | data_path | `gpio_data_o` | gpio_data | AI 推断：将内部数据寄存器gpio_data的值直接驱动到模块输出端口，用于外部GPIO数据输出 |
| `assign_2` | data_path | `data_o` | (addr_i[7:0] == GPIO_CTRL) ? gpio_ctrl : (addr_i[7:0] == GPIO_DATA) ? gpio_data : (addr_i[7:0... | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_3` | unknown | `irq` | \|(int_status & int_enable) | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_0` | unknown | `gpio_ctrl_o` | gpio_ctrl | AI 推断：将内部寄存器gpio_ctrl的值直接驱动到模块输出端口，用于外部GPIO控制信号 |
