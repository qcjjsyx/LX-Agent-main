# arm_soc_top RTL 代码手册

本手册采用“主手册 + 模块页”的结构，主手册用于快速定位系统结构，模块页用于查看具体接口和 flow 细节。

## 1. 项目总览

- 项目用途：AI 推断：顶层SoC模块，负责CPU核心与IO网络之间的驱动事件桥接。
- RTL 目录：`rtl/rtl`。
- 顶层文件：`rtl/rtl/SoC/arm_soc_top.v`。

## 2. 顶层模块 `arm_soc_top`

- 顶层直接实例化模块：`IONet_slot`, `async2sync`, `cpu_slot`。

### 2.1 外部端口分组

端口分组按 pad/信号命名和方向归类，用于快速识别顶层对外边界。

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | inout:1, input:7, output:1 | `initMode_pad`, `RCLK_BAUD_UART0_pad`, `RCLK_BAUD_UART1_pad`, `RCLK_UART0_pad`, `RCLK_UART1_pad`, `clk_pad`, `rst_pad`, `sclk_SPI0_pad`, `... +1` |
| `serial_boot_uart` | input:1, output:1 | `rx_pin_pad`, `tx_pin_pad` |
| `uart0` | input:6, output:6 | `BREG_UART0_pad`, `NCTS_UART0_pad`, `NDCD_UART0_pad`, `NDSR_UART0_pad`, `NRI_UART0_pad`, `SIN_UART0_pad`, `BAUD_UART0_pad`, `NDTR_UART0_pad`, `... +4` |
| `uart1` | input:6, output:6 | `BREG_UART1_pad`, `NCTS_UART1_pad`, `NDCD_UART1_pad`, `NDSR_UART1_pad`, `NRI_UART1_pad`, `SIN_UART1_pad`, `BAUD_UART1_pad`, `NDTR_UART1_pad`, `... +4` |
| `iic0` | input:5, output:6 | `FSEN_IIC0_pad`, `HSEN_IIC0_pad`, `IFSDA_IIC0_pad`, `ISCL_IIC0_pad`, `ISDA_IIC0_pad`, `CKISO_IIC0_pad`, `DAGND_IIC0_pad`, `DAISO_IIC0_pad`, `... +3` |
| `spi0` | input:1, output:3 | `miso_SPI0_pad`, `cs_n_SPI0_pad`, `mosi_SPI0_pad`, `startRead_SPI0_pad` |
| `spi1` | inout:3 | `miso_SPI1_pad`, `mosi_SPI1_pad`, `nss_SPI1_pad` |
| `pwm0` | output:1 | `PWM0_OUT_pad` |
| `pwm1` | output:1 | `PWM1_OUT_pad` |
| `gpio` | inout:1 | `io_pin_pad` |

### 2.2 顶层组成

| 子模块 | 职责 | 接收 | 输出 | 模块页 |
| --- | --- | --- | --- | --- |
| `IONet_slot` | AI 推断：该模块是SoC中CPU与外围设备（UART、SPI、I2C、PWM、定时器、看门狗、GPIO）之间的NoC（片上网络）桥接槽位，负责事件驱动和数据传输的路由与转发。 | drive 输入：`i_drvFCPU`；数据输入：`i_dataFCPU_51`, `io_pin`；free 输入：`i_freeFCPU`；其他输入：`BREG_UART0`, `BREG_UART1`, `FSEN_IIC0`, `HSEN_IIC0`, `... +24` | drive 输出：`o_drv2CPU`；数据输出：`INT_TIMER`, `gpio_ctrl_o`, `gpio_data_o`, `o_data2CPU_51`；free 输出：`o_free2CPU`；其他输出：`BAUD_UART0`, `BAUD_UART1`, `CKISO_IIC0`, `DAGND_IIC0`, `... +36` | [打开](arm_soc_top_generated_modules/IONet_slot.md) |
| `async2sync` | AI 推断：该模块是一个异步复位同步释放（复位同步器）模块 | 其他输入：`clk`, `rst_async_n` | 其他输出：`rst_sync_n` | [打开](arm_soc_top_generated_modules/async2sync.md) |
| `cpu_slot` | AI 推断：该模块是SoC中一个CPU槽位的顶层容器，负责将CPU核心与Mesh网络及本地存储子系统进行事件驱动的数据交互与初始化控制。 | drive 输入：`i_driveFromMesh`；数据输入：`i_IntSig`, `i_dataFMesh`；控制输入：`initMode`；free 输入：`i_freeFMesh`；其他输入：`clk`, `init_rx`, `soc_start` | drive 输出：`o_driveToMesh`；数据输出：`o_data2Mesh`；free 输出：`o_free2Mesh`；其他输出：`init_sig`, `init_tx` | [打开](arm_soc_top_generated_modules/cpu_slot.md) |

### 2.3 顶层结构图

下图只展示顶层向下的有限层级，完整父子关系见后续层级表。

