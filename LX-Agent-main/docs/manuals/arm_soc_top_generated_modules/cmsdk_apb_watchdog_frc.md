# 模块 `cmsdk_apb_watchdog_frc`

- 源文件：`rtl/rtl/IONet/Watchdog/cmsdk_apb_watchdog_frc.v`。
- 职责：AI 推断：该模块是一个基于APB接口的强制看门狗定时器，用于在系统锁定或故障时触发复位或中断。。
- 说明：模块通过APB接口接收配置（PADDR, PWDATA），并输出中断（WDOGINT）和复位（WDOGRES）信号。assign依赖显示写操作受frc_sel和wdog_lock控制，表明其强制特性。

## 1. 层级位置

- Parents：`cmsdk_apb_watchdog`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`PADDR`, `PWDATA`；其他输入：`PCLK`, `PENABLE`, `PRESETn`, `PWRITE`, `... +5`。
- 输出：数据输出：`frc_data`；其他输出：`WDOGINT`, `WDOGRES`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:4 | `PCLK`, `PRESETn`, `WDOGCLK`, `WDOGCLKEN` |
| `other_ports` | input:7, output:3 | `PADDR`, `PWDATA`, `frc_data`, `PENABLE`, `PWRITE`, `WDOGRESn`, `frc_sel`, `wdog_lock`, `WDOGINT`, `WDOGRES` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `PADDR [4:2]`, `PWDATA [31:0]` | 未记录 |
| `data_outputs` | output | - | `frc_data [31:0]` | 未记录 |

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
| `assign_4` | control_path | `load_en` | (PADDR == `ARM_WDOGLOADA) ? (PWRITE & frc_sel & (~PENABLE) & (~wdog_lock)) : 1'b0 | AI 推断：该赋值生成加载寄存器写使能信号，用于设置看门狗初始计数值。 |
| `assign_14` | control_path | `int_clr_en` | ((~int_clr_w) & PWRITE & frc_sel & (~PENABLE) & (~wdog_lock) & (PADDR == `ARM_WDOGCLEARA)) ? ... | AI 推断：该赋值生成中断清除使能信号，用于清除看门狗中断状态。 |
| `assign_20` | unknown | `WDOGINT` | wdog_mis | AI 推断：该赋值将内部中断状态（wdog_mis）直接映射到模块输出端口。 |
| `assign_22` | unknown | `WDOGRES` | i_wdog_res | AI 推断：该赋值将内部复位信号（i_wdog_res）直接映射到模块输出端口。 |
| `assign_0` | control_path | `wdog_ctrl_en` | (PADDR == `ARM_WDOGCONTROLA) ? (PWRITE & frc_sel & (~PENABLE) & (~wdog_lock)) : 1'b0 | AI 推断：该赋值生成控制寄存器写使能信号，仅在地址匹配、写操作、强制选择且未锁定时有效。 |
