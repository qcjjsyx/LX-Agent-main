# 模块 `decoder`

- 源文件：`rtl\rtl\Decode\decoder.v`。
- 职责：AI 推断：从RTL切片确认，i_driveFromIF经decoderSele选择后，驱动decoder16和decoder32实例，形成解码数据流，最终通过decoderData_187等输出流出模块。。
- 说明：切片第60-63行显示decoderSele将i_driveFromIF分发给decoder16和decoder32；第77-88行显示decoder16和decoder32实例化；第99-104行显示decMerge合并解码数据；第121-129行always块将合并数据寄存为r_decoderData_191；第163-167行通过连续赋值输出o_decoderData_187、o_blImm9_9、o_nzcvWen_4等，形成从输入到输出的完整数据流语义。

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
- AI 推断：手册应重点描述decoderSele的选择条件和decoMerge的仲裁逻辑，以及数据负载的同步方式。


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
| `assign_1` | data_path | `w_decoderData1_191` | r_decoderData_191 | AI 推断：输出36位解码PC和异常编号，从解码数据中提取。 |
| `assign_2` | data_path | `o_decoderData_187` | {1'b0, w_decoderData1_191[186:2], w_is16_1} | AI 推断：输出解码后的187位数据，包含指令解码结果和16位指令标志。 |
| `assign_3` | control_path | `o_wen_2` | w_decoderData1_191[1:0] | AI 推断：输出2位写使能信号，从解码数据中提取。 |
| `assign_4` | unknown | `o_blImm9_9` | r_blImm9_9 | AI 推断：输出9位BL指令立即数，来自寄存器r_blImm9_9。 |
| `assign_5` | control_path | `o_nzcvWen_4` | r_nzcvWen_4 | AI 推断：输出4位NZCV条件标志写使能，来自寄存器r_nzcvWen_4。 |
| `assign_6` | data_path | `o_decPCAndNum_36` | {w_decoderData1_191[136:105],w_decoderData1_191[190:187]} | AI 推断：输出36位解码PC和异常编号，从解码数据中提取。 |
