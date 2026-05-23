# 模块 `I2C2NoC`

- 源文件：`rtl\rtl\IONet\IIC\I2C2NoC.v`。
- 职责：AI 推断：该模块作为I2C主控制器（mi2cv2）与片上网络（NoC）之间的桥接与事件驱动接口适配器。。
- 说明：模块将来自NoC的驱动事件（i_drvFNoc）及其关联的51位数据（i_dataFNoc_51）通过内部FIFO和延迟链进行同步与整形，最终生成输出驱动事件（o_drv2Noc）和输出数据（o_data2Noc_51）。同时，它还处理空闲信号（i_freeFNoc, o_free2Noc）以管理数据流控制。核心组件是I2C控制器实例U1（mi2cv2）和三个FIFO实例（cfifo1, cfifo2, cfifo3_0）。

## 1. 层级位置

- Parents：`IONet_slot`。
- Children：`mi2cv2`。
- Component children：`cFifo1`, `cFifo3_I2C`, `cFifo3_I2C_1`。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

```mermaid
flowchart TB
  I2C2NoC["I2C2NoC"] -->|instance| cfifo1_cFifo1["cfifo1: cFifo1"]
  I2C2NoC["I2C2NoC"] -->|instance| cfifo2_cFifo3_I2C["cfifo2: cFifo3_I2C"]
  I2C2NoC["I2C2NoC"] -->|instance| cfifo3_0_cFifo3_I2C_1["cfifo3_0: cFifo3_I2C_1"]
  I2C2NoC["I2C2NoC"] --> mi2cv2["mi2cv2"]
  I2C2NoC["I2C2NoC"] -->|component| cFifo1["cFifo1"]
  I2C2NoC["I2C2NoC"] -->|component| cFifo3_I2C["cFifo3_I2C"]
  I2C2NoC["I2C2NoC"] -->|component| cFifo3_I2C_1["cFifo3_I2C_1"]
```

```text
I2C2NoC
|-- cfifo1: cFifo1
|-- cfifo2: cFifo3_I2C
|-- cfifo3_0: cFifo3_I2C_1
|-- mi2cv2
|-- cFifo1
|-- cFifo3_I2C
`-- cFifo3_I2C_1
```

## 2. 输入/输出接口摘要

- 接收：drive 输入：`i_drvFNoc`；数据输入：`i_dataFNoc_51`；free 输入：`i_freeFNoc`；其他输入：`CLOCK`, `FSEN`, `HSEN`, `IFSDA`, `... +3`。
- 输出：drive 输出：`o_drv2Noc`；数据输出：`o_data2Noc_51`；free 输出：`o_free2Noc`；其他输出：`CKISO`, `DAGND`, `DAISO`, `ENDRV`, `... +3`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:1 | `rst_finish` |
| `drive_event` | input:1, output:2 | `i_drvFNoc`, `o_drv2Noc`, `ENDRV` |
| `free_backpressure` | input:1, output:1 | `i_freeFNoc`, `o_free2Noc` |
| `other_ports` | input:7, output:7 | `i_dataFNoc_51`, `o_data2Noc_51`, `CLOCK`, `FSEN`, `HSEN`, `IFSDA`, `ISCL`, `ISDA`, `CKISO`, `DAGND`, `... +4` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `i_drvFNoc` | input | `i_drvFNoc` | `i_dataFNoc_51 [50:0]` | 未记录 |
| `o_drv2Noc` | output | `o_drv2Noc` | `o_data2Noc_51 [50:0]` | 未记录 |

## 4. 主要 Drive-centered Flow

### `i_drvFNoc`

- 确定性事实：`i_drvFNoc to o_drv2Noc`；flow_id=`flow_000_I2C2NoC_i_drvFNoc`。
- Payload：`i_drvFNoc` -> `i_dataFNoc_51 [50:0]`, `o_drv2Noc` -> `o_data2Noc_51 [50:0]`。
- 输出/影响：`o_drv2Noc`。
- 结构复杂度：branch=0，join=0，blocking=3。
- AI 推断：最终手册应重点描述事件从i_drvFNoc到o_drv2Noc的串行传播路径，以及FIFO和延迟链的角色，同时说明数据载荷的拼接关系。


## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| `cfifo1` | `cFifo1` | `w_drv2fifo1` | `w_drv2delay16` |
| `cfifo2` | `cFifo3_I2C` | `w_drv2fifo2` | `w_drv2Noc1` |
| `cfifo3_0` | `cFifo3_I2C_1` | `i_drvFNoc` | `w_drv2delay1` |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_1` | control_path | `o_free2Noc` | w_freeFfifo2 | 证据不足：No Semantic Layer assignment interpretation is available. |
| `assign_2` | data_path | `o_data2Noc_51` | {r_dataFNoc[50],r_dataFNoc[49:42],r_middle_24,RDATA,r_last_10} | AI 推断：该赋值将多个内部数据片段拼接成最终的51位输出数据，这些片段包括来自I2C控制器（U1）的读取数据（RDATA）和经过延迟/处理的数据。 |
| `assign_0` | unknown | `RESETN` | rst | 证据不足：No Semantic Layer assignment interpretation is available. |
