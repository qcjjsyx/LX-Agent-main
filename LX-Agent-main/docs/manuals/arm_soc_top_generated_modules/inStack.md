# 模块 `inStack`

- 源文件：`rtl\rtl\int\inStack.v`
- 职责：AI 推断：硬件上下文保存/恢复堆栈管理器，支持向量中断时将 RGRF、RPSR、PC 打包成栈帧并生成写入地址与数据，或在返回时从栈帧中提取数据分发到相应寄存器。
- 说明：界面事件输入来自 RGRF 和 RPSR；数据输入包含 i_pc_32、i_SP_32、通用寄存器数据（i_grfData_192）和程序状态字（i_psrData_32）；数据输出 o_data_96 为组合的数据与地址，o_SP_32 为更新后的栈指针。内部 WaitMerge 将两组数据合并为 224 位栈上下文，SelSplit 和 MutexMerge 等组件协同处理驱动事件，地址计算基于 SP 偏移 8~32，对应 4 个 64 位栈条目。整体意图符合中断入栈/出栈场景。

## 1. 层级位置

- Parents：`intAndExc`
- Children：无
- Component children：`cMutexMerge2_1b`, `cSelector2_1b`, `cSplitter2_1b_Nodata`, `cWaitMerge2_224b_int`
- Upstream modules：无
- Downstream modules：无

### 1.1 本模块结构图

```mermaid
flowchart TB
  inStack["inStack"] -->|instance| dataMerge_cWaitMerge2_224b_int["dataMerge: cWaitMerge2_224b_int"]
  inStack["inStack"] -->|instance| inStackMerge_cMutexMerge2_1b["inStackMerge: cMutexMerge2_1b"]
  inStack["inStack"] -->|instance| dataSpli_cSplitter2_1b_Nodata["dataSpli: cSplitter2_1b_Nodata"]
  inStack["inStack"] -->|component| cMutexMerge2_1b["cMutexMerge2_1b"]
  inStack["inStack"] -->|component| cSelector2_1b["cSelector2_1b"]
  inStack["inStack"] -->|component| cSplitter2_1b_Nodata["cSplitter2_1b_Nodata"]
  inStack["inStack"] -->|component| cWaitMerge2_224b_int["cWaitMerge2_224b_int"]
```

