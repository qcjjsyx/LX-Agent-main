# arm_soc_top 技术手册 (新读者指南)

## 1. System Overview

**证据来源**: `system:arm_soc_top`

本手册描述的顶层模块为 `arm_soc_top`。根据系统视图，该模块覆盖了 **105** 个可达子模块和 **149** 个结构子。系统总览的总体可信度为 **medium**。

- **直接子模块**: 顶层模块下有三个主要的一级子模块。
    - `IONet_slot`
    - `async2sync`
    - `cpu_slot`

- **所使用的结构协议族 (Families)**: 系统内部使用了多种结构子协议，包括 `ArbMerge`, `Fifo1`, `MutexMerge`, `PmtFifo1`, `SelSplit`, `WaitMerge`, `eventSource`。这些通用协议的细节将在后续章节展开。

- **外部依赖**: 系统依赖于多个外部 IP，这些依赖的当前状态为 **仅接口边界 (interface_only)**，意味着其内部实现细节在现有证据中不可见。
    - `BUFM2HM`
    - `CKMUX2M4HM`
    - `DFQRM2HM`
    - `INVM0HM`
    - `IUMB`
    - `SHKB110_1024X8X8CM8`
    - `SHKB110_4096X8X8CM8`

- **全局风险**:
    - 所有上述 7 个外部依赖项目前都只有接口边界定义，缺乏内部行为细节，这构成了设计理解上的主要风险。

## 2. Top Module

**证据来源**: `module:arm_soc_top`

- **模块名称**: `arm_soc_top`
- **结构摘要**: 该模块直接包含 **3** 个子模块和 **0** 个结构子。
- **可信度**: medium

该模块作为一个容器，将三个一级子模块 `IONet_slot`、`async2sync` 和 `cpu_slot` 封装在一起。证据中未提供该模块自己的接口、寄存器或内部 FSM 信息。

## 3. Primary Modules

**证据来源**: `module:IONet_slot`, `module:async2sync`, `module:cpu_slot`

本节描述 `arm_soc_top` 的三个直接子模块。

### 3.1. IONet_slot
- **结构摘要**: 该模块直接包含 **12** 个子模块和 **0** 个结构子。
- **风险与警告**:
    - **证据不足**: 该模块的直接子对象较多，建议按层级拆分理解。当前证据未提供其内部结构细节。
    - **证据不足**: 对于其名称暗示的 IONet 网络功能，当前证据未提供拓扑、路由规则或仲裁机制的描述。

### 3.2. async2sync
- **结构摘要**: 该模块直接包含 **0** 个子模块和 **0** 个结构子。
- **风险与警告**:
    - **证据不足**: 该模块是用于异步转同步的。当前证据未提供其跨时钟域处理的具体实现细节（如握手协议、同步器级数等）。

### 3.3. cpu_slot
- **结构摘要**: 该模块直接包含 **3** 个子模块和 **4** 个结构子。
- **风险与警告**:
    - **证据不足**: 该模块同时包含多类结构子角色，阅读时需要区分主路径与返回路径。
    - **证据不足**: 其直接子对象较多，建议按层级拆分理解。

## 4. Component Protocols

**证据来源**: 以下是 `contract:cFifo1` 等 12 个组件协议的证据。

本节列出了 `arm_soc_top` 系统中使用的核心结构子 (Component) 协议。每个协议都用一个概括性的摘要表示。

| 组件协议 (Contract Name) | 所属结构族 (Family) | 证据摘要 |
| :--- | :--- | :--- |
| `cFifo1` | `Fifo1` | 一个被 18 个不同父模块引用的通用单深度 FIFO 协议。 |
| `cFifo1_107b_lsu` | `Fifo1` | 一个 107 位宽的单深度 FIFO 协议，与 LSU 相关。 |
| `cPmtFifo1` | `PmtFifo1` | 一个被 4 个父模块引用的单深度 FIFO 协议，性质与 `Fifo1` 类似但族名不同。 |
| `cCondFork5` | `SelSplit` | 一个条件分支 (SelSplit) 协议。 |
| `cSelector11_68b_exe` | `SelSplit` | 一个选择器分支组件，与执行阶段相关。 |
| `cMutexMerge10_64b_exe` | `MutexMerge` | 一个 10 输入 64 位的互斥合并器。 |
| `cMutexMerge2_104b_lsu` | `MutexMerge` | 一个 2 输入 104 位的互斥合并器，与 LSU 相关。 |
| `cWaitMerge2_128b_exe` | `WaitMerge` | 一个 2 输入 128 位的等待合并器。 |
| `cWaitMerge2_163b_exe` | `WaitMerge` | 一个 2 输入 163 位的等待合并器。 |
| `cArbMerge2_105b_cpu` | `ArbMerge` | 一个 2 输入 105 位的仲裁合并器，被 2 个父模块引用。 |
| `cArbMerge5_51b` | `ArbMerge` | 一个 5 输入 51 位的仲裁合并器。 |
| `eventSource` | `eventSource` | 一个事件源协议。 |

