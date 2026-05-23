# 模块 `decoder`

- 源文件：`rtl/rtl/Decode/decoder.v`。
- 职责：AI 推断：指令解码与分发核心模块，负责将取指阶段传入的PC和指令数据解码为控制信号，并分发至发射和异常处理阶段。。
- 说明：模块接收来自IF阶段的驱动事件和PC+指令数据，通过内部选择器（decoderSele）根据指令宽度（16位或32位）分流至对应的解码子模块（decoder16/decoder32），解码结果经互斥合并（decoMerge）后输出解码数据、写使能、条件标志等控制信号，同时通过事件分发器（decSpli）将驱动事件分别导向发射（Launch）和异常（Exc）阶段。

## 1. 层级位置

- Parents：`cpu_top_all`。
- Children：`decoder_16`, `decoder_32`。
- Component children：`cFifo1`, `cMutexMerge2_191b_dec`, `cSelector2_65b_dec`, `cSplitter2_1b`。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

```mermaid
flowchart TB
  decoder["decoder"] -->|instance| decoMerge_cMutexMerge2_191b_dec["decoMerge: cMutexMerge2_191b_dec"]
  decoder["decoder"] -->|instance| decSpli_cSplitter2_1b["decSpli: cSplitter2_1b"]
  decoder["decoder"] -->|instance| decoderSele_cSelector2_65b_dec["decoderSele: cSelector2_65b_dec"]
  decoder["decoder"] --> decoder_16["decoder_16"]
  decoder["decoder"] --> decoder_32["decoder_32"]
  decoder["decoder"] -->|component| cFifo1["cFifo1"]
  decoder["decoder"] -->|component| cMutexMerge2_191b_dec["cMutexMerge2_191b_dec"]
  decoder["decoder"] -->|component| cSelector2_65b_dec["cSelector2_65b_dec"]
  decoder["decoder"] -->|component| cSplitter2_1b["cSplitter2_1b"]
```

```text
decoder
|-- decoMerge: cMutexMerge2_191b_dec
|-- decSpli: cSplitter2_1b
|-- decoderSele: cSelector2_65b_dec
|-- decoder_16
|-- decoder_32
|-- cFifo1
|-- cMutexMerge2_191b_dec
|-- cSelector2_65b_dec
`-- cSplitter2_1b
```

## 2. 输入/输出接口摘要

- 接收：drive 输入：`i_driveFromIF`；数据输入：`i_pcAndIns_64`；free 输入：`i_freeFromExc_1`, `i_freeFromLaunch_1`；其他输入：`i_is16_1`, `i_isInInt`。
- 输出：drive 输出：`o_driveToExc_1`, `o_driveToLaunch_1`；数据输出：`o_blImm9_9`, `o_decPCAndNum_36`, `o_decoderData_187`；控制输出：`o_nzcvWen_4`, `o_wen_2`；free 输出：`o_freeToIF`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `drive_event` | input:1, output:2 | `i_driveFromIF`, `o_driveToExc_1`, `o_driveToLaunch_1` |
| `free_backpressure` | input:2, output:1 | `i_freeFromExc_1`, `i_freeFromLaunch_1`, `o_freeToIF` |
| `other_ports` | input:3, output:5 | `i_pcAndIns_64`, `o_blImm9_9`, `o_decPCAndNum_36`, `o_decoderData_187`, `o_nzcvWen_4`, `o_wen_2`, `i_is16_1`, `i_isInInt` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `i_driveFromIF` | input | `i_driveFromIF` | `i_pcAndIns_64 [ 63:0]` | `o_freeToIF` |
| `o_driveToExc_1` | output | `o_driveToExc_1` | 未记录 | `i_freeFromExc_1` |
| `o_driveToLaunch_1` | output | `o_driveToLaunch_1` | 未记录 | `i_freeFromLaunch_1` |

## 4. 主要 Drive-centered Flow

### `i_driveFromIF`

- 确定性事实：`decoder flow from i_driveFromIF`；flow_id=`flow_000_decoder_i_driveFromIF`。
- Payload：`i_driveFromIF` -> `i_pcAndIns_64 [ 63:0]`。
- 输出/影响：证据不足：Knowledge IR did not find a module output endpoint for this flow.。
- 结构复杂度：branch=1，join=1，blocking=1。
- AI 推断：数据负载i_pcAndIns_64与事件驱动i_driveFromIF并行传播，但选择器decoderSele可能使用该数据决定分发路径。


## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| `decoMerge` | `cMutexMerge2_191b_dec` | 无 | 无 |
| `decSpli` | `cSplitter2_1b` | 无 | `o_driveToExc_1`, `o_driveToLaunch_1` |
| `decoderSele` | `cSelector2_65b_dec` | `i_driveFromIF` | 无 |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_2` | data_path | `o_decoderData_187` | {1'b0, w_decoderData1_191[186:2], w_is16_1} | AI 推断：解码数据输出，由合并后的解码数据w_decoderData1_191和指令宽度标志w_is16_1拼接而成。 |
| `assign_3` | control_path | `o_wen_2` | w_decoderData1_191[1:0] | AI 推断：写使能输出，直接从解码数据总线的低2位提取。 |
| `assign_4` | unknown | `o_blImm9_9` | r_blImm9_9 | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_5` | control_path | `o_nzcvWen_4` | r_nzcvWen_4 | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_6` | data_path | `o_decPCAndNum_36` | {w_decoderData1_191[136:105],w_decoderData1_191[190:187]} | AI 推断：解码PC和异常编号输出，从解码数据总线中提取PC字段和异常编号字段拼接而成。 |