```text
inStack
|-- dataMerge: cWaitMerge2_224b_int
|-- inStackMerge: cMutexMerge2_1b
|-- dataSpli: cSplitter2_1b_Nodata
|-- cMutexMerge2_1b
|-- cSelector2_1b
|-- cSplitter2_1b_Nodata
`-- cWaitMerge2_224b_int
```

## 2. 输入/输出接口摘要

- 接收：drive 输入：`i_driveFromRGRF_1`, `i_driveFromRPSR_1`；数据输入：`i_SP_32`, `i_grfData_192`, `i_inOutDriToDataSpli_1`, `i_pc_32`, `i_psrData_32`；free 输入：`i_freeFromDR_1`, `i_freeFromRGRF_1`, `i_freeFromRPSR_1`, `i_freeFromSPDec`；其他输入：`i_DRSeleDriToinStackSele_1`。
- 输出：drive 输出：`o_driveFromSPDec`, `o_driveToRGRF_1`, `o_driveToRPSR_1`；数据输出：`o_SP_32`, `o_data_96`；free 输出：`o_freeFromInStack`, `o_freeFrominStackSele_1`, `o_freeToRGRF_1`, `o_freeToRPSR_1`；其他输出：`o_w_inStackDriToDR_1`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `drive_event` | input:2, output:3 | `i_driveFromRGRF_1`, `i_driveFromRPSR_1`, `o_driveFromSPDec`, `o_driveToRGRF_1`, `o_driveToRPSR_1` |
| `free_backpressure` | input:4, output:4 | `i_freeFromDR_1`, `i_freeFromRGRF_1`, `i_freeFromRPSR_1`, `i_freeFromSPDec`, `o_freeFromInStack`, `o_freeFrominStackSele_1`, `o_freeToRGRF_1`, `o_freeToRPSR_1` |
| `other_ports` | input:6, output:3 | `i_SP_32`, `i_grfData_192`, `i_inOutDriToDataSpli_1`, `i_pc_32`, `i_psrData_32`, `o_SP_32`, `o_data_96`, `i_DRSeleDriToinStackSele_1`, `o_w_inStackDriToDR_1` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `i_driveFromRGRF_1` | input | `i_driveFromRGRF_1` | 未记录 | `o_freeToRGRF_1` |
| `i_driveFromRPSR_1` | input | `i_driveFromRPSR_1` | 未记录 | `o_freeToRPSR_1` |
| `o_driveFromSPDec` | output | `o_driveFromSPDec` | 未记录 | `i_freeFromSPDec` |
| `o_driveToRGRF_1` | output | `o_driveToRGRF_1` | 未记录 | `i_freeFromRGRF_1` |
| `o_driveToRPSR_1` | output | `o_driveToRPSR_1` | 未记录 | `i_freeFromRPSR_1` |

## 4. 主要 Drive-centered Flow

### `i_driveFromRGRF_1`

- 确定性事实：`inStack flow from i_driveFromRGRF_1`；flow_id=`flow_000_inStack_i_driveFromRGRF_1`。
- Payload：未记录。
- 输出/影响：证据不足：Knowledge IR did not find a module output endpoint for this flow.。
- 结构复杂度：branch=0，join=2，blocking=2。
- AI 推断：手册应强调这是一个不完全的两级合并内部流，说明合并器类型及其仲裁/等待语义，并指出 `w_inStackDriToDR_1` 去向不明。

### `i_driveFromRPSR_1`

- 确定性事实：`inStack flow from i_driveFromRPSR_1`；flow_id=`flow_001_inStack_i_driveFromRPSR_1`。
- Payload：未记录。
- 输出/影响：证据不足：Knowledge IR did not find a module output endpoint for this flow.。
- 结构复杂度：branch=0，join=2，blocking=2。
- AI 推断：终稿应弱化该流的独立输出角色，强调其为内部数据驱动合并与仲裁的预备路径，且可能作为更大状态机事件的一部分。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| `dataMerge` | `cWaitMerge2_224b_int` | `i_driveFromRGRF_1`, `i_driveFromRPSR_1` | `w_dataMerDriveToInMer_1` |
| `inStackMerge` | `cMutexMerge2_1b` | `w_dataMerDriveToInMer_1` | 无 |
| `dataSpli` | `cSplitter2_1b_Nodata` | 无 | `o_driveToRGRF_1`, `o_driveToRPSR_1` |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_4` | data_path | `w_inData0Addr_32` | i_SP_32 - 8 | AI 推断：将内部寄存器 r_SP_32 直接驱动到输出 o_SP_32，反映更新后的栈指针。 |
| `assign_5` | data_path | `w_inData1Addr_32` | i_SP_32 - 16 | AI 推断：将内部寄存器 r_SP_32 直接驱动到输出 o_SP_32，反映更新后的栈指针。 |
| `assign_6` | data_path | `w_inData2Addr_32` | i_SP_32 - 24 | AI 推断：将内部寄存器 r_SP_32 直接驱动到输出 o_SP_32，反映更新后的栈指针。 |
| `assign_7` | data_path | `w_inData3Addr_32` | i_SP_32 - 32 | AI 推断：将内部寄存器 r_SP_32 直接驱动到输出 o_SP_32，反映更新后的栈指针。 |
| `assign_10` | data_path | `o_data_96` | (w_inNum_2==2'b00)?({w_inData0_64,w_inData0Addr_32}): (w_inNum_2==2'b01)?({w_inData1_64,w_inD... | AI 推断：计算栈条目0的地址为 i_SP_32 - 8，后续 assign_5/6/7 分别计算条目1~3地址为 SP-16/-24/-32。 |
| `assign_11` | data_path | `o_SP_32` | r_SP_32 | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_0` | data_path | `w_inData0_64` | {i_pc_32, w_stackData_224[223:192]} | AI 推断：根据 w_inNum_2 选择一组合并的 64 位数据与 32 位地址输出，作为栈写入数据总线。 |
