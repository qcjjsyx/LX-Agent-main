# 模块 `sram_128k`

- **源文件**：`rtl\rtl\memory\sram_128k.v`
- **职责**：AI 推断：实现一个128KB异步SRAM存储宏单元，提供64位数据宽度与字节写使能，内部通过地址高两位划分为4个Bank并组合输出读数据。
- **说明**：接口仅包含数据输入（`i_WEB_8`、`i_addr_14`、`i_data_64`）和数据输出（`o_data_64`），无时钟或复位事件，表明其为纯异步SRAM行为级模型。结合 `assign` 依赖中的地址译码（`i_addr_14[13:12]`）生成4个Bank选择信号 `csb_0..csb_3`，以及根据地址高位将内部读总线 `w_data_64_s0..s3` 多路输出到 `o_data_64`，符合大型SRAM宏单元的典型封装结构。因此该模块在系统中承担128KB异步存储的功能角色。

## 1. 层级位置

- Parents：`socmem`
- Children：无
- Component children：无
- Upstream modules：无
- Downstream modules：无

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`i_WEB_8`、`i_addr_14`、`i_data_64`；其他输入：`i_sramTrig`
- 输出：数据输出：`o_data_64`

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `other_ports` | input:4, output:1 | `i_WEB_8`、`i_addr_14`、`i_data_64`、`i_sramTrig`、`o_data_64` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | \- | `i_WEB_8 [7:0]`、`i_addr_14 [13:0]`、`i_data_64 [63:0]` | 未记录 |
| `data_outputs` | output | \- | `o_data_64 [63:0]` | 未记录 |

## 4. 主要 Drive‑centered Flow

- 证据不足：Manual Context 未提供本模块 drive flow。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| \- | \- | \- | Manual Context 未提供 primary internal component |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_0` | unknown | `csb_0` | `(i_addr_14[13:12] == 2'b00)` | AI 推断：生成4个Bank的高有效使能信号，用于选择当前地址对应的存储体。 |
| `assign_1` | unknown | `csb_1` | `(i_addr_14[13:12] == 2'b01)` | AI 推断：生成4个Bank的高有效使能信号，用于选择当前地址对应的存储体。 |
| `assign_2` | unknown | `csb_2` | `(i_addr_14[13:12] == 2'b10)` | AI 推断：生成4个Bank的高有效使能信号，用于选择当前地址对应的存储体。 |
| `assign_3` | unknown | `csb_3` | `(i_addr_14[13:12] == 2'b11)` | AI 推断：生成4个Bank的高有效使能信号，用于选择当前地址对应的存储体。 |
| `assign_4` | data_path | `o_data_64` | `(i_addr_14[13:12] == 2'b00) ? w_data_64_s0 : (i_addr_14[13:12] == 2'b01) ? w_data_64_s1 : (i_...` | AI 推断：根据当前地址的Bank选择将内部读数据总线之一传递到模块的输出数据端口。 |
