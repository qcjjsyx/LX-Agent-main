# 模块 `satQ`

- 源文件：`rtl\rtl\Execute\satQ.v`。
- 职责：AI 推断：饱和量化单元，根据符号标志选择有符号或无符号饱和路径，将输入操作数1量化到由操作数2指定的位宽范围内。。
- 说明：模块接收两个32位操作数，i_oprand1_32为待量化数据，i_oprand2_32的低6位指定量化位宽。i_satQSymbolFlag_1控制选择有符号饱和路径（w_saturated1_32）或无符号饱和路径（w_satuarted2_32），最终输出量化结果o_saQResult_32和饱和标志sat。

## 1. 层级位置

- Parents：`execute`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`i_oprand1_32`, `i_oprand2_32`；控制输入：`i_satQSymbolFlag_1`。
- 输出：数据输出：`o_saQResult_32`；其他输出：`sat`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `other_ports` | input:3, output:2 | `i_oprand1_32`, `i_oprand2_32`, `o_saQResult_32`, `i_satQSymbolFlag_1`, `sat` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `i_oprand1_32 [31:0]`, `i_oprand2_32 [31:0]` | 未记录 |
| `data_outputs` | output | - | `o_saQResult_32 [31:0]` | 未记录 |
| `control_inputs` | input | - | 未记录 | 未记录 |

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
| `assign_1` | data_path | `w_saturated1_32` | w_maxOprand1_32 > $signed(1<<(i_oprand2_32[5:0] - 1)-1) ? $signed(1<<(i_oprand2_32[5:0] - 1)-... | AI 推断：有符号饱和标志，指示i_oprand1_32是否超出有符号量化范围。 |
| `assign_2` | data_path | `w_sat1_1` | ( i_oprand1_32 < $signed(-(1<<(i_oprand2_32[5:0]-1))) ) \|\| (i_oprand1_32 >= 1<<(i_oprand2_32[... | AI 推断：有符号饱和路径的上界钳位，将w_maxOprand1_32限制在由i_oprand2_32[5:0]指定的有符号最大值之下。 |
| `assign_3` | data_path | `w_maxOprand2_32` | i_oprand1_32 > 0 ? i_oprand1_32 : 0 | AI 推断：无符号饱和标志，指示i_oprand1_32是否超出无符号量化范围。 |
| `assign_4` | data_path | `w_satuarted2_32` | w_maxOprand2_32 > ((1<<i_oprand2_32[5:0]) - 1) ? (1<<i_oprand2_32[5:0]) - 1 : w_maxOprand2_32 | AI 推断：无符号饱和标志，指示i_oprand1_32是否超出无符号量化范围。 |
| `assign_5` | data_path | `w_sat2_1` | (i_oprand1_32 < 0) \|\| (i_oprand1_32 >= 1<<i_oprand2_32[5:0]) | AI 推断：无符号饱和路径的上界钳位，将w_maxOprand2_32限制在由i_oprand2_32[5:0]指定的无符号最大值之下。 |
| `assign_6` | control_path | `o_saQResult_32` | i_satQSymbolFlag_1 == 1'b1 ? w_saturated1_32 : w_satuarted2_32 | 证据不足：No Semantic Layer assignment interpretation is available. |
| ... | ... | ... | ... | 其余 2 条 assign 省略 |