```mermaid
flowchart TB
  arm_soc_top["arm_soc_top"] --> IONet_slot["IONet_slot"]
  arm_soc_top["arm_soc_top"] --> async2sync["async2sync"]
  arm_soc_top["arm_soc_top"] --> cpu_slot["cpu_slot"]
  IONet_slot["IONet_slot"] --> CPU2NoC["CPU2NoC"]
  IONet_slot["IONet_slot"] --> I2C2NoC["I2C2NoC"]
  IONet_slot["IONet_slot"] --> IONetwork["IONetwork"]
  IONet_slot["IONet_slot"] --> NoCUART0["NoCUART0"]
  IONet_slot["IONet_slot"] --> NoCUART1["NoCUART1"]
  IONet_slot["IONet_slot"] --> SPI02NoC["SPI02NoC"]
  IONet_slot["IONet_slot"] --> SPI2NoC["SPI2NoC"]
  IONet_slot["IONet_slot"] --> gpio_slot["gpio_slot"]
  IONet_slot["IONet_slot"] --> pwm0_top["pwm0_top"]
  IONet_slot["IONet_slot"] --> pwm1_top["pwm1_top"]
  IONet_slot["IONet_slot"] --> timer_slot["timer_slot"]
  IONet_slot["IONet_slot"] --> wd2noc["wd2noc"]
  cpu_slot["cpu_slot"] --> cpu_top_all["cpu_top_all"]
  cpu_slot["cpu_slot"] --> data_slot["data_slot"]
  cpu_slot["cpu_slot"] --> memory_slot["memory_slot"]
```

```text
arm_soc_top
|-- IONet_slot
|   |-- CPU2NoC
|   |-- I2C2NoC
|   |-- IONetwork
|   |-- NoCUART0
|   |-- NoCUART1
|   |-- SPI02NoC
|   |-- SPI2NoC
|   |-- gpio_slot
|   |-- pwm0_top
|   |-- pwm1_top
|   |-- timer_slot
|   `-- wd2noc
|-- async2sync
`-- cpu_slot
    |-- cpu_top_all
    |-- data_slot
    `-- memory_slot
