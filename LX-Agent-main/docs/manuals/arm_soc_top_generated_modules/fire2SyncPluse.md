# 模块 `fire2SyncPluse`

- 源文件：`rtl/rtl/IONet/GPIO/fire2SyncPluse.v`。
- 职责：AI 推断：边沿检测同步器，将输入脉冲信号同步到本地时钟域并检测上升沿。
- 说明：模块名“SyncPluse”暗示同步脉冲功能，assign依赖中通过两级寄存器（pluse_level_t, pluse_level_tt）实现同步，再通过异或运算检测上升沿（rise），表明这是一个跨时钟域脉冲同步与边沿检测单元

## 1. 层级位置

- Parents：`SPI02NoC`, `perip_slot`, `perip_slot_timer`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：其他输入：`clk`, `fire`, `rst_finish`。
- 输出：其他输出：`rise`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input:2 | `clk`, `rst_finish` |
| `other_ports` | input:1, output:1 | `fire`, `rise` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| - | - | - | - | Manual Context 未提供接口分组 |

## 4. 主要 Drive-centered Flow

- 证据不足：Manual Context 未提供本模块 drive flow。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
| --- | --- | --- | --- |
| - | - | - | Manual Context 未提供 primary internal component |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_0` | unknown | `rise` | pluse_level_t ^ pluse_level_tt | AI 推断：通过两级同步后的信号异或运算，生成输入脉冲的上升沿指示 |
