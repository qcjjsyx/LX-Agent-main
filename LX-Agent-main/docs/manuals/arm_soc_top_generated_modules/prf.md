# 模块 `prf`

- 源文件：`rtl\rtl\PRF\prf.v`。
- 职责：AI 推断：物理寄存器文件模块，负责存储和转发通用寄存器（PRF）和程序状态寄存器（PSR）的值，并管理来自发射、写回和异常阶段的驱动与释放事件。。
- 说明：模块通过多个Fifo1和MutexMerge组件处理来自不同流水线阶段的驱动事件（i_prfDriveFromLaunch_1等）和释放事件（i_prfFreeFromLaunch_1等），将数据（i_rdDataToPrf_32）写入内部寄存器（r_prfValue_32, r_psrValue_32），并通过输出事件（o_prfDriveToLaunch_1等）将数据（o_prfDataToLaunch_32等）转发出去。证据显示其核心功能是寄存器值的存储和基于事件驱动的数据分发。

## 1. 层级位置

- Parents：`cpu_top_all`。
- Children：无。
- Component children：`cFifo1`, `cLastFifo1`, `cMutexMerge2_8b`。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

```mermaid
flowchart TB
  prf["prf"] -->|instance| cMutexMerge2_8b_cMutexMerge2_8b["cMutexMerge2_8b: cMutexMerge2_8b"]
  prf["prf"] -->|instance| cFifo1_prf1_cFifo1["cFifo1_prf1: cFifo1"]
  prf["prf"] -->|instance| cFifo1_prf2_cFifo1["cFifo1_prf2: cFifo1"]
  prf["prf"] -->|instance| cFifo1_prf3_cFifo1["cFifo1_prf3: cFifo1"]
  prf["prf"] -->|instance| cLastFifo1_prf1_cLastFifo1["cLastFifo1_prf1: cLastFifo1"]
  prf["prf"] -->|instance| cLastFifo2_prf2_cLastFifo1["cLastFifo2_prf2: cLastFifo1"]
  prf["prf"] -->|component| cFifo1["cFifo1"]
  prf["prf"] -->|component| cLastFifo1["cLastFifo1"]
  prf["prf"] -->|component| cMutexMerge2_8b["cMutexMerge2_8b"]
```