```
- 图中已截断，未展开 26 条后续层级边。

## 3. 完整模块层级结构

- 模块数：106。
- 层级边数：114。

| Parent | Child | Relationship |
| --- | --- | --- |
| `I2C2NoC` | `mi2cv2` | instantiates |
| `IONet_slot` | `CPU2NoC` | instantiates |
| `IONet_slot` | `I2C2NoC` | instantiates |
| `IONet_slot` | `IONetwork` | instantiates |
| `IONet_slot` | `NoCUART0` | instantiates |
| `IONet_slot` | `NoCUART1` | instantiates |
| `IONet_slot` | `SPI02NoC` | instantiates |
| `IONet_slot` | `SPI2NoC` | instantiates |
| `IONet_slot` | `gpio_slot` | instantiates |
| `IONet_slot` | `pwm0_top` | instantiates |
| `IONet_slot` | `pwm1_top` | instantiates |
| `IONet_slot` | `timer_slot` | instantiates |
| `IONet_slot` | `wd2noc` | instantiates |
| `IONetwork` | `nodeTop` | instantiates |
| `NoCUART0` | `m16550s` | instantiates |
| `NoCUART1` | `m16550s` | instantiates |
| `SPI02NoC` | `fire2SyncPluse` | instantiates |
| `SPI02NoC` | `flash_state` | instantiates |
| `SPI2NoC` | `SPI_control` | instantiates |
| `SPI_control` | `CRC_rx` | instantiates |
| `SPI_control` | `CRC_tx` | instantiates |
| `SPI_control` | `clk_div` | instantiates |
| `SPI_control` | `reg_apb` | instantiates |
| `SPI_control` | `spi_m` | instantiates |
| `SPI_control` | `spi_s` | instantiates |
| `SPI_control` | `state0` | instantiates |
| `adder` | `adder32` | instantiates |
| `adder` | `adder5` | instantiates |
| `adder` | `adder64` | instantiates |
| `arm_soc_top` | `IONet_slot` | instantiates |
| `arm_soc_top` | `async2sync` | instantiates |
| `arm_soc_top` | `cpu_slot` | instantiates |
| `clk_div_spi0` | `sclk_done_1` | instantiates |
| `cmsdk_apb_watchdog` | `cmsdk_apb_watchdog_frc` | instantiates |
| `cpu_slot` | `cpu_top_all` | instantiates |
| `cpu_slot` | `data_slot` | instantiates |
| `cpu_slot` | `memory_slot` | instantiates |
| `cpu_top_all` | `contTap` | instantiates |
| `cpu_top_all` | `decoder` | instantiates |
| `cpu_top_all` | `execute` | instantiates |
| `cpu_top_all` | `fetch` | instantiates |
| `cpu_top_all` | `grf` | instantiates |
| `cpu_top_all` | `intAndExc` | instantiates |
| `cpu_top_all` | `launch` | instantiates |
| `cpu_top_all` | `lsu` | instantiates |
| `cpu_top_all` | `prf` | instantiates |
| `cpu_top_all` | `wb` | instantiates |
| `data_init` | `uart_rx` | instantiates |
| `data_init` | `uart_tx` | instantiates |
| `decoder` | `decoder_16` | instantiates |
| `decoder` | `decoder_32` | instantiates |
| `execute` | `adder` | instantiates |
| `execute` | `align` | instantiates |
| `execute` | `ander` | instantiates |
| `execute` | `contTap` | instantiates |
| `execute` | `div` | instantiates |
| `execute` | `eor` | instantiates |
| `execute` | `hsb` | instantiates |
| `execute` | `muller` | instantiates |
| `execute` | `orrer` | instantiates |
| `execute` | `reverse` | instantiates |
| `execute` | `satQ` | instantiates |
| `execute` | `shifter` | instantiates |
| `fetch` | `instSplit` | instantiates |
| `flash_state` | `spi_master_spi0` | instantiates |
| `gpio_slot` | `gpio_module` | instantiates |
| `gpio_slot` | `perip_slot` | instantiates |
| `intAndExc` | `contTap` | instantiates |
| `intAndExc` | `inStack` | instantiates |
| `intAndExc` | `intAndExc_pop` | instantiates |
| `lsu` | `contTap` | instantiates |
| `lsu` | `dataUpdate` | instantiates |
| `lsu` | `multiLoadDataUpate` | instantiates |
| `lsu` | `multiStoreDataUpate` | instantiates |
| `lsu` | `stateUpdate` | instantiates |
| `m16550s` | `m3s001fd` | instantiates |
| `m16550s` | `m3s002fd` | instantiates |
| `m16550s` | `m3s003fd` | instantiates |
| `m16550s` | `m3s004fd` | instantiates |
| `m16550s` | `m3s005fd` | instantiates |
| `m16550s` | `m3s006fd` | instantiates |
| `m16550s` | `m3s007fd` | instantiates |
| `m16550s` | `m3s008fd` | instantiates |
| `m16550s` | `m3s009fd` | instantiates |
| `m16550s` | `m3s010fd` | instantiates |
| `m16550s` | `m3s011fd` | instantiates |
| `m3s009fd` | `m3s012fd` | instantiates |
| `m3s010fd` | `m3s012fd` | instantiates |
| `m3s011fd` | `m3s013fd` | instantiates |
| `m3s013fd` | `m3s014fd` | instantiates |
| `memory_slot` | `data_init` | instantiates |
| `memory_slot` | `socmem` | instantiates |
| `mi2cv2` | `m3s001fb` | instantiates |
| `mi2cv2` | `m3s002fb` | instantiates |
| `mi2cv2` | `m3s003fb` | instantiates |
| `mi2cv2` | `m3s004fb` | instantiates |
| `mi2cv2` | `m3s005fb` | instantiates |
| `nodeTop` | `arbMsg` | instantiates |
| `nodeTop` | `routeMsg` | instantiates |
| `perip_slot` | `fire2SyncPluse` | instantiates |
| `perip_slot_timer` | `fire2SyncPluse` | instantiates |
| `pwm0_top` | `pwm` | instantiates |
| `pwm1_top` | `pwm` | instantiates |
| `routeMsg` | `routeMsgEW` | instantiates |
| `routeMsg` | `routeMsgSN` | instantiates |
| `routeMsg` | `subtr4b` | instantiates |
| `socmem` | `ROM` | instantiates |
| `socmem` | `contTap` | instantiates |
| `socmem` | `sram_128k` | instantiates |
| `socmem` | `sram_8k` | instantiates |
| `spi_master_spi0` | `clk_div_spi0` | instantiates |
| `timer_slot` | `perip_slot_timer` | instantiates |
| `timer_slot` | `timer_module` | instantiates |
| `wd2noc` | `cmsdk_apb_watchdog` | instantiates |

## 4. 子系统与模块索引

每个 reachable module 都有独立模块页；关键模块详写，helper/leaf 模块使用压缩卡片。

| 模块 | 区域 | 职责摘要 | 模块页 |
| --- | --- | --- | --- |
| `CPU2NoC` | cpu | AI 推断：w_channelChoose 由 r_IOAddr 落在特定地址范围决定，选择 NoC 通道 0 或通道 1。 | [打开](arm_soc_top_generated_modules/CPU2NoC.md) |
| `cpu_slot` | cpu | AI 推断：该模块是SoC中一个CPU槽位的顶层容器，负责将CPU核心与Mesh网络及本地存储子系统进行事件驱动的数据交互与初始化控制。 | [打开](arm_soc_top_generated_modules/cpu_slot.md) |
| `cpu_top_all` | cpu | AI 推断：RTL源码中未提供事件与释放信号之间的握手时序逻辑（如valid/ready握手或阶段驱动），仅通过模块实例之间的连线传递事件和释放信号。 | [打开](arm_soc_top_generated_modules/cpu_top_all.md) |
| `dataUpdate` | cpu | AI 推断：数据更新模块，负责将加载数据按类型（lb/lhw/lw/ldw）进行字节对齐和符号扩展，并管理存储数据的地址偏移和字节写使能生成。 | [打开](arm_soc_top_generated_modules/dataUpdate.md) |
| `decoder` | cpu | AI 推断：指令解码与分发核心模块，负责将取指阶段传入的PC和指令数据解码为控制信号，并分发至发射和异常处理阶段。 | [打开](arm_soc_top_generated_modules/decoder.md) |
| `decoder_16` | cpu | AI 推断：16位Thumb指令解码器，将输入的16位指令数据解码为187位内部微操作控制信号 | [打开](arm_soc_top_generated_modules/decoder_16.md) |
| `decoder_32` | cpu | AI 推断：32位Thumb指令解码器，将输入的64位指令包解码为187位发射数据和控制信号。 | [打开](arm_soc_top_generated_modules/decoder_32.md) |
| `fetch` | cpu | AI 推断：取指模块，负责接收来自顶层、ICache和Dispatch的驱动事件，经过内部流水线处理后，向译码、异常、中断和ICache发送驱动事件，并输出取指地址、指令及PC组合、异常和中断状态。 | [打开](arm_soc_top_generated_modules/fetch.md) |
| `grf` | cpu | AI 推断：通用寄存器文件模块，为处理器流水线各阶段提供寄存器读取和写回仲裁服务 | [打开](arm_soc_top_generated_modules/grf.md) |
| `intAndExc` | cpu | AI 推断：中断与异常集中仲裁与分发中心，负责收集来自流水线各阶段的中断/异常事件，仲裁优先级，并驱动后续的栈操作、数据路由和PC重定向。 | [打开](arm_soc_top_generated_modules/intAndExc.md) |
| `intAndExc_pop` | cpu | AI 推断：中断与异常出栈调度器，负责将来自DR（数据读取器）和Top（顶层）的出栈请求分发到SP（栈指针）、WGRF（通用寄存器文件写入）和WPSR（程序状态字写入）等目标单元。 | [打开](arm_soc_top_generated_modules/intAndExc_pop.md) |
| `launch` | cpu | AI 推断：指令发射与数据准备中心，负责接收来自解码器、执行单元、加载存储单元、通用寄存器文件和系统寄存器文件的驱动事件，仲裁数据依赖，组装操作数，并最终向执行单元、通用寄存器文件、指令预取单元、程... | [打开](arm_soc_top_generated_modules/launch.md) |
| `lsu` | cpu | AI 推断：加载存储单元，负责执行内存访问指令（加载/存储）并管理数据在处理器核心与内存系统之间的流动。 | [打开](arm_soc_top_generated_modules/lsu.md) |
| `prf` | cpu | AI 推断：物理寄存器文件模块，负责存储和转发通用寄存器（PRF）和程序状态寄存器（PSR）的值。 | [打开](arm_soc_top_generated_modules/prf.md) |
| `stateUpdate` | cpu | AI 推断：状态更新与分发模块，负责将来自更新拆分器的请求进行缓冲、类型识别（加载/存储）并分发至对应的加载或存储FIFO，最终合并输出。 | [打开](arm_soc_top_generated_modules/stateUpdate.md) |
| `wb` | cpu | AI 推断：写回阶段模块，负责将执行结果分发到通用寄存器组、程序计数器、谓词寄存器、XPSR以及GRF读取路径。 | [打开](arm_soc_top_generated_modules/wb.md) |
| `adder` | execution_pipeline | AI 推断：多宽度算术加法器，根据操作类型选择32位、5位或64位加法结果 | [打开](arm_soc_top_generated_modules/adder.md) |
| `adder32` | execution_pipeline | AI 推断：32位加法器模块，支持有符号和无符号加法运算，并生成进位和溢出标志。 | [打开](arm_soc_top_generated_modules/adder32.md) |
| `adder5` | execution_pipeline | AI 推断：带符号/无符号模式选择的5位加法器，支持进位输入和溢出检测 | [打开](arm_soc_top_generated_modules/adder5.md) |
| `adder64` | execution_pipeline | AI 推断：64位加法器，支持有符号/无符号模式选择，并生成进位和溢出标志 | [打开](arm_soc_top_generated_modules/adder64.md) |
| `align` | execution_pipeline | AI 推断：该模块负责将输入的32位操作数地址对齐到4字节边界，并输出对齐后的结果。 | [打开](arm_soc_top_generated_modules/align.md) |
| `ander` | execution_pipeline | AI 推断：该模块执行两个32位操作数的按位与运算，并输出结果。 | [打开](arm_soc_top_generated_modules/ander.md) |
| `clk_div` | execution_pipeline | AI 推断：该模块根据波特率选择信号和SPI模式配置，从系统时钟生成可配置的SPI串行时钟（sclk_out）及其完成指示信号（sclk_done）。 | [打开](arm_soc_top_generated_modules/clk_div.md) |
| `clk_div_spi0` | execution_pipeline | AI 推断：sclk_m由nss_out和cnt[BR]决定，实现片选使能下的可编程分频；sclk_out由bit8_out门控，确保仅在数据窗口输出时钟。 | [打开](arm_soc_top_generated_modules/clk_div_spi0.md) |
| `div` | execution_pipeline | AI 推断：该模块执行32位有符号或无符号整数除法运算，根据symbolFlag信号选择运算模式。 | [打开](arm_soc_top_generated_modules/div.md) |
| `eor` | execution_pipeline | AI 推断：执行按位异或运算的组合逻辑模块 | [打开](arm_soc_top_generated_modules/eor.md) |
| `execute` | execution_pipeline | AI 推断：执行模块是处理器流水线的执行阶段，负责接收来自发射阶段（Launch）的指令，从通用寄存器组（GRF）和加载存储单元（LSU）获取操作数，执行算术逻辑运算，并将结果写回或发送给后续阶段。 | [打开](arm_soc_top_generated_modules/execute.md) |
| `hsb` | execution_pipeline | AI 推断：算术结果符号判断模块，根据操作数和标志位生成结果 | [打开](arm_soc_top_generated_modules/hsb.md) |
| `muller` | execution_pipeline | AI 推断：32位有符号/无符号整数乘法器，支持结果按位取反输出 | [打开](arm_soc_top_generated_modules/muller.md) |
| `multiLoadDataUpate` | execution_pipeline | AI 推断：多加载数据更新与写回控制模块，负责从加载数据路由中选择并重组数据，生成写回使能、结束标志及下一轮地址/寄存器列表。 | [打开](arm_soc_top_generated_modules/multiLoadDataUpate.md) |
| `multiStoreDataUpate` | execution_pipeline | AI 推断：该模块负责根据输入地址和寄存器列表，生成多存储操作所需的下一地址、下一寄存器列表、数据写入使能以及写回控制信号。 | [打开](arm_soc_top_generated_modules/multiStoreDataUpate.md) |
| `orrer` | execution_pipeline | AI 推断：执行按位逻辑或运算的组合逻辑单元 | [打开](arm_soc_top_generated_modules/orrer.md) |
| `reverse` | execution_pipeline | AI 推断：该模块根据reverseType选择四种位反转/字节交换操作之一，将输入oprand转换为输出result。 | [打开](arm_soc_top_generated_modules/reverse.md) |
| `satQ` | execution_pipeline | AI 推断：饱和量化运算单元，根据符号标志选择有符号或无符号饱和算法对操作数进行限幅。 | [打开](arm_soc_top_generated_modules/satQ.md) |
| `shifter` | execution_pipeline | AI 推断：该模块根据移位类型和移位量对32位操作数执行多种移位和扩展操作，并输出移位结果和进位标志。 | [打开](arm_soc_top_generated_modules/shifter.md) |
| `CRC_rx` | noc | AI 推断：该模块根据输入数据流和多项式计算并输出CRC校验值。 | [打开](arm_soc_top_generated_modules/CRC_rx.md) |
| `CRC_tx` | noc | AI 推断：该模块根据输入数据计算并输出CRC校验值，支持16位和8位两种CRC模式。 | [打开](arm_soc_top_generated_modules/CRC_tx.md) |
| `I2C2NoC` | noc | AI 推断：该模块作为I2C主控制器（mi2cv2）与片上网络（NoC）之间的桥接与数据同步模块，负责将I2C总线事件转换为NoC可识别的驱动事件，并管理数据路径的延迟与同步。 | [打开](arm_soc_top_generated_modules/I2C2NoC.md) |
| `IONet_slot` | noc | AI 推断：该模块是SoC中CPU与外围设备（UART、SPI、I2C、PWM、定时器、看门狗、GPIO）之间的NoC（片上网络）桥接槽位，负责事件驱动和数据传输的路由与转发。 | [打开](arm_soc_top_generated_modules/IONet_slot.md) |
| `IONetwork` | noc | AI 推断：2x2 网格片上网络路由器，负责在四个节点（node_00、node_01、node_10、node_11）之间路由事件驱动消息和空闲信号。 | [打开](arm_soc_top_generated_modules/IONetwork.md) |
| `NoCUART0` | noc | AI 推断：基于NoC的UART桥接模块，负责将NoC驱动事件与UART核心进行协议转换和同步 | [打开](arm_soc_top_generated_modules/NoCUART0.md) |
| `NoCUART1` | noc | AI 推断：NoCUART1 是一个 UART 桥接模块，负责在 NoC 事件驱动接口和标准 UART 外设 (m16550s) 之间进行协议转换与数据同步。 | [打开](arm_soc_top_generated_modules/NoCUART1.md) |
| `SPI02NoC` | noc | AI 推断：w_fire_2[0]来自cFifo1的o_fire_1，w_fire_2[1]来自cFifo2的o_fire_1 | [打开](arm_soc_top_generated_modules/SPI02NoC.md) |
| `SPI2NoC` | noc | AI 推断：SPI2NoC 是 SPI 子系统与片上网络 (NoC) 之间的桥接模块，负责将 SPI 控制器的驱动事件和数据打包成 NoC 兼容的格式，并处理来自 NoC 的释放信号。 | [打开](arm_soc_top_generated_modules/SPI2NoC.md) |
| `SPI_control` | noc | AI 推断：SPI 主从控制器，通过 APB 接口配置寄存器，管理 SPI 协议时序、时钟分频、CRC 校验及中断生成。 | [打开](arm_soc_top_generated_modules/SPI_control.md) |
| `arbMsg` | noc | AI 推断：五路输入消息仲裁与合并模块，负责从东、本地、北、南、西五个方向中选择一路消息转发至下一级。 | [打开](arm_soc_top_generated_modules/arbMsg.md) |
| `cmsdk_apb_watchdog` | noc | AI 推断：该模块是APB总线接口的看门狗定时器顶层，负责将APB总线协议转换为内部看门狗功能子模块的控制与数据。 | [打开](arm_soc_top_generated_modules/cmsdk_apb_watchdog.md) |
| `cmsdk_apb_watchdog_frc` | noc | AI 推断：该模块是一个基于APB接口的强制看门狗定时器，用于在系统锁定或故障时生成复位或中断。 | [打开](arm_soc_top_generated_modules/cmsdk_apb_watchdog_frc.md) |
| `fire2SyncPluse` | noc | AI 推断：该模块负责将输入的脉冲信号同步到本地时钟域，并检测其上升沿。 | [打开](arm_soc_top_generated_modules/fire2SyncPluse.md) |
| `flash_state` | noc | AI 推断：flash_state 是 SPI 闪存协议状态控制器，负责管理 SPI 主设备与外部闪存之间的读写操作状态机。 | [打开](arm_soc_top_generated_modules/flash_state.md) |
| `gpio_module` | noc | AI 推断：通用输入输出控制模块，提供寄存器映射的GPIO引脚控制和中断管理功能 | [打开](arm_soc_top_generated_modules/gpio_module.md) |
| `gpio_slot` | noc | AI 推断：该模块是GPIO外设的槽位封装，负责将Mesh网络的事件驱动与自由信号路由到内部GPIO模块和外围槽位控制器。 | [打开](arm_soc_top_generated_modules/gpio_slot.md) |
| `m16550s` | noc | AI 推断：该模块是一个UART寄存器文件与总线接口桥接单元，负责将系统总线访问转换为内部寄存器读写操作。 | [打开](arm_soc_top_generated_modules/m16550s.md) |
| `m3s001fb` | noc | AI 推断：该模块是一个基于时钟选择的多路复用器，用于在两种时钟参考源之间选择分频计数器的预置值。 | [打开](arm_soc_top_generated_modules/m3s001fb.md) |
| `m3s001fd` | noc | AI 推断：该模块是UART发送路径中的发送缓冲加载控制单元，负责将并行数据加载到发送FIFO。 | [打开](arm_soc_top_generated_modules/m3s001fd.md) |
| `m3s002fb` | noc | AI 推断：该模块在当前上下文中缺乏明确的接口和内部结构信息，可能是一个空壳模块或尚未被解析的占位模块。 | [打开](arm_soc_top_generated_modules/m3s002fb.md) |
| `m3s002fd` | noc | AI 推断：该模块是一个UART接收数据缓冲与转发单元，负责将串行接收的FIFO数据转换为并行输出。 | [打开](arm_soc_top_generated_modules/m3s002fd.md) |
| `m3s003fb` | noc | AI 推断：该模块是I2C总线从机接口的寄存器文件与地址译码单元，负责从I2C总线接收地址和数据，并输出配置寄存器值。 | [打开](arm_soc_top_generated_modules/m3s003fb.md) |
| `m3s003fd` | noc | AI 推断：该模块是UART内部寄存器文件与数据通路控制单元，负责地址译码、寄存器读写以及接收数据缓冲。 | [打开](arm_soc_top_generated_modules/m3s003fd.md) |
| `m3s004fb` | noc | AI 推断：该模块是一个IIC总线接口的从设备数据与状态寄存器模块，负责存储和输出从设备地址匹配后的数据与状态信息。 | [打开](arm_soc_top_generated_modules/m3s004fb.md) |
| `m3s004fd` | noc | AI 推断：该模块是UART中断使能寄存器(IER)和中断标识寄存器(IIR)的驱动单元，负责将外部输入的4位数据(DataIn)转换为中断控制与状态输出。 | [打开](arm_soc_top_generated_modules/m3s004fd.md) |
| `m3s005fb` | noc | AI 推断：该模块是一个单比特写数据缓冲或直通单元，用于将外部写入数据传递至内部逻辑。 | [打开](arm_soc_top_generated_modules/m3s005fb.md) |
| `m3s005fd` | noc | AI 推断：该模块是一个UART波特率分频器，将输入的8位数据转换为16位分频值输出。 | [打开](arm_soc_top_generated_modules/m3s005fd.md) |
| `m3s006fd` | noc | AI 推断：该模块是一个5位数据输入接口的简单数据接收单元，可能用于UART子系统的数据捕获或配置。 | [打开](arm_soc_top_generated_modules/m3s006fd.md) |
| `m3s007fd` | noc | AI 推断：该模块是一个纯数据输出单元，仅提供两个4位数据输出端口，无任何输入、事件或控制接口。 | [打开](arm_soc_top_generated_modules/m3s007fd.md) |
| `m3s008fd` | noc | AI 推断：该模块是一个纯数据输出模块，负责提供两组4位并行数据输出，无事件或控制输入。 | [打开](arm_soc_top_generated_modules/m3s008fd.md) |
| `m3s009fd` | noc | AI 推断：该模块是一个基于地址映射的寄存器读取多路选择器，根据输入地址选择内部信号并输出数据。 | [打开](arm_soc_top_generated_modules/m3s009fd.md) |
| `m3s010fd` | noc | AI 推断：该模块是一个基于地址映射的多路选择器，用于从多个内部信号中选择一个输出到数据总线。 | [打开](arm_soc_top_generated_modules/m3s010fd.md) |
| `m3s011fd` | noc | AI 推断：该模块是一个窄位宽数据转换或路由单元，将两个4位输入映射为一个3位输出。 | [打开](arm_soc_top_generated_modules/m3s011fd.md) |
| `m3s012fd` | noc | AI 推断：该模块是一个简单的数据通路单元，可能用于UART子系统中的字节级数据传递或缓冲。 | [打开](arm_soc_top_generated_modules/m3s012fd.md) |
| `m3s013fd` | noc | AI 推断：该模块是一个基于地址映射的多路选择器，用于从16个内部信号中选择一个输出到OP_D。 | [打开](arm_soc_top_generated_modules/m3s013fd.md) |
| `m3s014fd` | noc | AI 推断：该模块是一个简单的3位数据通路单元，可能用于UART子系统内的数据缓冲或直通。 | [打开](arm_soc_top_generated_modules/m3s014fd.md) |
| `mi2cv2` | noc | AI 推断：mi2cv2 是 IONet IIC 子系统内的一个顶层模块，负责将 APB 总线接口（ADDRESS、WDATA、RDATA）转换为 I2C 总线协议（ISCL、ISDA、OSCL、O... | [打开](arm_soc_top_generated_modules/mi2cv2.md) |
| `nodeTop` | noc | AI 推断：五方向网络节点路由器，负责将来自东、西、南、北、本地五个方向的输入消息路由到目标方向输出。 | [打开](arm_soc_top_generated_modules/nodeTop.md) |
| `perip_slot` | noc | AI 推断：外围设备插槽模块，负责在Mesh网络与外围设备之间进行驱动事件和释放事件的流水线缓冲与延迟同步。 | [打开](arm_soc_top_generated_modules/perip_slot.md) |
| `perip_slot_timer` | noc | AI 推断：该模块是一个基于事件驱动的时隙定时器，用于在网格网络中控制数据包的传输时序。 | [打开](arm_soc_top_generated_modules/perip_slot_timer.md) |
| `pwm` | noc | AI 推断：该模块是一个PWM波形生成器，根据输入的占空比和频率参数产生PWM输出信号。 | [打开](arm_soc_top_generated_modules/pwm.md) |
| `pwm0_top` | noc | AI 推断：该模块是PWM子系统的事件驱动型顶层，负责通过两级FIFO流水线传递驱动事件和关联消息，并输出PWM波形。 | [打开](arm_soc_top_generated_modules/pwm0_top.md) |
| `pwm1_top` | noc | AI 推断：该模块是一个PWM驱动事件流水线中的两级FIFO转发节点，负责接收并转发驱动事件及其关联消息，同时管理自由事件和PWM输出。 | [打开](arm_soc_top_generated_modules/pwm1_top.md) |
| `reg_apb` | noc | AI 推断：reg_apb 是 SPI 模块的 APB 从设备寄存器接口，负责将 APB 总线协议转换为 SPI 内部寄存器读写控制信号。 | [打开](arm_soc_top_generated_modules/reg_apb.md) |
| `routeMsg` | noc | AI 推断：路由消息分发模块，将输入消息根据方向选择分发到五个方向（东、本地、北、南、西）的发送FIFO。 | [打开](arm_soc_top_generated_modules/routeMsg.md) |
| `routeMsgEW` | noc | AI 推断：该模块是一个基于坐标的东-西向消息路由判定单元，用于判断输入坐标是否有效以生成消息有效信号。 | [打开](arm_soc_top_generated_modules/routeMsgEW.md) |
| `routeMsgSN` | noc | AI 推断：坐标有效性检测与消息有效信号生成模块 | [打开](arm_soc_top_generated_modules/routeMsgSN.md) |
| `sclk_done_1` | noc | AI 推断：该模块是一个SPI时钟周期完成检测器，用于生成串行时钟计数完成的指示信号。 | [打开](arm_soc_top_generated_modules/sclk_done_1.md) |
| `spi_m` | noc | AI 推断：SPI主设备控制器，负责管理SPI总线的发送、接收和CRC校验时序 | [打开](arm_soc_top_generated_modules/spi_m.md) |
| `spi_master_spi0` | noc | AI 推断：SPI主控制器模块，负责生成SPI时钟、片选信号，并控制数据收发完成标志。 | [打开](arm_soc_top_generated_modules/spi_master_spi0.md) |
| `spi_s` | noc | AI 推断：SPI从机核心数据收发与CRC校验控制模块 | [打开](arm_soc_top_generated_modules/spi_s.md) |
| `state0` | noc | AI 推断：状态机核心模块，管理SPI接口的主状态转换与操作阶段控制 | [打开](arm_soc_top_generated_modules/state0.md) |
| `subtr4b` | noc | AI 推断：4位二进制减法器，通过逐位异或和借位传播链实现无符号减法 | [打开](arm_soc_top_generated_modules/subtr4b.md) |
| `timer_module` | noc | AI 推断：该模块是一个基于内存映射寄存器接口的定时器单元，提供可编程定时计数和软件中断功能。 | [打开](arm_soc_top_generated_modules/timer_module.md) |
| `timer_slot` | noc | AI 推断：定时器槽位模块，作为网格驱动事件流的中继节点，将外部驱动事件转发至内部定时器外设槽，并返回驱动事件及中断信号。 | [打开](arm_soc_top_generated_modules/timer_slot.md) |
| `wd2noc` | noc | AI 推断：看门狗事件到NoC的同步与转发模块，将看门狗中断/复位事件通过7级Fifo1链传递到NoC域 | [打开](arm_soc_top_generated_modules/wd2noc.md) |
| `arm_soc_top` | other | AI 推断：顶层SoC模块，负责CPU核心与IO网络之间的驱动事件桥接。 | [打开](arm_soc_top_generated_modules/arm_soc_top.md) |
| `async2sync` | other | AI 推断：该模块是一个异步复位同步释放（复位同步器）模块 | [打开](arm_soc_top_generated_modules/async2sync.md) |
| `contTap` | other | AI 推断：该模块是一个控制路径上的“轻触”或“脉冲”生成器，用于在特定条件下产生一个或多个时钟周期的控制脉冲。 | [打开](arm_soc_top_generated_modules/contTap.md) |
| `inStack` | other | AI 推断：入栈数据合并与分发模块，负责将来自RGRF和RPSR的驱动事件及负载数据合并后，按SP偏移地址选择一路输出，并管理对应的释放信号。 | [打开](arm_soc_top_generated_modules/inStack.md) |
| `instSplit` | other | AI 推断：指令拆分与分发模块，将取回的64位指令包拆分为最多4条指令，并管理指令FIFO的驱动与释放。 | [打开](arm_soc_top_generated_modules/instSplit.md) |
| `ROM` | storage | AI 推断：该模块是一个只读存储器（ROM），通过地址输入提供固定数据输出。 | [打开](arm_soc_top_generated_modules/ROM.md) |
| `data_init` | storage | AI 推断：数据初始化模块，通过UART接口接收配置数据并驱动指令总线和数据总线的初始化写入。 | [打开](arm_soc_top_generated_modules/data_init.md) |
| `data_slot` | storage | AI 推断：数据槽模块，作为CPU、Dcache和Mesh之间的数据通路仲裁与分发中心 | [打开](arm_soc_top_generated_modules/data_slot.md) |
| `memory_slot` | storage | AI 推断：该模块是SoC内存子系统的顶层插槽，负责仲裁和转发来自IF（指令取指）和LSU（加载存储单元）的驱动事件，并管理数据初始化通道。 | [打开](arm_soc_top_generated_modules/memory_slot.md) |
| `socmem` | storage | AI 推断：片上存储器子系统，为指令和数据访问提供缓存、ROM和栈存储，并通过事件驱动流与IF和LSU单元交互。 | [打开](arm_soc_top_generated_modules/socmem.md) |
| `sram_128k` | storage | AI 推断：该模块是一个128KB的同步SRAM控制器，通过地址高位解码将访问请求分发到四个32KB的子存储体。 | [打开](arm_soc_top_generated_modules/sram_128k.md) |
| `sram_8k` | storage | AI 推断：该模块是一个8KB同步SRAM存储器，提供单端口读写访问。 | [打开](arm_soc_top_generated_modules/sram_8k.md) |
| `uart_rx` | storage | AI 推断：UART接收模块，负责将串行输入数据转换为并行数据并输出 | [打开](arm_soc_top_generated_modules/uart_rx.md) |
| `uart_tx` | storage | AI 推断：UART发送模块，负责将并行数据转换为串行比特流并通过tx_pin输出 | [打开](arm_soc_top_generated_modules/uart_tx.md) |