- **风险与警告**:
    - 多个组件（如 `cFifo1`、`cPmtFifo1`、`cArbMerge2_105b_cpu`）被多个父模块引用，意味着它们被实例化多次。当前证据未提供这些实例的具体连接细节。

## 5. Representative Event Flows

**证据来源**: 本节覆盖了 12 个 `flow_path`。

这一部分展示系统内部有代表性的局部事件流。每个流都从一个输入信号 (`i_...`) 开始，并跟踪事件在模块内部的处理路径。

> **注意**: 以下所有 flow 的可信度均为 **medium**。每个 flow 都涉及具体的 payload 信号，但当前证据明确标注这些 payload 候选信号是**模糊的 (ambiguous)**。因此，手册只能记录这些信号的存在，而无法确认其确切含义。

### 5.1. cpu_top_all 模块内的流
- **`cpu_top_all:i_dataRoutDriveToLsu_1`**: 一个从 `i_dataRoutDriveToLsu_1` 出发的局部事件流。
    - **模糊 Payload 候选**: `i_IntSig`, `i_inst_65`, `i_memData_65`, `i_startPc_32`
- **`cpu_top_all:i_drvFICache`**: 一个从 `i_drvFICache` 出发的局部事件流。
    - **模糊 Payload 候选**: `i_IntSig`, `i_inst_65`, `i_memData_65`, `i_startPc_32`
- **`cpu_top_all:i_driveFromStart_1`**: 一个从 `i_driveFromStart_1` 出发的局部事件流。
    - **模糊 Payload 候选**: `i_IntSig`, `i_inst_65`, `i_memData_65`, `i_startPc_32`

### 5.2. launch 模块内的流
- **`launch:i_decoderDriveToLaunch_1`**: 从 `i_decoderDriveToLaunch_1` 出发的局部事件流。
    - **模糊 Payload 候选**: `i_ExeData_96`, `i_blImm9_9`, `i_decoderData_185`, ... (共 11 个候选)
- **`launch:i_ExeDriveToLunch_1`**: 从 `i_ExeDriveToLunch_1` 出发的局部事件流。
    - **模糊 Payload 候选**: 同上 (共 11 个候选)
- **`launch:i_GrfDriveToLaunch_1`**: 从 `i_GrfDriveToLaunch_1` 出发的局部事件流。
    - **模糊 Payload 候选**: 同上 (共 11 个候选)
- **`launch:i_SrfDriveToLaunch_1`**: 从 `i_SrfDriveToLaunch_1` 出发的局部事件流。
    - **模糊 Payload 候选**: 同上 (共 11 个候选)
- **`launch:i_LsuDriveToLunch_1`**: 从 `i_LsuDriveToLunch_1` 出发的局部事件流。
    - **模糊 Payload 候选**: 同上 (共 11 个候选)

### 5.3. fetch 模块内的流
- **`fetch:i_drvFdispatch`**: 从 `i_drvFdispatch` 出发的局部事件流。
    - **模糊 Payload 候选**: `i_inst_64`, `i_interrupt`, ... (共 5 个候选)
- **`fetch:i_drvFICache`**: 从 `i_drvFICache` 出发的局部事件流。
    - **模糊 Payload 候选**: `i_inst_64`, `i_interrupt`, ... (共 5 个候选)

### 5.4. intAndExc 模块内的流
- **`intAndExc:i_driveFromDR_1`**: 从 `i_driveFromDR_1` 出发的局部事件流。
    - **模糊 Payload 候选**: `i_DRdata_64`, `i_decPCAndNum_36`, ... (共 8 个候选)
