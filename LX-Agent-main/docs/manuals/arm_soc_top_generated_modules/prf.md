# 模块 `prf`

- 源文件：`rtl/rtl/PRF/prf.v`。
- 职责：AI 推断：物理寄存器文件模块，负责存储和转发通用寄存器（PRF）和程序状态寄存器（PSR）的值。。
- 说明：模块通过多个驱动事件（来自发射、写回、异常阶段）接收数据，并通过FIFO组件进行缓冲和排序，最终将数据输出到发射和异常阶段。同时，模块管理释放信号，指示数据已被消费。

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
- AI 推断：单级FIFO直通驱动流，将输入事件i_prfDriveFromLaunch_1通过cFifo1_prf1缓冲后直接输出为o_prfDriveToLaunch_1

### `i_prfDriveFromWB_1`

- 确定性事实：`prf flow from i_prfDriveFromWB_1`；flow_id=`flow_005_prf_i_prfDriveFromWB_1`。
- Payload：`i_prfDriveFromWB_1` -> `i_rdDataToPrf_32 [31:0]`。
- 输出/影响：证据不足：Knowledge IR did not find a module output endpoint for this flow.。
- 结构复杂度：branch=0，join=0，blocking=1。
- AI 推断：事件携带读回数据载荷进入FIFO

### `i_psrDriveFromExp_1`

- 确定性事实：`i_psrDriveFromExp_1 to o_psrDriveToExp_1`；flow_id=`flow_001_prf_i_psrDriveFromExp_1`。
- Payload：`i_psrDriveFromExp_1` -> `i_rdDataToPrf_32 [31:0]`, `o_psrDriveToExp_1` -> `o_psrDataToExp_32 [31:0]`。
- 输出/影响：`o_psrDriveToExp_1`。
- 结构复杂度：branch=0，join=0，blocking=1。
- AI 推断：手册应强调该流是一个简单的单级 FIFO 缓冲事件驱动路径，并指出数据路径与事件路径分离，但可能存在隐含的握手或反压机制。

### `i_psrDriveFromLaunch_1`

- 确定性事实：`i_psrDriveFromLaunch_1 to o_psrDriveToLaunch_1`；flow_id=`flow_002_prf_i_psrDriveFromLaunch_1`。
- Payload：`i_psrDriveFromLaunch_1` -> `i_rdDataToPrf_32 [31:0]`, `o_psrDriveToLaunch_1` -> `o_prfDataToLaunch_32 [31:0]`, `o_psrDriveToLaunch_1` -> `o_psrDataToLaunch_32 [31:0]`。
- 输出/影响：`o_psrDriveToLaunch_1`。
- 结构复杂度：branch=0，join=0，blocking=1。
- AI 推断：事件o_psrDriveToLaunch_1的传播由FIFO控制，而数据载荷o_prfDataToLaunch_32和o_psrDataToLaunch_32由独立赋值驱动，表明数据与事件在传播路径上解耦。

### `i_psrDriveFromWB_1`

- 确定性事实：`prf flow from i_psrDriveFromWB_1`；flow_id=`flow_003_prf_i_psrDriveFromWB_1`。
- Payload：`i_psrDriveFromWB_1` -> `i_rdDataToPrf_32 [31:0]`。
- 输出/影响：证据不足：Knowledge IR did not find a module output endpoint for this flow.。
- 结构复杂度：branch=0，join=1，blocking=2。
- AI 推断：手册应强调该流从输入端口经合并器到FIFO级后终止，未到达模块输出端点

### `i_psrwDriveFromExp_1`

- 确定性事实：`prf flow from i_psrwDriveFromExp_1`；flow_id=`flow_004_prf_i_psrwDriveFromExp_1`。
- Payload：`i_psrwDriveFromExp_1` -> `i_rdDataToPrf_32 [31:0]`。
- 输出/影响：证据不足：Knowledge IR did not find a module output endpoint for this flow.。
- 结构复杂度：branch=0，join=1，blocking=2。
- AI 推断：存在一个空闲信号 o_psrFreeToExp_1 可能用于反压异常阶段的写请求，但其与流中组件的连接未定义。


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
| `assign_1` | data_path | `o_psrDataToLaunch_32` | r_psrValue_32 | AI 推断：将内部寄存器r_psrValue_32的值直接赋值给输出端口，用于向发射阶段提供PSR数据。 |
| `assign_2` | data_path | `o_psrDataToExp_32` | r_psrValue2_32 | AI 推断：将内部寄存器r_psrValue2_32的值直接赋值给输出端口，用于向异常阶段提供PSR数据。 |
| `assign_0` | data_path | `o_prfDataToLaunch_32` | r_prfValue_32 | AI 推断：将内部寄存器r_prfValue_32的值直接赋值给输出端口，用于向发射阶段提供PRF数据。 |
