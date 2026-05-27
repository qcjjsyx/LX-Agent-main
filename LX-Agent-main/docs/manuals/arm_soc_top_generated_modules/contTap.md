# 模块 `contTap`

- 源文件：`rtl\rtl\Control\base\contTap.v`
- 职责（**AI 推断**）：无法从紧凑型 AI 上下文中推断模块结构角色，推断的信号列表全部为空。
- 说明：当前 AI 上下文中，事件、数据、自由、控制类输入/输出计数均为零；推断仅存在一个复位端口 `rst`。内部事件流、组件连接、赋值依赖及关键实例信息全部缺失，无法形成任何设计意图假设。

## 1. 层级位置

- Parents：`cpu_top_all`, `execute`, `intAndExc`, `lsu`, `socmem`
- Children：无
- Component children：无
- Upstream modules：无
- Downstream modules：无

### 1.1 本模块结构图

Manual Context 未记录本模块的内部实例或子模块结构。

## 2. 输入/输出接口摘要

- 接收：其他输入 `trig`
- 输出：其他输出 `req`

### 2.1 端口分组

| 端口组       | 方向统计        | 代表信号       |
|--------------|-----------------|----------------|
| `other_ports`| input:1, output:1 | `trig`, `req` |

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
|-----------|------|-------|---------|-------------------|
| -         | -    | -     | -       | Manual Context 未提供接口分组 |

## 4. 主要 Drive-centered Flow

- 证据不足：Manual Context 未提供本模块的 drive flow。

## 5. 内部组件与 assign 影响

### 5.1 内部组件

| 实例 | 类型 | 输入事件 | 输出事件 |
|------|------|----------|----------|
| -    | -    | -        | Manual Context 未提供 primary internal component |

### 5.2 assign 影响

| Assign | Impact area | LHS | RHS 摘要 | 解释状态 |
|--------|-------------|-----|----------|----------|
| -      | -           | -   | -        | Manual Context 未提供 primary assign 影响 |
