# 模块 `perip_slot`

- 源文件：`rtl/rtl/IONet/GPIO/perip_slot.v`。
- 职责：AI 推断：外围设备插槽模块，负责在Mesh网络与外围设备之间进行驱动事件和释放事件的流水线缓冲与延迟同步。。
- 说明：模块通过两个cFifo1实例（cFifo_1和cFifo_2）以及两级延迟单元（delay0、delay1）构成驱动事件链，将来自Mesh的驱动事件（i_driveFrmMesh）经过缓冲和延迟后输出到Mesh（o_driveNextToMesh），同时处理释放事件（i_freeNextFrmMesh、o_freeToMesh）的同步。数据端口（data_from、data_to、addr_i、data_i、data_o）表明模块还承担数据路径的桥接角色，但事件与数据的关联契约证据不足。

## 1. 层级位置

- Parents：`gpio_slot`。
- Children：`fire2SyncPluse`。
- Component children：`cFifo1`。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

```mermaid
flowchart TB
  perip_slot["perip_slot"] -->|instance| cFifo_1_cFifo1["cFifo_1: cFifo1"]
  perip_slot["perip_slot"] -->|instance| cFifo_2_cFifo1["cFifo_2: cFifo1"]
  perip_slot["perip_slot"] --> fire2SyncPluse["fire2SyncPluse"]
  perip_slot["perip_slot"] -->|component| cFifo1["cFifo1"]
```

```text
perip_slot
|-- cFifo_1: cFifo1
|-- cFifo_2: cFifo1
|-- fire2SyncPluse
`-- cFifo1
```

## 2. 输入/输出接口摘要

- 接收：drive 输入：`i_driveFrmMesh`；数据输入：`data_from`, `data_o`；free 输入：`i_freeNextFrmMesh`；其他输入：`clk`, `rst_finish`。
- 输出：drive 输出：`o_driveNextToMesh`；数据输出：`addr_i`, `data_i`, `data_to`；free 输出：`o_freeToMesh`；其他输出：`we`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:2 | `clk`, `rst_finish` |
| `drive_event` | input:1, output:1 | `i_driveFrmMesh`, `o_driveNextToMesh` |
| `free_backpressure` | input:1, output:1 | `i_freeNextFrmMesh`, `o_freeToMesh` |
| `other_ports` | input:2, output:4 | `data_from`, `data_o`, `addr_i`, `data_i`, `data_to`, `we` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `i_driveFrmMesh` | input | `i_driveFrmMesh` | 未记录 | `o_freeToMesh` |
| `o_driveNextToMesh` | output | `o_driveNextToMesh` | 未记录 | `i_freeNextFrmMesh` |

## 4. 主要 Drive-centered Flow

### `i_driveFrmMesh`

- 确定性事实：`i_driveFrmMesh to o_driveNextToMesh`；flow_id=`flow_000_perip_slot_i_driveFrmMesh`。
- Payload：未记录。
- 输出/影响：`o_driveNextToMesh`。
- 结构复杂度：branch=0，join=0，blocking=2。
- AI 推断：最终手册应强调该流是单向、无数据负载的事件传播路径，并说明FIFO作为节流点的作用，同时指出延迟单元仅用于时序调整。


## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| `cFifo_1` | `cFifo1` | `i_driveFrmMesh` | `w_drv2Fifo2` |
| `cFifo_2` | `cFifo1` | `w_drv2Fifo2_delay2` | `o_driveNextToMesh` |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_0` | unknown | `we` | (!we_r) & rise | AI 推断：写使能信号生成，基于上升沿检测和延迟版本信号。 |
