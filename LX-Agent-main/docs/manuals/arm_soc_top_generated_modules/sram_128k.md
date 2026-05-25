# 模块 `sram_128k`

- 源文件：`rtl/rtl/memory/sram_128k.v`。
- 职责：AI 推断：该模块是一个128KB的同步SRAM控制器，通过地址高位解码将访问请求分发到四个32KB的SRAM子bank。。
- 说明：模块通过地址位[13:12]解码生成四个片选信号csb_0至csb_3，分别对应四个子bank，并将64位数据输出从对应子bank的数据总线中选出。无事件接口，表明是纯数据存储访问。

## 1. 层级位置

- Parents：`socmem`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`i_WEB_8`, `i_addr_14`, `i_data_64`；其他输入：`i_sramTrig`。
- 输出：数据输出：`o_data_64`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `other_ports` | input:4, output:1 | `i_WEB_8`, `i_addr_14`, `i_data_64`, `o_data_64`, `i_sramTrig` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `i_WEB_8 [ 7:0]`, `i_addr_14 [13:0]`, `i_data_64 [63:0]` | 未记录 |
| `data_outputs` | output | - | `o_data_64 [63:0]` | 未记录 |

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
| `assign_1` | unknown | `csb_1` | (i_addr_14[13:12] == 2'b01) | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_2` | unknown | `csb_2` | (i_addr_14[13:12] == 2'b10) | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_3` | unknown | `csb_3` | (i_addr_14[13:12] == 2'b11) | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_4` | data_path | `o_data_64` | (i_addr_14[13:12] == 2'b00) ? w_data_64_s0 : (i_addr_14[13:12] == 2'b01) ? w_data_64_s1 : (i_... | AI 推断：该assign根据地址位[13:12]的值，从四个子bank的64位数据总线中选择一个作为模块输出。 |
| `assign_0` | unknown | `csb_0` | (i_addr_14[13:12] == 2'b00) | 证据不足：No Semantic Layer assignment interpretation is available. |
