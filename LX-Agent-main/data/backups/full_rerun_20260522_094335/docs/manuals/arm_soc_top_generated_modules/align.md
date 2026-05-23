# 模块 `align`

- 源文件：`rtl/rtl/Execute/align.v`。
- 职责：AI 推断：该模块负责将输入的32位操作数地址对齐到4字节边界，并输出对齐后的结果。。
- 说明：模块接收一个32位操作数地址，通过加4操作生成临时值，然后将该临时值的低2位清零，实现4字节对齐。输出结果用于后续的地址访问。

## 1. 层级位置

- Parents：`execute`。
- Children：无。
- Component children：无。
- Upstream modules：无。
- Downstream modules：无。

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入：`oprand`。
- 输出：数据输出：`result`。

### 2.1 端口分组

| 端口组 | 方向统计 | 代表信号 |
| --- | --- | --- |
| `other_ports` | input:1, output:1 | `oprand`, `result` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `data_inputs` | input | - | `oprand [31:0]` | 未记录 |
| `data_outputs` | output | - | `result [31:0]` | 未记录 |

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
| `assign_1` | data_path | `result` | {oprandTmp[31:2],{2{1'b0}}} | AI 推断：该赋值将输入操作数加4，生成一个临时地址偏移值。 |
| `assign_0` | unknown | `oprandTmp` | oprand + 4 | AI 推断：该赋值将临时地址的低2位清零，实现4字节对齐。 |
