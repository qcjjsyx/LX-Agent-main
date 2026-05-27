# 模块 `CRC_tx`

-   源文件：`rtl\rtl\IONet\SPI\SPI1\CRC_tx.v`
-   职责：**AI 推断** — 可配置的 CRC 计算模块，根据内部控制信号 DFF 选择输出 8 位或 16 位 CRC 校验值。
-   说明：模块接收数据输入 `datain` 和生成多项式 `poly`，内部维护 8 位和 16 位两种 CRC 结果寄存器。通过 `DFF` 信号选择输出完整的 16 位 CRC 值，或将低 8 位补零后输出。
    `assign` 语句体现了这一输出选择逻辑。`enable_rise` 检测 `enable` 信号的上升沿，可能用于触发计算或锁存对应结果。模块无实例化组件，内部详细逻辑待源码确认。

## 1. 层级位置

-   Parents：`SPI_control`
-   Children：无
-   Component children：无
-   上游/下游模块：未记录

### 1.1 本模块结构图

Manual Context 未记录内部实例或子模块结构。

## 2. 输入/输出接口

### 2.1 端口一览

| 端口名 | 方向 | 位宽（推测） | 说明 |
| --- | --- | --- | --- |
| `clk` | input | 1 | 时钟 |
| `rst_n` | input | 1 | 复位，低有效 |
| `datain` | input | [15:0] | 数据输入 |
| `poly` | input | [15:0] | 生成多项式 |
| `crc_en` | input | 1 | 未记录 |
| `CRC_en` | input | 1 | 未记录 |
| `enable` | input | 1 | 未记录（与 `enable_rise` 相关） |
| `DFF` | input | 1 | 输出宽度选择：0 选 8 位，1 选 16 位 |
| `CRC_out` | output | [15:0] | CRC 校验值输出 |
| `CRC_busy` | output | 1 | 未记录 |

### 2.2 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:2 | `clk`, `rst_n` |
| `other_ports` | input:6, output:2 | `datain`, `poly`, `CRC_out`, `CRC_en`, `DFF`, `crc_en`, `enable`, `CRC_busy` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `datain [15:0]`, `poly [15:0]` | 未记录 |
| `data_outputs` | output | - | `CRC_out [15:0]` | 未记录 |

## 4. 主要 Drive‑centered Flow

-   **证据不足**：Manual Context 未提供本模块的驱动流程（drive flow）。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供主要内部组件 |

### 5.2 assign 影响

| Assign | 影响区域 | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_1` | unknown | `enable_rise` | (~enable_buf) & enable | **AI 推断** — 生成 `enable` 信号的上升沿脉冲。 |
| `assign_0` | unknown | `CRC_out` | DFF ? CRC16_reg : {8’b0, CRC8_reg} | **AI 推断** — 实现 CRC 结果输出格式化：根据 `DFF` 选择 16 位 CRC 值，或输出低 8 位并进行高位补零。 |
