# 模块 `subtr4b`

- 源文件：`rtl\rtl\IONet\IONetwork_9.24\subtr4b.v`。
- 职责：AI 推断：4位二进制减法器，计算 a - b 并输出差值 differ 和内部借位链。
- 说明：模块通过异或门计算逐位差，并通过组合逻辑链生成借位信号，最终输出差值。无时钟或复位，纯组合逻辑。

## 1. 层级位置

- Parents：`routeMsg`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`a`, `b`。
- 输出：数据输出：`differ`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `other_ports` | input:2, output:1 | `a`, `b`, `differ` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `a [3:0]`, `b [3:0]` | 未记录 |
| `data_outputs` | output | - | `differ [3:0]` | 未记录 |

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
| `assign_1` | unknown | `w_pSub_4[1]` | a[1]^b[1] | AI 推断：生成 a 与 b 的逐位异或结果，作为减法中间差 |
| `assign_2` | unknown | `w_pSub_4[2]` | a[2]^b[2] | AI 推断：生成 a 与 b 的逐位异或结果，作为减法中间差 |
| `assign_3` | unknown | `w_pSub_4[3]` | a[3]^b[3] | AI 推断：生成 a 与 b 的逐位异或结果，作为减法中间差 |
| `assign_4` | unknown | `w_borrow_5[1]` | (w_pSub_4[0]&b[0])\|(~w_pSub_4[0]&BORROW0) | AI 推断：实现借位传播链，从低位向高位传递借位条件 |
| `assign_5` | unknown | `w_borrow_5[2]` | (w_pSub_4[1]&b[1])\|(~w_pSub_4[1]&w_borrow_5[1]) | AI 推断：实现借位传播链，从低位向高位传递借位条件 |
| `assign_6` | unknown | `w_borrow_5[3]` | (w_pSub_4[2]&b[2])\|(~w_pSub_4[2]&w_borrow_5[2]) | AI 推断：实现借位传播链，从低位向高位传递借位条件 |
| ... | ... | ... | ... | 其余 5 条 assign 省略 |
