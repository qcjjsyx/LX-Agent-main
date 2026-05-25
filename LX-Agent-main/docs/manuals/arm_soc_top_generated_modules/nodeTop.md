# 模块 `nodeTop`

- 源文件：`rtl/rtl/IONet/IONetwork_9.24/nodeTop.v`。
- 职责：AI 推断：nodeTop 是一个五方向（东、本地、北、南、西）网络节点路由器，负责将来自五个输入方向的消息路由到五个输出方向。。
- 说明：模块具有五个方向的事件输入（i_drive*）和输出（o_drive*），以及对应的数据输入（i_*InMsg_51）和数据输出（o_*Msg_51）。内部由五个 routeMsg 实例和五个 arbMsg 实例组成，分别负责消息路由和仲裁，形成完整的交叉开关结构。

## 1. 层级位置

- Parents：`IONetwork`。
- Children：`arbMsg`, `routeMsg`。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

```mermaid
flowchart TB
  nodeTop["nodeTop"] -->|instance| eastArbMsg_arbMsg["eastArbMsg: arbMsg"]
  nodeTop["nodeTop"] -->|instance| eastRouteMsg_routeMsg["eastRouteMsg: routeMsg"]
  nodeTop["nodeTop"] -->|instance| localArbMsg_arbMsg["localArbMsg: arbMsg"]
  nodeTop["nodeTop"] -->|instance| localRouteMsg_routeMsg["localRouteMsg: routeMsg"]
  nodeTop["nodeTop"] -->|instance| northArbMsg_arbMsg["northArbMsg: arbMsg"]
  nodeTop["nodeTop"] -->|instance| northRouteMsg_routeMsg["northRouteMsg: routeMsg"]
  nodeTop["nodeTop"] -->|instance| southArbMsg_arbMsg["southArbMsg: arbMsg"]
  nodeTop["nodeTop"] -->|instance| southRouteMsg_routeMsg["southRouteMsg: routeMsg"]
  nodeTop["nodeTop"] -->|instance| westArbMsg_arbMsg["westArbMsg: arbMsg"]
  nodeTop["nodeTop"] -->|instance| westRouteMsg_routeMsg["westRouteMsg: routeMsg"]
  nodeTop["nodeTop"] --> arbMsg["arbMsg"]
  nodeTop["nodeTop"] --> routeMsg["routeMsg"]
```

