# 模块 `arbMsg`

- 源文件：`rtl/rtl/IONet/IONetwork_9.24/arbMsg.v`。
- 职责：AI 推断：五路输入消息仲裁与合并模块，负责从东、本地、北、南、西五个方向中选择一路消息转发至下一级。。
- 说明：模块接收五个方向的事件驱动信号(i_driveEast等)及其对应的51位消息载荷，通过内部实例arbMerge(cArbMerge5_51b)进行仲裁合并，输出选中的消息(o_msg_51)和驱动事件(o_driveNext)。同时根据下游空闲信号(i_freeNext)生成各方向独立的空闲反馈信号(o_freeEast等)。

## 1. 层级位置

- Parents：`nodeTop`。
- Children：无。
- Component children：`cArbMerge5_51b`。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

```mermaid
flowchart TB
  arbMsg["arbMsg"] -->|instance| arbMerge_cArbMerge5_51b["arbMerge: cArbMerge5_51b"]
  arbMsg["arbMsg"] -->|component| cArbMerge5_51b["cArbMerge5_51b"]
```

```text
arbMsg
|-- arbMerge: cArbMerge5_51b
`-- cArbMerge5_51b
```

## 2. 输入/输出接口摘要

- 接收：drive 输入：`i_driveEast`, `i_driveLocal`, `i_driveNorth`, `i_driveSouth`, `... +1`；数据输入：`i_eastMsg_51`, `i_localMsg_51`, `i_northMsg_51`, `i_southMsg_51`, `... +1`；free 输入：`i_freeNext`。
- 输出：drive 输出：`o_driveNext`；数据输出：`o_msg_51`；free 输出：`o_freeEast`, `o_freeLocal`, `o_freeNorth`, `o_freeSouth`, `... +1`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `drive_event` | input:5, output:1 | `i_driveEast`, `i_driveLocal`, `i_driveNorth`, `i_driveSouth`, `i_driveWest`, `o_driveNext` |
| `free_backpressure` | input:1, output:5 | `i_freeNext`, `o_freeEast`, `o_freeLocal`, `o_freeNorth`, `o_freeSouth`, `o_freeWest` |
| `other_ports` | input:5, output:1 | `i_eastMsg_51`, `i_localMsg_51`, `i_northMsg_51`, `i_southMsg_51`, `i_westMsg_51`, `o_msg_51` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `i_driveEast` | input | `i_driveEast` | `i_eastMsg_51 [50:0]` | `o_freeEast` |
| `i_driveLocal` | input | `i_driveLocal` | `i_localMsg_51 [50:0]` | `o_freeLocal` |
| `i_driveNorth` | input | `i_driveNorth` | `i_northMsg_51 [50:0]` | `o_freeNorth` |
| `i_driveSouth` | input | `i_driveSouth` | `i_southMsg_51 [50:0]` | `o_freeSouth` |
| `i_driveWest` | input | `i_driveWest` | `i_westMsg_51 [50:0]` | `o_freeWest` |
| `o_driveNext` | output | `o_driveNext` | `o_msg_51 [50:0]` | 未记录 |

## 4. 主要 Drive-centered Flow

### `i_driveEast`

- 确定性事实：`i_driveEast to o_driveNext`；flow_id=`flow_000_arbMsg_i_driveEast`。
- Payload：`i_driveEast` -> `i_eastMsg_51 [50:0]`, `o_driveNext` -> `o_msg_51 [50:0]`。
- 输出/影响：`o_driveNext`。
- 结构复杂度：branch=0，join=1，blocking=1。
- AI 推断：东向驱动事件携带一个 51 位数据载荷，该载荷通过 arbMerge 合并后输出

### `i_driveLocal`

- 确定性事实：`i_driveLocal to o_driveNext`；flow_id=`flow_001_arbMsg_i_driveLocal`。
- Payload：`i_driveLocal` -> `i_localMsg_51 [50:0]`, `o_driveNext` -> `o_msg_51 [50:0]`。
- 输出/影响：`o_driveNext`。
- 结构复杂度：branch=0，join=1，blocking=1。
- AI 推断：本地驱动事件携带51位数据负载，两者通过arbMerge同步转发

### `i_driveNorth`

- 确定性事实：`i_driveNorth to o_driveNext`；flow_id=`flow_002_arbMsg_i_driveNorth`。
- Payload：`i_driveNorth` -> `i_northMsg_51 [50:0]`, `o_driveNext` -> `o_msg_51 [50:0]`。
- 输出/影响：`o_driveNext`。
- 结构复杂度：branch=0，join=1，blocking=1。
- AI 推断：驱动事件i_driveNorth控制其关联的51位消息负载i_northMsg_51的传播

### `i_driveSouth`

- 确定性事实：`i_driveSouth to o_driveNext`；flow_id=`flow_003_arbMsg_i_driveSouth`。
- Payload：`i_driveSouth` -> `i_southMsg_51 [50:0]`, `o_driveNext` -> `o_msg_51 [50:0]`。
- 输出/影响：`o_driveNext`。
- 结构复杂度：branch=0，join=1，blocking=1。
- AI 推断：事件驱动信号 i_driveSouth 与数据负载信号 i_southMsg_51 相关联，后者作为输入数据被送入 arbMerge 实例。

### `i_driveWest`

- 确定性事实：`i_driveWest to o_driveNext`；flow_id=`flow_004_arbMsg_i_driveWest`。
- Payload：`i_driveWest` -> `i_westMsg_51 [50:0]`, `o_driveNext` -> `o_msg_51 [50:0]`。
- 输出/影响：`o_driveNext`。
- 结构复杂度：branch=0，join=1，blocking=1。
- AI 推断：西侧事件驱动信号 i_driveWest 与 51 位西侧消息负载 i_westMsg_51 相关联，但控制与数据的耦合方式未知


## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| `arbMerge` | `cArbMerge5_51b` | `i_driveEast`, `i_driveLocal`, `i_driveNorth`, `i_driveSouth`, `i_driveWest` | `o_driveNext` |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| - | - | - | - | Manual Context 未提供 primary assign 影响 |
