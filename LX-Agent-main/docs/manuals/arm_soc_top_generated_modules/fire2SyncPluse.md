# 模块 `fire2SyncPluse`

- 源文件：`rtl\rtl\IONet\GPIO\fire2SyncPluse.v`
- 职责：**AI 推断**：一个将输入信号电平变化转换为同步脉冲输出的边沿检测模块。
- 说明：模块名中的 “SyncPluse” 暗示同步脉冲产生功能；唯一赋值 `rise = pluse_level_t ^ pluse_level_tt` 通过异或实现边沿检测：当两个连续电平不同时输出高脉冲，符合同步脉冲生成器的典型行为。

## 1. 层级位置

- Parents：`SPI02NoC`、`perip_slot`、`perip_slot_timer`
- Children：无
- Component children：无
- 上游模块：无
- 下游模块：无

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 输入信号：`clk`、`fire`、`rst_finish`
- 输出信号：`rise`

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `clock_reset_init` | input: 2 | `clk`, `rst_finish` |
| `other_ports` | input: 1, output: 1 | `fire`, `rise` |

## 3. Drive/Data/Free 契约

Manual Context 未提供本模块的接口分组，该表无有效内容。

## 4. 主要 Drive‑centered Flow

- **证据不足**：Manual Context 未提供本模块的 drive flow。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

Manual Context 未记录 primary internal component，该表无有效内容。

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
| --- | --- | --- | --- | --- |
| `assign_0` | unknown | `rise` | `pluse_level_t ^ pluse_level_tt` | **AI 推断**：该赋值产生电平变化指示信号。 |
