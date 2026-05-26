# 模块 `arbMsg`

- 源文件：`rtl/rtl/IONet/IONetwork_9.24/arbMsg.v`。
- 职责：AI 推断：五路输入消息仲裁与合并模块，将来自东、本地、北、南、西五个方向的消息请求合并为单一输出。。
- 说明：模块接收五个方向的事件驱动信号（i_driveEast等）及其对应的51位消息负载，通过内部实例arbMerge（cArbMerge5_51b）进行仲裁合并，输出一个合并后的消息o_msg_51和驱动事件o_driveNext。同时，模块接收一个释放信号i_freeNext，并产生五个方向的释放输出（o_freeEast等），表明arbMerge内部实现了释放信号的扇出。

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
- AI 推断：文档应强调 i_driveEast 如何通过 arbMerge 与其他方向事件合并，并说明仲裁/合并策略

### `i_driveLocal`

- 确定性事实：`i_driveLocal to o_driveNext`；flow_id=`flow_001_arbMsg_i_driveLocal`。
- Payload：`i_driveLocal` -> `i_localMsg_51 [50:0]`, `o_driveNext` -> `o_msg_51 [50:0]`。
- 输出/影响：`o_driveNext`。
- 结构复杂度：branch=0，join=1，blocking=1。
- AI 推断：本地驱动事件 i_driveLocal 携带 51 位数据负载 i_localMsg_51，两者在模块接口层面耦合

### `i_driveNorth`

- 确定性事实：`i_driveNorth to o_driveNext`；flow_id=`flow_002_arbMsg_i_driveNorth`。
- Payload：`i_driveNorth` -> `i_northMsg_51 [50:0]`, `o_driveNext` -> `o_msg_51 [50:0]`。
- 输出/影响：`o_driveNext`。
- 结构复杂度：branch=0，join=1，blocking=1。
- AI 推断：北向事件驱动信号与 51 位数据载荷相关联

### `i_driveSouth`

- 确定性事实：`i_driveSouth to o_driveNext`；flow_id=`flow_003_arbMsg_i_driveSouth`。
- Payload：`i_driveSouth` -> `i_southMsg_51 [50:0]`, `o_driveNext` -> `o_msg_51 [50:0]`。
- 输出/影响：`o_driveNext`。
- 结构复杂度：branch=0，join=1，blocking=1。
- AI 推断：事件驱动信号 i_driveSouth 与南向消息负载 i_southMsg_51 相关联，两者共同通过 arbMerge 处理后输出为 o_driveNext 和 o_msg_51。

### `i_driveWest`

- 确定性事实：`i_driveWest to o_driveNext`；flow_id=`flow_004_arbMsg_i_driveWest`。
- Payload：`i_driveWest` -> `i_westMsg_51 [50:0]`, `o_driveNext` -> `o_msg_51 [50:0]`。
- 输出/影响：`o_driveNext`。
- 结构复杂度：branch=0，join=1，blocking=1。
- AI 推断：西侧消息数据与驱动事件同步传输，但数据路径独立于事件控制


## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| `arbMerge` | `cArbMerge5_51b` | `i_driveEast`, `i_driveLocal`, `i_driveNorth`, `i_driveSouth`, `i_driveWest` | `o_driveNext` |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| - | - | - | - | Manual Context 未提供 primary assign 影响 |
