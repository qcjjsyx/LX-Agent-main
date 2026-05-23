# 模块 `reg_apb`

- 源文件：`rtl\rtl\IONet\SPI\SPI1\reg_apb.v`。
- 职责：AI 推断：APB从设备寄存器接口模块，负责SPI控制/状态/数据寄存器的地址译码与读写访问。
- 说明：模块通过APB协议信号（PSEL、PENABLE、PWRITE、PADDR）生成内部读写选通信号，将PADDR译码为SPI寄存器地址（SPI_SR、SPI_DR、SPI_CR1），并组合PRDATA输出

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
| `assign_1` | unknown | `PSLVERR` | 1'b0 | AI 推断：固定为就绪状态且无错误，表明模块为单周期响应从设备 |
| `assign_2` | control_path | `read` | PSEL & (!PWRITE) | AI 推断：将APB协议握手信号组合为内部读写使能，控制数据路径方向 |
| `assign_3` | control_path | `write` | PENABLE & PSEL & PWRITE | AI 推断：将APB协议握手信号组合为内部读写使能，控制数据路径方向 |
| `assign_4` | unknown | `PREADY` | 1'b1 | AI 推断：固定为就绪状态且无错误，表明模块为单周期响应从设备 |
| `assign_5` | unknown | `SR_r` | ( read & ( addr == SPI_SR ) ) ? 1'b1 : 1'b0 | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_6` | unknown | `DR_r` | ( read && ( addr == SPI_DR ) ) ? 1'b1 : 1'b0 | 证据不足：No Semantic Layer assignment interpretation is available. |
| ... | ... | ... | ... | 其余 5 条 assign 省略 |