```text
prf
|-- cMutexMerge2_8b: cMutexMerge2_8b
|-- cFifo1_prf1: cFifo1
|-- cFifo1_prf2: cFifo1
|-- cFifo1_prf3: cFifo1
|-- cLastFifo1_prf1: cLastFifo1
|-- cLastFifo2_prf2: cLastFifo1
|-- cFifo1
|-- cLastFifo1
`-- cMutexMerge2_8b
```

## 2. 输入/输出接口摘要

- 接收：drive 输入：`i_prfDriveFromLaunch_1`, `i_prfDriveFromWB_1`, `i_psrDriveFromExp_1`, `i_psrDriveFromLaunch_1`, `... +2`；数据输入：`i_expen_4`, `i_expnzcv_4`, `i_rdAddr_8`, `i_rdDataToPrf_32`, `... +3`；free 输入：`i_prfFreeFromLaunch_1`, `i_psrFreeFromExp_1`, `i_psrFreeFromLaunch_1`。
- 输出：drive 输出：`o_prfDriveToLaunch_1`, `o_psrDriveToExp_1`, `o_psrDriveToLaunch_1`；数据输出：`o_prfDataToLaunch_32`, `o_psrDataToExp_32`, `o_psrDataToLaunch_32`；free 输出：`o_prfFreeToLaunch_1`, `o_prfFreeToWB_1`, `o_psrFreeToExp_1`, `o_psrFreeToLaunch_1`, `... +2`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `drive_event` | input:6, output:3 | `i_prfDriveFromLaunch_1`, `i_prfDriveFromWB_1`, `i_psrDriveFromExp_1`, `i_psrDriveFromLaunch_1`, `i_psrDriveFromWB_1`, `i_psrwDriveFromExp_1`, `o_prfDriveToLaunch_1`, `o_psrDriveToExp_1`, `o_psrDriveToLaunch_1` |
| `free_backpressure` | input:3, output:6 | `i_prfFreeFromLaunch_1`, `i_psrFreeFromExp_1`, `i_psrFreeFromLaunch_1`, `o_prfFreeToLaunch_1`, `o_prfFreeToWB_1`, `o_psrFreeToExp_1`, `o_psrFreeToLaunch_1`, `o_psrFreeToWB_1`, `o_psrwFreeToExp_1` |
| `other_ports` | input:7, output:3 | `i_expen_4`, `i_expnzcv_4`, `i_rdAddr_8`, `i_rdDataToPrf_32`, `i_rsAddr_8`, `i_wben_4`, `i_wbnzcv_4`, `o_prfDataToLaunch_32`, `o_psrDataToExp_32`, `o_psrDataToLaunch_32` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `i_prfDriveFromLaunch_1` | input | `i_prfDriveFromLaunch_1` | `i_rdDataToPrf_32 [31:0]` | `o_prfFreeToLaunch_1` |
| `i_prfDriveFromWB_1` | input | `i_prfDriveFromWB_1` | `i_rdDataToPrf_32 [31:0]` | `o_prfFreeToWB_1` |
| `i_psrDriveFromExp_1` | input | `i_psrDriveFromExp_1` | `i_rdDataToPrf_32 [31:0]` | `o_psrFreeToExp_1` |
| `i_psrDriveFromLaunch_1` | input | `i_psrDriveFromLaunch_1` | `i_rdDataToPrf_32 [31:0]` | `o_prfFreeToLaunch_1` |
| `i_psrDriveFromWB_1` | input | `i_psrDriveFromWB_1` | `i_rdDataToPrf_32 [31:0]` | `o_prfFreeToWB_1` |
| `i_psrwDriveFromExp_1` | input | `i_psrwDriveFromExp_1` | `i_rdDataToPrf_32 [31:0]` | `o_psrFreeToExp_1` |
| `o_prfDriveToLaunch_1` | output | `o_prfDriveToLaunch_1` | `o_prfDataToLaunch_32 [31:0]`, `o_psrDataToLaunch_32 [31:0]` | `i_prfFreeFromLaunch_1` |
| `o_psrDriveToExp_1` | output | `o_psrDriveToExp_1` | `o_psrDataToExp_32 [31:0]` | `i_psrFreeFromExp_1` |
| `o_psrDriveToLaunch_1` | output | `o_psrDriveToLaunch_1` | `o_prfDataToLaunch_32 [31:0]`, `o_psrDataToLaunch_32 [31:0]` | `i_prfFreeFromLaunch_1` |

## 4. 主要 Drive-centered Flow

### `i_prfDriveFromLaunch_1`

- 确定性事实：`i_prfDriveFromLaunch_1 to o_prfDriveToLaunch_1`；flow_id=`flow_000_prf_i_prfDriveFromLaunch_1`。
- Payload：`i_prfDriveFromLaunch_1` -> `i_rdDataToPrf_32 [31:0]`, `o_prfDriveToLaunch_1` -> `o_prfDataToLaunch_32 [31:0]`, `o_prfDriveToLaunch_1` -> `o_psrDataToLaunch_32 [31:0]`。
- 输出/影响：`o_prfDriveToLaunch_1`。
- 结构复杂度：branch=0，join=0，blocking=1。
- AI 推断：文档应强调事件驱动路径与数据负载的独立赋值关系

### `i_prfDriveFromWB_1`

- 确定性事实：`prf flow from i_prfDriveFromWB_1`；flow_id=`flow_005_prf_i_prfDriveFromWB_1`。
- Payload：`i_prfDriveFromWB_1` -> `i_rdDataToPrf_32 [31:0]`。
- 输出/影响：证据不足：Knowledge IR did not find a module output endpoint for this flow.。
- 结构复杂度：branch=0，join=0，blocking=1。
- AI 推断：驱动事件i_prfDriveFromWB_1携带有效载荷i_rdDataToPrf_32（32位读数据），该载荷在事件进入FIFO时被传递。

### `i_psrDriveFromExp_1`

- 确定性事实：`i_psrDriveFromExp_1 to o_psrDriveToExp_1`；flow_id=`flow_001_prf_i_psrDriveFromExp_1`。
- Payload：`i_psrDriveFromExp_1` -> `i_rdDataToPrf_32 [31:0]`, `o_psrDriveToExp_1` -> `o_psrDataToExp_32 [31:0]`。
- 输出/影响：`o_psrDriveToExp_1`。
- 结构复杂度：branch=0，join=0，blocking=1。
- AI 推断：最终手册应重点描述该流作为单级FIFO事件转发路径，并说明载荷数据从输入到输出的传递关系，但需避免过度推断FIFO内部行为。

### `i_psrDriveFromLaunch_1`

- 确定性事实：`i_psrDriveFromLaunch_1 to o_psrDriveToLaunch_1`；flow_id=`flow_002_prf_i_psrDriveFromLaunch_1`。
- Payload：`i_psrDriveFromLaunch_1` -> `i_rdDataToPrf_32 [31:0]`, `o_psrDriveToLaunch_1` -> `o_prfDataToLaunch_32 [31:0]`, `o_psrDriveToLaunch_1` -> `o_psrDataToLaunch_32 [31:0]`。
- 输出/影响：`o_psrDriveToLaunch_1`。
- 结构复杂度：branch=0，join=0，blocking=1。
- AI 推断：事件流i_psrDriveFromLaunch_1到o_psrDriveToLaunch_1的传播，与载荷数据o_prfDataToLaunch_32和o_psrDataToLaunch_32的更新是并行且独立的。

### `i_psrDriveFromWB_1`

- 确定性事实：`prf flow from i_psrDriveFromWB_1`；flow_id=`flow_003_prf_i_psrDriveFromWB_1`。
- Payload：`i_psrDriveFromWB_1` -> `i_rdDataToPrf_32 [31:0]`。
- 输出/影响：证据不足：Knowledge IR did not find a module output endpoint for this flow.。
- 结构复杂度：branch=0，join=1，blocking=2。
- AI 推断：写回阶段的数据载荷与事件驱动信号相关联，但数据路径未在流中显式跟踪

### `i_psrwDriveFromExp_1`

- 确定性事实：`prf flow from i_psrwDriveFromExp_1`；flow_id=`flow_004_prf_i_psrwDriveFromExp_1`。
- Payload：`i_psrwDriveFromExp_1` -> `i_rdDataToPrf_32 [31:0]`。
- 输出/影响：证据不足：Knowledge IR did not find a module output endpoint for this flow.。
- 结构复杂度：branch=0，join=1，blocking=2。
- AI 推断：该驱动流携带来自异常阶段的写数据负载i_rdDataToPrf_32，数据与控制事件同步传递。


## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| `cMutexMerge2_8b` | `cMutexMerge2_8b` | `i_psrDriveFromWB_1`, `i_psrwDriveFromExp_1` | `w_driveTopsr` |
| `cFifo1_prf1` | `cFifo1` | `i_prfDriveFromLaunch_1` | `o_prfDriveToLaunch_1` |
| `cFifo1_prf2` | `cFifo1` | `i_psrDriveFromLaunch_1` | `o_psrDriveToLaunch_1` |
| `cFifo1_prf3` | `cFifo1` | `i_psrDriveFromExp_1` | `o_psrDriveToExp_1` |
| `cLastFifo1_prf1` | `cLastFifo1` | `i_prfDriveFromWB_1` | 无 |
| `cLastFifo2_prf2` | `cLastFifo1` | `w_driveTopsr` | 无 |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_1` | data_path | `o_psrDataToLaunch_32` | r_psrValue_32 | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_2` | data_path | `o_psrDataToExp_32` | r_psrValue2_32 | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_0` | data_path | `o_prfDataToLaunch_32` | r_prfValue_32 | 证据不足：No Semantic Layer assignment interpretation is available. |