- **`intAndExc:i_driveFromRGRF_1`**: 从 `i_driveFromRGRF_1` 出发的局部事件流。
    - **模糊 Payload 候选**: 同上 (共 8 个候选)

## 6. Partial Or Deferred Event Flows

**证据来源**: 本节覆盖了 12 个 `flow_path`。

这一部分的事件流目前属于**低置信度 (low confidence)** 路径。这些路径及其相关内容在当前 Manual IR 中**无法**追踪到完整的模块输出事件。

- **风险与警告**:
    - 以下每个 flow 均被标注为 **"no module output event drive reached from start signal"**。
    - 以下每个 flow 的可信度均为 **low**。
    - 所有相关 FlowPath 的 payload 候选信号同样是**模糊的**。

| Flow Path | 所属模块 | 模糊 Payload 候选 (示例) |
| :--- | :--- | :--- |
| `decoder:i_driveFromIF` | decoder | `i_is16_1`, `i_isInInt`, `i_pcAndIns_64` |
| `decoder_16:i_drive` | decoder_16 | `i_data_64`, `i_isInInt` |
| `launch:i_PSRDriveToLaunch_1` | launch | `i_ExeData_96`, `i_decoderData_185`, ... |
| `launch:i_driveFExcToIf_1` | launch | `i_ExeData_96`, `i_decoderData_185`, ... |
| `execute:i_LsuDriveToExe_1` | execute | `i_grfToExecuteData_64`, `i_launchDataToExe_207`, ... |
| `execute:i_grfDriveToExecute_1` | execute | (同 `i_LsuDriveToExe_1`) |
| `execute:i_launchDriveToExecute_1` | execute | (同 `i_LsuDriveToExe_1`) |
| `execute:i_launchDrive_1` | execute | (同 `i_LsuDriveToExe_1`) |
| `inStack:i_driveFromRGRF_1` | inStack | `i_DRSeleDriToinStackSele_1`, `i_grfData_192`, ... |
| `inStack:i_driveFromRPSR_1` | inStack | (同 `i_driveFromRGRF_1`) |
| `grf:i_grfwDriveFromExp_1` | grf | `i_expAddr_8`, `i_expDataToGrf_64`, ... |
| `grf:i_grfwDriveFromLsu_1` | grf | (同 `i_grfwDriveFromExp_1`) |

## 7. 证据边界与风险点

**证据来源**: `context_pack.evidence_boundary`, `system_view.global_risks`

### 7.1. 证据使用规则
本手册完全基于提供的 JSON 证据摘要撰写。
- **禁止推断**: 除非证据来源 (Manual IR) 明确包含，否则不得推断任何 RTL 进程、状态机、寄存器行为或工程结构。
- **保留警告**: 所有低置信度 (low confidence) 的 FlowPath 和警告信息都被如实保留，而不是通过猜测来补全。
- **Payload 模糊性**: 手册中提及的几乎所有 `channel` 的 payload 候选信号都是模糊的。这意味着现有证据无法确定这些通道上具体传输的是哪些信号，仅能记录所有可能的候选信号。

### 7.2. 主要风险总结
1.  **外部依赖不完整**: 7 个外部依赖 (BUFM2HM, CKMUX2M4HM, DFQRM2HM, INVM0HM, IUMB, SHKB110 系列) 仅有接口定义。
2.  **大量低置信度路径**: 12 个 FlowPath 被标注为低置信度，并且无法追踪到模块的输出，表明这些事件流的关键逻辑链条在当前分析下是断裂的。
3.  **大量模糊 Payload**: 几乎所有列出的 ChannelCard 都包含模糊的 payload 候选信号，这使得准确理解数据路径和协议交互变得困难。
4.  **组件复用导致歧义**: 如 `cFifo1`、`cPmtFifo1` 等核心组件被多个父模块引用，但没有说明不同实例之间的配置和连接差异。
5.  **延迟辅助单元 (transparent_delay)**: 在 FlowPath 中出现的 `transparent_delay` 表示 parser 保留了 delay helper 的透传事实，但 delay 不作为正式 component 展开，因此其具体实现是未知的。
6.  **模块复杂度**: 多个模块 (`cpu_slot`, `cpu_top_all`, `fetch`, `decoder`, `execute` 等) 被指出子对象多或角色复杂，增加了理解上的难度。
