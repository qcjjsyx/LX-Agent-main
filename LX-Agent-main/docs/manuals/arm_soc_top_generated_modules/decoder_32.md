# 模块 `decoder_32`

- 源文件：`rtl\rtl\Decode\decoder_32.v`
- 职责：AI 推断：将64位输入数据（指令与PC）解码为发射级所需的187位控制数据包，同时产生分支偏移、异常号、条件码写使能，并以 i_drive 事件驱动流水。
- 说明：接口采用单一的驱动事件对 i_drive / o_drive。输入为 i_data_64，输出包含 o_data_187 等信号。assign 0 将输入拆分为 PC 和指令部分，assign 241 打包了大量解码信号，体现了解码器的功能。自由信号透传，异常固定为 4'b1111。整体符合解码阶段的职责要求。

## 1. 层级位置

- 父模块：`decoder`
- 子模块：无
- 组件子模块：无
- 上游模块：无
- 下游模块：无

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：`i_drive`（驱动事件），`i_data_64`（数据），`i_free`（背压释放）
- 输出：`o_drive`（驱动事件），`o_blImm9_9`、`o_data_187`、`o_excNum_4`（数据），`o_nzcvWen_4`（控制），`o_free`（背压释放）

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| drive_event | input:1, output:1 | i_drive, o_drive |
| free_backpressure | input:1, output:1 | i_free, o_free |
| other_ports | input:1, output:4 | i_data_64, o_blImm9_9, o_data_187, o_excNum_4, o_nzcvWen_4 |

## 3. Drive/Data/Free 契约

| 接口 | 方向 | 事件 | Payload | Free/背压 |
| --- | --- | --- | --- | --- |
| i_drive | input | i_drive | i_data_64 [63:0] | 未记录 |
| o_drive | output | o_drive | 未记录 | 未记录 |

## 4. 主要 Drive-centered Flow

### `i_drive` 流

- 确定性事实：`i_drive to o_drive`（flow_id=`flow_000_decoder_32_i_drive`）
- Payload：i_drive 事件携带 i_data_64 [63:0]
- 输出/影响：o_drive
- 结构复杂度：branch=0，join=0，blocking=0
- AI 推断：手册应强调 i_drive 到 o_drive 的纯事件传递及其时序延迟作用，弱化数据流细节（数据拆分单独说明）。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供主要的内部组件 |

### 5.2 assign 影响

| Assign | 影响区域 | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| assign_71 | data_path | w_dataProConstantShift_1 | w_addRConsShift_1 \| w_andRConsShift_1 \| w_adcRConsShift_1 \| w_bicRConsShift_1 \| w_cmnRConsShi... | AI 推断：将解码产生的所有域（S标志、寄存器索引、立即数、操作类型等）打包成187位宽数据，以便下游使用。 |
| assign_0 | data_path | {w_pc_32, w_int_32} | i_data_64 | 证据不足：No Semantic Layer assignment interpretation is available. |
