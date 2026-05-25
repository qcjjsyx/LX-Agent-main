# 模块 `I2C2NoC`

- 源文件：`rtl/rtl/IONet/IIC/I2C2NoC.v`。
- 职责：AI 推断：验证了模块将输入数据拆解并重组输出数据，其中插入I2C读数据（RDATA）。。
- 说明：切片2行73-74声明了r_middle_24和r_last_10寄存器；切片5行118表明r_dataFNoc锁存i_dataFNoc_51全51位；切片7行204-207表明r_mode0有效时，RD（读/写指示）取自r_dataFNoc[50]，ADDRESS取自[44:42]，WDATA取自[17:10]；切片8行228表明RDATA在w_firefifo1触发时更新为w_rdata；切片9行236将输出拼接为{r_dataFNoc[50], [49:42], r_middle_24, RDATA, r_last_10}。该拼接直接对应claim描述的结构。

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
- AI 推断：最终手册应重点描述该流作为纯事件驱动路径的结构，强调FIFO的选通作用和延迟链的累积延迟。


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
| `assign_2` | data_path | `o_data2Noc_51` | {r_dataFNoc[50],r_dataFNoc[49:42],r_middle_24,RDATA,r_last_10} | AI 推断：该赋值是模块的核心数据路径操作，将I2C读取的数据（RDATA）整合到NoC输出数据包中。 |
| `assign_0` | unknown | `RESETN` | rst | 证据不足：No Semantic Layer assignment interpretation is available. |
