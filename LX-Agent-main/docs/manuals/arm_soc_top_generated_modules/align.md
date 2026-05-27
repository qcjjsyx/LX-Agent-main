# 模块 `align`

- 源文件：`rtl\rtl\Execute\align.v`
- 职责：AI 推断：地址预对齐单元，将输入操作数递增4并对齐到4字节边界，生成下一个顺序对齐地址。
- 说明：接口仅包含数据输入 `oprand` 和数据输出 `result`，无事件或控制信号，内部无子模块实例，符合纯组合数据通路特征。电路逻辑：`assign oprandTmp = oprand + 4` 计算递增后的地址；`assign result = {oprandTmp[31:2], {2{1'b0}}}` 将低2位强制清零，实现4字节对齐。该模块常用于流水线中计算下一顺序取指或数据访问地址（例如分支目标或顺序程序计数器更新后执行对齐），保证地址满足字对准要求。

## 1. 层级位置

- Parents：`execute`
- Children：无
- Component children：无
- Upstream modules：无
- Downstream modules：无

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：数据输入 `oprand`
- 输出：数据输出 `result`

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
| `assign_1` | data_path | `result` | {oprandTmp[31:2],{2{1'b0}}} | AI 推断：中间连线 oprandTmp 计算 oprand+4，为后续对齐操作提供加数结果。 |
| `assign_0` | unknown | `oprandTmp` | oprand + 4 | AI 推断：中间连线 oprandTmp 计算 oprand+4，为后续对齐操作提供加数结果。 |
