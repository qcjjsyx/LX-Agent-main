# 模块 `SPI02NoC`

- 源文件：`rtl\rtl\IONet\SPI\SPI0\SPI02NoC.v`。
- 职责：AI 推断：fire2SyncPluse_u 将 startRead_fire 同步转换为 startRead 脉冲。。
- 说明：根据切片7（第170-176行），实例化 fire2SyncPluse 模块，连接 .fire(startRead_fire)、.clk(clk)、.rst(rst)、.rst_finish(rst_finish)、.rise(startRead)。输入 startRead_fire 经同步后输出 startRead 上升沿脉冲。

## 1. 层级位置

- Parents：`IONet_slot`。
- Children：`fire2SyncPluse`, `flash_state`。
- Component children：`cFifo1`。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

```mermaid
flowchart TB
  SPI02NoC["SPI02NoC"] -->|instance| cFifo1_cFifo1["cFifo1: cFifo1"]
  SPI02NoC["SPI02NoC"] -->|instance| cFifo2_cFifo1["cFifo2: cFifo1"]
  SPI02NoC["SPI02NoC"] --> fire2SyncPluse["fire2SyncPluse"]
  SPI02NoC["SPI02NoC"] --> flash_state["flash_state"]
  SPI02NoC["SPI02NoC"] -->|component| cFifo1["cFifo1"]
```

```text
SPI02NoC
|-- cFifo1: cFifo1
|-- cFifo2: cFifo1
|-- fire2SyncPluse
|-- flash_state
`-- cFifo1
```

## 2. 输入/输出接口摘要

- 接收：drive 输入：`i_driveFrmMesh`；数据输入：`i_dataFrmNoc`；free 输入：`i_freeNextFrmMesh`；其他输入：`clk`, `miso`, `rst_finish`。
- 输出：drive 输出：`o_driveNextToMesh`；数据输出：`address`, `o_data2Noc`；free 输出：`o_freeToMesh`；其他输出：`busy`, `cs_n`, `mosi`, `sclk`, `... +1`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:2, output:1 | `clk`, `rst_finish`, `sclk` |
| `drive_event` | input:1, output:1 | `i_driveFrmMesh`, `o_driveNextToMesh` |
| `free_backpressure` | input:1, output:1 | `i_freeNextFrmMesh`, `o_freeToMesh` |
| `other_ports` | input:2, output:6 | `i_dataFrmNoc`, `address`, `o_data2Noc`, `miso`, `busy`, `cs_n`, `mosi`, `startRead` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `i_driveFrmMesh` | input | `i_driveFrmMesh` | `i_dataFrmNoc [50:0]` | `o_freeToMesh` |
| `o_driveNextToMesh` | output | `o_driveNextToMesh` | 未记录 | `i_freeNextFrmMesh` |

## 4. 主要 Drive-centered Flow

### `i_driveFrmMesh`

- 确定性事实：`i_driveFrmMesh to o_driveNextToMesh`；flow_id=`flow_000_SPI02NoC_i_driveFrmMesh`。
- Payload：`i_driveFrmMesh` -> `i_dataFrmNoc [50:0]`。
- 输出/影响：`o_driveNextToMesh`。
- 结构复杂度：branch=0，join=0，blocking=2。
- AI 推断：输入事件i_driveFrmMesh携带一个51位的数据负载i_dataFrmNoc，其中包含地址字段。


## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| `cFifo1` | `cFifo1` | `i_driveFrmMesh` | `w_driveNext` |
| `cFifo2` | `cFifo1` | `w_driveNext_delay` | `o_driveNextToMesh` |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_1` | data_path | `w_SR` | {dataReady,w_TXE,busy,w_finish,4'b0} | AI 推断：组合 SPI 状态寄存器，包含数据就绪、发送空、忙和完成标志。 |
| `assign_2` | data_path | `w_data2noc` | (address[3:0] == CR) ? {24'b0,r_CR} : (address[3:0] == SR) ? {24'b0,w_SR} : (address[3:0] == ... | AI 推断：组合 SPI 状态寄存器，包含数据就绪、发送空、忙和完成标志。 |
| `assign_5` | unknown | `startRead_fire` | ((address[3:0] == TDR) & w_en) ? w_fire_2[1] : 1'b0 | AI 推断：当向 TDR 寄存器写入数据时，产生启动 Flash 读操作的触发信号。 |
| `assign_6` | unknown | `w_en_tmp` | w_en & (address == 8'h64) | AI 推断：当地址为 8'h64 且写使能有效时，产生一个临时写使能信号。 |
| `assign_0` | data_path | `address` | i_dataFrmNoc[49:42] | AI 推断：从 NoC 输入数据包中提取地址字段，用于后续的寄存器选择和命令解析。 |
