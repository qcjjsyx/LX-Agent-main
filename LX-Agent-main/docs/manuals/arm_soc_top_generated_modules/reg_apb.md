# 模块 `reg_apb`

- 源文件：`rtl/rtl/IONet/SPI/SPI1/reg_apb.v`。
- 职责：AI 推断：reg_apb 是 SPI 模块的 APB 从接口寄存器桥，负责将 APB 总线协议转换为 SPI 内部寄存器读写控制信号。。
- 说明：模块通过 APB 接口信号（PADDR、PWDATA、PSEL、PENABLE、PWRITE）生成内部读写选通信号（read、write），并基于地址译码产生各寄存器（SPI_SR、SPI_DR、SPI_CR1）的读写使能信号（SR_r、DR_r、CR1_r、DR_w、CR1_w），同时输出 SPI 配置参数（BR、CRCPOLY、TDR）和状态数据（PRDATA）。

## 1. 层级位置

- Parents：`SPI_control`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`PADDR`, `PWDATA`, `RDR`, `RXCRC`, `... +1`；其他输入：`BSY`, `CRCBSY`, `CRCERR`, `MODF`, `... +8`。
- 输出：数据输出：`BR`, `CRCPOLY`, `PRDATA`, `TDR`；控制输出：`BIDIMODE`；其他输出：`BIDIOE`, `CPHA`, `CPOL`, `CR1_r`, `... +21`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:2, output:1 | `clk`, `rst_n`, `LSBFIRST` |
| `other_ports` | input:15, output:29 | `PADDR`, `PWDATA`, `RDR`, `RXCRC`, `TXCRC`, `BR`, `CRCPOLY`, `PRDATA`, `TDR`, `BIDIMODE`, `... +34` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `PADDR [7:0]`, `PWDATA [31:0]`, `RDR [15:0]`, `RXCRC [15:0]`, `TXCRC [15:0]` | 未记录 |
| `data_outputs` | output | - | `BR [2:0]`, `CRCPOLY [15:0]`, `PRDATA [31:0]`, `TDR [15:0]` | 未记录 |
| `control_outputs` | output | - | 未记录 | 未记录 |

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
| `assign_1` | unknown | `PSLVERR` | 1'b0 | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_2` | control_path | `read` | PSEL & (!PWRITE) | AI 推断：生成 APB 读选通信号，用于控制寄存器读取操作。 |
| `assign_3` | control_path | `write` | PENABLE & PSEL & PWRITE | AI 推断：生成 APB 写选通信号，用于控制寄存器写入操作。 |
| `assign_4` | unknown | `PREADY` | 1'b1 | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_5` | unknown | `SR_r` | ( read & ( addr == SPI_SR ) ) ? 1'b1 : 1'b0 | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_6` | unknown | `DR_r` | ( read && ( addr == SPI_DR ) ) ? 1'b1 : 1'b0 | 证据不足：No Semantic Layer assignment interpretation is available. |
| ... | ... | ... | ... | 其余 5 条 assign 省略 |