```text
nodeTop
|-- eastArbMsg: arbMsg
|-- eastRouteMsg: routeMsg
|-- localArbMsg: arbMsg
|-- localRouteMsg: routeMsg
|-- northArbMsg: arbMsg
|-- northRouteMsg: routeMsg
|-- southArbMsg: arbMsg
|-- southRouteMsg: routeMsg
|-- westArbMsg: arbMsg
|-- westRouteMsg: routeMsg
|-- arbMsg
`-- routeMsg
```

## 2. 输入/输出接口摘要

- 接收：drive 输入：`i_driveEast`, `i_driveLocal`, `i_driveNorth`, `i_driveSouth`, `... +1`；数据输入：`i_eastInMsg_51`, `i_localInMsg_51`, `i_northInMsg_51`, `i_southInMsg_51`, `... +1`；free 输入：`i_freeEast`, `i_freeLocal`, `i_freeNorth`, `i_freeSouth`, `... +1`。
- 输出：drive 输出：`o_driveEast`, `o_driveLocal`, `o_driveNorth`, `o_driveSouth`, `... +1`；数据输出：`o_eastMsg_51`, `o_localMsg_51`, `o_northMsg_51`, `o_southMsg_51`, `... +1`；free 输出：`o_freeEast`, `o_freeLocal`, `o_freeNorth`, `o_freeSouth`, `... +1`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `drive_event` | input:5, output:5 | `i_driveEast`, `i_driveLocal`, `i_driveNorth`, `i_driveSouth`, `i_driveWest`, `o_driveEast`, `o_driveLocal`, `o_driveNorth`, `o_driveSouth`, `o_driveWest` |
| `free_backpressure` | input:5, output:5 | `i_freeEast`, `i_freeLocal`, `i_freeNorth`, `i_freeSouth`, `i_freeWest`, `o_freeEast`, `o_freeLocal`, `o_freeNorth`, `o_freeSouth`, `o_freeWest` |
| `other_ports` | input:5, output:5 | `i_eastInMsg_51`, `i_localInMsg_51`, `i_northInMsg_51`, `i_southInMsg_51`, `i_westInMsg_51`, `o_eastMsg_51`, `o_localMsg_51`, `o_northMsg_51`, `o_southMsg_51`, `o_westMsg_51` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `i_driveEast` | input | `i_driveEast` | `i_eastInMsg_51 [50:0]` | `o_freeEast` |
| `i_driveLocal` | input | `i_driveLocal` | `i_localInMsg_51 [50:0]` | `o_freeLocal` |
| `i_driveNorth` | input | `i_driveNorth` | `i_northInMsg_51 [50:0]` | `o_freeNorth` |
| `i_driveSouth` | input | `i_driveSouth` | `i_southInMsg_51 [50:0]` | `o_freeSouth` |
| `i_driveWest` | input | `i_driveWest` | `i_westInMsg_51 [50:0]` | `o_freeWest` |
| `o_driveEast` | output | `o_driveEast` | `o_eastMsg_51 [50:0]` | `i_freeEast` |
| `o_driveLocal` | output | `o_driveLocal` | `o_localMsg_51 [50:0]` | `i_freeLocal` |
| `o_driveNorth` | output | `o_driveNorth` | `o_northMsg_51 [50:0]` | `i_freeNorth` |
| `o_driveSouth` | output | `o_driveSouth` | `o_southMsg_51 [50:0]` | `i_freeSouth` |
| `o_driveWest` | output | `o_driveWest` | `o_westMsg_51 [50:0]` | `i_freeWest` |

## 4. 主要 Drive-centered Flow

### `i_driveEast`

- 确定性事实：`i_driveEast to o_driveEast, o_driveLocal, o_driveNorth`；flow_id=`flow_000_nodeTop_i_driveEast`。
- Payload：`i_driveEast` -> `i_eastInMsg_51 [50:0]`, `o_driveEast` -> `o_eastMsg_51 [50:0]`, `o_driveLocal` -> `o_localMsg_51 [50:0]`, `o_driveNorth` -> `o_northMsg_51 [50:0]`, `o_driveSouth` -> `o_southMsg_51 [50:0]`, `o_driveWest` -> `o_westMsg_51 [50:0]`。
- 输出/影响：`o_driveEast`, `o_driveLocal`, `o_driveNorth`, `o_driveSouth`, `o_driveWest`。
- 结构复杂度：branch=1，join=5，blocking=0。
- AI 推断：手册应重点描述从东向输入事件到五个方向输出的路由分发和仲裁过程。

### `i_driveLocal`

- 确定性事实：`i_driveLocal to o_driveEast, o_driveLocal, o_driveNorth`；flow_id=`flow_001_nodeTop_i_driveLocal`。
- Payload：`i_driveLocal` -> `i_localInMsg_51 [50:0]`, `o_driveEast` -> `o_eastMsg_51 [50:0]`, `o_driveLocal` -> `o_localMsg_51 [50:0]`, `o_driveNorth` -> `o_northMsg_51 [50:0]`, `o_driveSouth` -> `o_southMsg_51 [50:0]`, `o_driveWest` -> `o_westMsg_51 [50:0]`。
- 输出/影响：`o_driveEast`, `o_driveLocal`, `o_driveNorth`, `o_driveSouth`, `o_driveWest`。
- 结构复杂度：branch=1，join=5，blocking=0。
- AI 推断：手册应重点描述本地事件如何经路由后分发到五个方向仲裁器，以及仲裁器的输入源竞争关系

### `i_driveNorth`

- 确定性事实：`i_driveNorth to o_driveEast, o_driveLocal, o_driveNorth`；flow_id=`flow_002_nodeTop_i_driveNorth`。
- Payload：`i_driveNorth` -> `i_northInMsg_51 [50:0]`, `o_driveEast` -> `o_eastMsg_51 [50:0]`, `o_driveLocal` -> `o_localMsg_51 [50:0]`, `o_driveNorth` -> `o_northMsg_51 [50:0]`, `o_driveSouth` -> `o_southMsg_51 [50:0]`, `o_driveWest` -> `o_westMsg_51 [50:0]`。
- 输出/影响：`o_driveEast`, `o_driveLocal`, `o_driveNorth`, `o_driveSouth`, `o_driveWest`。
- 结构复杂度：branch=1，join=5，blocking=0。
- AI 推断：应重点描述北向输入事件如何通过路由扇出和仲裁，最终驱动五个方向输出事件

### `i_driveSouth`

- 确定性事实：`i_driveSouth to o_driveEast, o_driveLocal, o_driveNorth`；flow_id=`flow_003_nodeTop_i_driveSouth`。
- Payload：`i_driveSouth` -> `i_southInMsg_51 [50:0]`, `o_driveEast` -> `o_eastMsg_51 [50:0]`, `o_driveLocal` -> `o_localMsg_51 [50:0]`, `o_driveNorth` -> `o_northMsg_51 [50:0]`, `o_driveSouth` -> `o_southMsg_51 [50:0]`, `o_driveWest` -> `o_westMsg_51 [50:0]`。
- 输出/影响：`o_driveEast`, `o_driveLocal`, `o_driveNorth`, `o_driveSouth`, `o_driveWest`。
- 结构复杂度：branch=1，join=5，blocking=0。
- AI 推断：手册应重点描述从南向输入到五个方向输出的完整事件流，包括路由和仲裁阶段。

### `i_driveWest`

- 确定性事实：`i_driveWest to o_driveEast, o_driveLocal, o_driveNorth`；flow_id=`flow_004_nodeTop_i_driveWest`。
- Payload：`i_driveWest` -> `i_westInMsg_51 [50:0]`, `o_driveEast` -> `o_eastMsg_51 [50:0]`, `o_driveLocal` -> `o_localMsg_51 [50:0]`, `o_driveNorth` -> `o_northMsg_51 [50:0]`, `o_driveSouth` -> `o_southMsg_51 [50:0]`, `o_driveWest` -> `o_westMsg_51 [50:0]`。
- 输出/影响：`o_driveEast`, `o_driveLocal`, `o_driveNorth`, `o_driveSouth`, `o_driveWest`。
- 结构复杂度：branch=1，join=5，blocking=0。
- AI 推断：最终手册应重点描述从单一输入事件到多方向输出的分发和仲裁路径，并明确数据负载的关联关系。


## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| `eastArbMsg` | `arbMsg` | 无 | `o_driveEast` |
| `eastRouteMsg` | `routeMsg` | `i_driveEast` | 无 |
| `localArbMsg` | `arbMsg` | 无 | `o_driveLocal` |
| `localRouteMsg` | `routeMsg` | `i_driveLocal` | 无 |
| `northArbMsg` | `arbMsg` | 无 | `o_driveNorth` |
| `northRouteMsg` | `routeMsg` | `i_driveNorth` | 无 |
| `southArbMsg` | `arbMsg` | 无 | `o_driveSouth` |
| `southRouteMsg` | `routeMsg` | `i_driveSouth` | 无 |
| `westArbMsg` | `arbMsg` | 无 | `o_driveWest` |
| `westRouteMsg` | `routeMsg` | `i_driveWest` | 无 |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| - | - | - | - | Manual Context 未提供 primary assign 影响 |
