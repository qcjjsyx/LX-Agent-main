# arm_soc_top RTL 代码手册

本手册由 `manual_context` 结构化证据渲染生成。确定性事实、派生事实、AI 推断和证据缺口按字段原样分级，手册不补写 Manual Context 中没有的连接、接口、flow、时序保证、always/FSM 行为或寄存器更新语义。

## 1. 项目总览

### 1.1 Manual Context 范围

- 确定性事实：`top_module` 为 `arm_soc_top`；源文件为 `rtl/rtl/SoC/arm_soc_top.v`；证据：`ev:project:top_module`。
- 确定性事实：顶层直接实例化模块为 `IONet_slot`, `async2sync`, `cpu_slot`；证据：`ev:project:top_level`。
- Manual Context 对象数量：modules=106，interfaces=499，flows=103，evidence_entries=952，validation_issues=0。
- Validation：`passed` / issues=0 / checked_files=427。

### 1.2 文档焦点

- 派生事实：主要事件信号为 `drive`；次要事件记录为 `free`。
- 派生事实：主要写作主题为 `module_responsibility`, `interface_data_contract`, `internal_drive_flow`, `cross_module_data_event_flow`。
- 写作策略：`free` 信号只作为 backpressure/drive availability 相关参考出现，不作为主流程解释入口。

### 1.3 系统语义摘要

- AI 推断（confidence=medium, review_status=needs_review, requires_rtl_source_review=true）：Emphasize the bidirectional event-driven drive protocol between the CPU slot and I/O network slot, and the role of initMode_pad.
  - 说明：The module has no data or event ports at the top level, so the manual should focus on the internal drive flow (w_driveFrmCPU, w_driveToCPU) and how initMode_pad conditions it. The gpio_data_o from io_slot may be relevant if it connects to top-level pads, but this is not shown in the context.
  - 证据：`ev:arm_soc_top:semantic_module`

## 2. 顶层模块 `arm_soc_top`

### 2.1 结构边界

- 确定性事实：`arm_soc_top` 的直接子模块为 `IONet_slot`, `async2sync`, `cpu_slot`。
- 确定性事实：module_context 中记录的 children 为 `IONet_slot`, `async2sync`, `cpu_slot`。
- 确定性事实：component_children 为 无。
- 确定性事实：接口计数为 `{"event_input_count": 0, "event_output_count": 0, "data_input_count": 0, "data_output_count": 0, "free_input_count": 0, "free_output_count": 0}`。

### 2.2 语义职责

- AI 推断（confidence=medium, review_status=needs_review, requires_rtl_source_review=true）：Top-level SoC integration module that connects a CPU core to an I/O network slot via a bidirectional event-driven drive interface.
  - review_status：`needs_review`；证据：`ev:arm_soc_top:semantic_module`。

### 2.3 关键实例

下表来自 `module_context.internal_components` 的 primary 样本；它不是直接子模块完整清单，完整清单以上方 children 为准。

| 实例 | 模块类型 | 输入事件 | 输出事件 | 证据 |
| --- | --- | --- | --- | --- |
| `io_slot` | `IONet_slot` | `w_driveFrmCPU` | `w_driveToCPU` | `ev:arm_soc_top:key_instances` |
| `u_cpu` | `cpu_slot` | `w_driveToCPU` | `w_driveFrmCPU` | `ev:arm_soc_top:key_instances` |

## 3. 模块层级结构

- 确定性事实：system_topology 记录 module_count=106。

### 3.1 顶层直接层级

| Parent | Child | Relationship | Certainty | Evidence |
| --- | --- | --- | --- | --- |
| `arm_soc_top` | `IONet_slot` | instantiates | deterministic_fact | `ev:arm_soc_top:parser_module` |
| `arm_soc_top` | `async2sync` | instantiates | deterministic_fact | `ev:arm_soc_top:parser_module` |
| `arm_soc_top` | `cpu_slot` | instantiates | deterministic_fact | `ev:arm_soc_top:parser_module` |

### 3.2 层级样本

| Parent | Child | Relationship | Certainty | Evidence |
| --- | --- | --- | --- | --- |
| `I2C2NoC` | `mi2cv2` | instantiates | deterministic_fact | `ev:I2C2NoC:parser_module` |
| `IONet_slot` | `CPU2NoC` | instantiates | deterministic_fact | `ev:IONet_slot:parser_module` |
| `IONet_slot` | `I2C2NoC` | instantiates | deterministic_fact | `ev:IONet_slot:parser_module` |
| `IONet_slot` | `IONetwork` | instantiates | deterministic_fact | `ev:IONet_slot:parser_module` |
| `IONet_slot` | `NoCUART0` | instantiates | deterministic_fact | `ev:IONet_slot:parser_module` |
| `IONet_slot` | `NoCUART1` | instantiates | deterministic_fact | `ev:IONet_slot:parser_module` |
| `IONet_slot` | `SPI02NoC` | instantiates | deterministic_fact | `ev:IONet_slot:parser_module` |
| `IONet_slot` | `SPI2NoC` | instantiates | deterministic_fact | `ev:IONet_slot:parser_module` |
| `IONet_slot` | `gpio_slot` | instantiates | deterministic_fact | `ev:IONet_slot:parser_module` |
| `IONet_slot` | `pwm0_top` | instantiates | deterministic_fact | `ev:IONet_slot:parser_module` |
| `IONet_slot` | `pwm1_top` | instantiates | deterministic_fact | `ev:IONet_slot:parser_module` |
| `IONet_slot` | `timer_slot` | instantiates | deterministic_fact | `ev:IONet_slot:parser_module` |
| `IONet_slot` | `wd2noc` | instantiates | deterministic_fact | `ev:IONet_slot:parser_module` |
| `IONetwork` | `nodeTop` | instantiates | deterministic_fact | `ev:IONetwork:parser_module` |
| `NoCUART0` | `m16550s` | instantiates | deterministic_fact | `ev:NoCUART0:parser_module` |
| `NoCUART1` | `m16550s` | instantiates | deterministic_fact | `ev:NoCUART1:parser_module` |
| `SPI02NoC` | `fire2SyncPluse` | instantiates | deterministic_fact | `ev:SPI02NoC:parser_module` |
| `SPI02NoC` | `flash_state` | instantiates | deterministic_fact | `ev:SPI02NoC:parser_module` |
| `SPI2NoC` | `SPI_control` | instantiates | deterministic_fact | `ev:SPI2NoC:parser_module` |
| `SPI_control` | `CRC_rx` | instantiates | deterministic_fact | `ev:SPI_control:parser_module` |
| `SPI_control` | `CRC_tx` | instantiates | deterministic_fact | `ev:SPI_control:parser_module` |
| `SPI_control` | `clk_div` | instantiates | deterministic_fact | `ev:SPI_control:parser_module` |
| `SPI_control` | `reg_apb` | instantiates | deterministic_fact | `ev:SPI_control:parser_module` |
| `SPI_control` | `spi_m` | instantiates | deterministic_fact | `ev:SPI_control:parser_module` |
| `SPI_control` | `spi_s` | instantiates | deterministic_fact | `ev:SPI_control:parser_module` |
| `SPI_control` | `state0` | instantiates | deterministic_fact | `ev:SPI_control:parser_module` |
| `adder` | `adder32` | instantiates | deterministic_fact | `ev:adder:parser_module` |
| `adder` | `adder5` | instantiates | deterministic_fact | `ev:adder:parser_module` |
| `adder` | `adder64` | instantiates | deterministic_fact | `ev:adder:parser_module` |
| `arm_soc_top` | `IONet_slot` | instantiates | deterministic_fact | `ev:arm_soc_top:parser_module` |

## 4. 关键模块职责

### 4.1 主要模块摘要

以下摘要来自 `project_context.major_modules`。凡 `certainty=ai_inferred` 的内容均按 AI 推断写入，不升级为确定性事实。

| 模块 | 区域 | 重要性 | Certainty | 摘要 | Evidence |
| --- | --- | --- | --- | --- | --- |
| `IONetwork` | noc | 35 | AI 推断 | 2x2 mesh network-on-chip (NoC) router connecting four nodeTop instances in a grid topology. | `ev:IONetwork:semantic_module` |
| `cpu_top_all` | cpu | 26 | AI 推断 | Central pipeline orchestration module that sequences instruction fetch, decode, execute, LSU, and writeback through a drive-event-based control network. | `ev:cpu_top_all:semantic_module` |
| `execute` | execution_pipeline | 26 | AI 推断 | Central execution unit that decodes launch instructions, dispatches to ALU/div/mul/shift/bitwise datapaths, and routes results to LSU, GRF, exception, and launch feedback. | `ev:execute:semantic_module` |
| `grf` | cpu | 22 | AI 推断 | Register file module providing operand read ports and write arbitration for a multi-pipeline processor. | `ev:grf:semantic_module` |
| `lsu` | cpu | 19 | AI 推断 | Central load/store execution unit that arbitrates and routes memory access requests between the execution pipeline, register file, data cache, and memory interface. | `ev:lsu:semantic_module` |
| `IONet_slot` | noc | 18 | AI 推断 | Top-level peripheral interconnect slot that routes CPU-originated drive events and data to on-chip peripherals and returns peripheral drive events and data to the CPU. | `ev:IONet_slot:semantic_module` |
| `prf` | cpu | 18 | AI 推断 | Physical Register File (PRF) that stores architectural register values and PSR state, arbitrating between writeback, launch, and exception sources. | `ev:prf:semantic_module` |
| `launch` | cpu | 16 | AI 推断 | Central instruction launch and operand preparation module that decodes, merges, and routes instruction data and register operands to execution units based on drive events from multiple pipeline stages. | `ev:launch:semantic_module` |
| `socmem` | storage | 16 | AI 推断 | Central memory subsystem arbiter and pipeline controller for instruction and data access | `ev:socmem:semantic_module` |
| `wb` | cpu | 16 | AI 推断 | Write-back stage that demultiplexes LSU results and mutex-merged drive events into targeted register file and system register write paths. | `ev:wb:semantic_module` |
| `m16550s` | noc | 15 | AI 推断 | UART register file and bus interface bridge | `ev:m16550s:semantic_module` |
| `decoder` | cpu | 14 | AI 推断 | Instruction decode and dispatch unit that selects between 16-bit and 32-bit instruction decoders based on instruction type. | `ev:decoder:semantic_module` |
| `fetch` | cpu | 14 | AI 推断 | Central instruction fetch and event distribution hub that receives drive events from dispatch, top, and ICache, then routes them through a pipeline of fifos, merges, and splitters to produce decoded instruction, exception, interrupt, and ICache control events. | `ev:fetch:semantic_module` |
| `intAndExc` | cpu | 12 | AI 推断 | Central interrupt and exception arbitration and vectoring module that collects events from pipeline stages, selects the highest-priority exception or interrupt, and drives the resulting vector address and data to the appropriate register files and data route. | `ev:intAndExc:semantic_module` |
| `SPI_control` | noc | 11 | AI 推断 | APB-to-SPI bridge that translates APB register accesses into SPI master/slave control, clock generation, and interrupt aggregation. | `ev:SPI_control:semantic_module` |

### 4.2 已加载模块页面职责

| 模块 | 职责 claim | Review | Evidence |
| --- | --- | --- | --- |
| `arm_soc_top` | AI 推断（confidence=medium, review_status=needs_review, requires_rtl_source_review=true）：Top-level SoC integration module that connects a CPU core to an I/O network slot via a bidirectional event-driven drive interface. | needs_review | `ev:arm_soc_top:semantic_module` |
| `IONet_slot` | AI 推断（confidence=high, review_status=ready）：Top-level peripheral interconnect slot that routes CPU-originated drive events and data to on-chip peripherals and returns peripheral drive events and data to the CPU. | ready | `ev:IONet_slot:semantic_module` |
| `async2sync` | AI 推断（confidence=high, review_status=needs_review, requires_rtl_source_review=true）：This module synchronizes an asynchronous reset signal to a destination clock domain. | needs_review | `ev:async2sync:semantic_module` |
| `cpu_slot` | AI 推断（confidence=high, review_status=ready）：CPU slot module that routes data and events between the mesh network and a local CPU core with an integrated memory slot. | ready | `ev:cpu_slot:semantic_module` |
| `IONetwork` | AI 推断（confidence=high, review_status=ready）：2x2 mesh network-on-chip (NoC) router connecting four nodeTop instances in a grid topology. | ready | `ev:IONetwork:semantic_module` |
| `cpu_top_all` | AI 推断（confidence=high, review_status=ready）：Central pipeline orchestration module that sequences instruction fetch, decode, execute, LSU, and writeback through a drive-event-based control network. | ready | `ev:cpu_top_all:semantic_module` |
| `execute` | AI 推断（confidence=high, review_status=ready）：Central execution unit that decodes launch instructions, dispatches to ALU/div/mul/shift/bitwise datapaths, and routes results to LSU, GRF, exception, and launch feedback. | ready | `ev:execute:semantic_module` |
| `grf` | AI 推断（confidence=high, review_status=ready）：Register file module providing operand read ports and write arbitration for a multi-pipeline processor. | ready | `ev:grf:semantic_module` |
| `lsu` | AI 推断（confidence=high, review_status=ready）：Central load/store execution unit that arbitrates and routes memory access requests between the execution pipeline, register file, data cache, and memory interface. | ready | `ev:lsu:semantic_module` |
| `prf` | AI 推断（confidence=high, review_status=ready）：Physical Register File (PRF) that stores architectural register values and PSR state, arbitrating between writeback, launch, and exception sources. | ready | `ev:prf:semantic_module` |
| `launch` | AI 推断（confidence=high, review_status=ready）：Central instruction launch and operand preparation module that decodes, merges, and routes instruction data and register operands to execution units based on drive events from multiple pipeline stages. | ready | `ev:launch:semantic_module` |
| `socmem` | AI 推断（confidence=high, review_status=ready）：Central memory subsystem arbiter and pipeline controller for instruction and data access | ready | `ev:socmem:semantic_module` |
| `wb` | AI 推断（confidence=high, review_status=ready）：Write-back stage that demultiplexes LSU results and mutex-merged drive events into targeted register file and system register write paths. | ready | `ev:wb:semantic_module` |
| `m16550s` | AI 推断（confidence=medium, review_status=needs_review, requires_rtl_source_review=true）：UART register file and bus interface bridge | needs_review | `ev:m16550s:semantic_module` |
| `decoder` | AI 推断（confidence=medium, review_status=needs_review, requires_rtl_source_review=true）：Instruction decode and dispatch unit that selects between 16-bit and 32-bit instruction decoders based on instruction type. | needs_review | `ev:decoder:semantic_module` |
| `fetch` | AI 推断（confidence=high, review_status=ready）：Central instruction fetch and event distribution hub that receives drive events from dispatch, top, and ICache, then routes them through a pipeline of fifos, merges, and splitters to produce decoded instruction, exception, interrupt, and ICache control events. | ready | `ev:fetch:semantic_module` |
| `intAndExc` | AI 推断（confidence=high, review_status=ready）：Central interrupt and exception arbitration and vectoring module that collects events from pipeline stages, selects the highest-priority exception or interrupt, and drives the resulting vector address and data to the appropriate register files and data route. | ready | `ev:intAndExc:semantic_module` |
| `SPI_control` | AI 推断（confidence=high, review_status=ready）：APB-to-SPI bridge that translates APB register accesses into SPI master/slave control, clock generation, and interrupt aggregation. | ready | `ev:SPI_control:semantic_module` |
| `memory_slot` | AI 推断（confidence=high, review_status=ready）：Multiplexes instruction and data bus payloads from either normal CPU paths or an initialization controller (u_data_init) into a shared socmem instance, and propagates drive/free handshake events between the two requesters and the memory. | ready | `ev:memory_slot:semantic_module` |
| `mi2cv2` | AI 推断（confidence=high, review_status=ready）：I2C master/slave controller with APB-like register interface and external I2C bus drive | ready | `ev:mi2cv2:semantic_module` |

## 5. 接口与数据事件契约

- 确定性事实：interface_index 记录 `{"interfaces": 499, "modules": 100, "by_priority": {"primary": 208, "reference": 77, "secondary": 214}}`。
- 表格只记录 primary event interface 的事件、payload 和 companion free 名称；不推断 free 的生成逻辑。

| 模块 | Interface | 方向 | Event | Payload | Free/backpressure 记录 | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `IONet_slot` | `i_drvFCPU` | input | `i_drvFCPU` | `i_dataFCPU_51 [50:0]` | 未记录 | `ev:IONet_slot:interface`, `ev:IONet_slot:interface_data_contract` |
| `IONet_slot` | `o_drv2CPU` | output | `o_drv2CPU` | 未记录 | 未记录 | `ev:IONet_slot:interface`, `ev:IONet_slot:interface_data_contract` |
| `cpu_slot` | `i_driveFromMesh` | input | `i_driveFromMesh` | 未记录 | 未记录 | `ev:cpu_slot:interface`, `ev:cpu_slot:interface_data_contract` |
| `cpu_slot` | `o_driveToMesh` | output | `o_driveToMesh` | `o_data2Mesh [50:0]` | 未记录 | `ev:cpu_slot:interface`, `ev:cpu_slot:interface_data_contract` |
| `IONetwork` | `i_driveEast_10` | input | `i_driveEast_10` | `i_eastInMsg_51_10 [50:0]`, `i_eastInMsg_51_11 [50:0]` | `o_freeEast_10`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:IONetwork:interface`, `ev:IONetwork:interface_data_contract` |
| `IONetwork` | `i_driveEast_11` | input | `i_driveEast_11` | `i_eastInMsg_51_10 [50:0]`, `i_eastInMsg_51_11 [50:0]` | `o_freeEast_10`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:IONetwork:interface`, `ev:IONetwork:interface_data_contract` |
| `IONetwork` | `i_driveLocal_00` | input | `i_driveLocal_00` | `i_localInMsg_51_00 [50:0]`, `i_localInMsg_51_01 [50:0]`, `i_localInMsg_51_10 [50:0]` | `o_freeLocal_00`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:IONetwork:interface`, `ev:IONetwork:interface_data_contract` |
| `IONetwork` | `i_driveLocal_01` | input | `i_driveLocal_01` | `i_localInMsg_51_00 [50:0]`, `i_localInMsg_51_01 [50:0]`, `i_localInMsg_51_10 [50:0]` | `o_freeLocal_00`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:IONetwork:interface`, `ev:IONetwork:interface_data_contract` |
| `IONetwork` | `i_driveLocal_10` | input | `i_driveLocal_10` | `i_localInMsg_51_00 [50:0]`, `i_localInMsg_51_01 [50:0]`, `i_localInMsg_51_10 [50:0]` | `o_freeLocal_00`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:IONetwork:interface`, `ev:IONetwork:interface_data_contract` |
| `IONetwork` | `i_driveLocal_11` | input | `i_driveLocal_11` | `i_localInMsg_51_00 [50:0]`, `i_localInMsg_51_01 [50:0]`, `i_localInMsg_51_10 [50:0]` | `o_freeLocal_00`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:IONetwork:interface`, `ev:IONetwork:interface_data_contract` |
| `IONetwork` | `i_driveNorth_01` | input | `i_driveNorth_01` | `i_northInMsg_51_01 [50:0]`, `i_northInMsg_51_11 [50:0]` | `o_freeNorth_01`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:IONetwork:interface`, `ev:IONetwork:interface_data_contract` |
| `IONetwork` | `i_driveNorth_11` | input | `i_driveNorth_11` | `i_northInMsg_51_01 [50:0]`, `i_northInMsg_51_11 [50:0]` | `o_freeNorth_01`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:IONetwork:interface`, `ev:IONetwork:interface_data_contract` |
| `IONetwork` | `i_driveSouth_00` | input | `i_driveSouth_00` | `i_southInMsg_51_00 [50:0]`, `i_southInMsg_51_10 [50:0]` | `o_freeSouth_00`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:IONetwork:interface`, `ev:IONetwork:interface_data_contract` |
| `IONetwork` | `i_driveSouth_10` | input | `i_driveSouth_10` | `i_southInMsg_51_00 [50:0]`, `i_southInMsg_51_10 [50:0]` | `o_freeSouth_00`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:IONetwork:interface`, `ev:IONetwork:interface_data_contract` |
| `IONetwork` | `i_driveWest_00` | input | `i_driveWest_00` | `i_westInMsg_51_00 [50:0]`, `i_westInMsg_51_01 [50:0]` | `o_freeWest_00`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:IONetwork:interface`, `ev:IONetwork:interface_data_contract` |
| `IONetwork` | `i_driveWest_01` | input | `i_driveWest_01` | `i_westInMsg_51_00 [50:0]`, `i_westInMsg_51_01 [50:0]` | `o_freeWest_00`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:IONetwork:interface`, `ev:IONetwork:interface_data_contract` |
| `cpu_top_all` | `i_dataRoutDriveToLsu_1` | input | `i_dataRoutDriveToLsu_1` | 未记录 | `o_lsuFreeToDataRout_1`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:cpu_top_all:interface`, `ev:cpu_top_all:interface_data_contract` |
| `cpu_top_all` | `i_driveFromStart_1` | input | `i_driveFromStart_1` | `i_startPc_32 [31:0]` | `o_freeToStart_1`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:cpu_top_all:interface`, `ev:cpu_top_all:interface_data_contract` |
| `cpu_top_all` | `i_drvFICache` | input | `i_drvFICache` | 未记录 | 未记录 | `ev:cpu_top_all:interface`, `ev:cpu_top_all:interface_data_contract` |
| `cpu_top_all` | `o_drv2ICache` | output | `o_drv2ICache` | 未记录 | 未记录 | `ev:cpu_top_all:interface`, `ev:cpu_top_all:interface_data_contract` |
| `cpu_top_all` | `o_lsuDriveToDataRout_1` | output | `o_lsuDriveToDataRout_1` | `o_lsuToDataRoutData_105 [104:0]` | `i_lsuFreeFromDataRout_1`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:cpu_top_all:interface`, `ev:cpu_top_all:interface_data_contract` |
| `execute` | `i_LsuDriveToExe_1` | input | `i_LsuDriveToExe_1` | `i_lsuToExeData_64 [63:0]` | `o_lsuFreeFromExecute_1`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:execute:interface`, `ev:execute:interface_data_contract` |
| `execute` | `i_grfDriveToExecute_1` | input | `i_grfDriveToExecute_1` | `i_grfToExecuteData_64 [63:0]` | `o_executeFreeToGrf_1`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:execute:interface`, `ev:execute:interface_data_contract` |
| `execute` | `i_launchDriveToExecute_1` | input | `i_launchDriveToExecute_1` | `i_launchDataToExe_207 [206:0]` | `o_executeFreeToLaunch_1`；reference；仅在影响 drive availability/backpressure 时解释 | `ev:execute:interface`, `ev:execute:interface_data_contract` |

接口写作边界：payload/event binding 若为 `deterministic_fact` 可以陈述；`manual_description` 若来自 Semantic Layer，必须按 AI 推断处理；`free` 仅在影响 drive availability/backpressure 时解释。

## 6. Drive-centered Flow

- 确定性事实：flow_index 记录 `{"flows": 103, "modules": 38, "by_importance": {"high": 102, "medium": 1}}`。
- 每个 flow 先列 Knowledge IR 可证明的 trigger、payload、path/effect，再列 AI 语义 claim 和 evidence_gap。

### 6.1 `IONet_slot.i_drvFCPU`

- 确定性事实：flow_id=`flow_000_IONet_slot_i_drvFCPU`；title=`i_drvFCPU to o_drv2CPU`；manual_importance=`high`。
- 确定性事实：trigger_event=`i_drvFCPU`；证据：`ev:IONet_slot:flow:flow_000_IONet_slot_i_drvFCPU`。
- 确定性事实：payload binding：`i_drvFCPU` -> `i_dataFCPU_51 [50:0]`。
- 确定性事实：ordered_path step_count=15，component_step_count=13；前序组件：`cpu2noc_instance`(CPU2NoC), `delayUart0`(delay8U), `uut`(IONetwork), `IIC`(I2C2NoC), `gpio_slot`(gpio_slot), `TIMER`(timer_slot), `PWM0`(pwm0_top), `PWM1`(pwm1_top)。
- 确定性事实：branch_points=2，join_points=2，blocking_points=0。
- outputs/effects=`o_drv2CPU`。
- AI 推断（confidence=medium, review_status=needs_review, requires_rtl_source_review=true）：The CPU drive event is accompanied by a 51-bit data payload.
  - review_status：`needs_review`；requires_rtl_source_review=`True`；证据：`ev:IONet_slot:flow:flow_000_IONet_slot_i_drvFCPU`, `ev:IONet_slot:semantic_flow:flow_000_IONet_slot_i_drvFCPU`。
- 证据缺口：
  - 证据缺口：field=`semantic_flow.i_drvFCPU`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONet_slot:semantic_flow:flow_000_IONet_slot_i_drvFCPU`

### 6.2 `cpu_slot.i_driveFromMesh`

- 确定性事实：flow_id=`flow_000_cpu_slot_i_driveFromMesh`；title=`i_driveFromMesh to o_driveToMesh`；manual_importance=`high`。
- 确定性事实：trigger_event=`i_driveFromMesh`；证据：`ev:cpu_slot:flow:flow_000_cpu_slot_i_driveFromMesh`。
- 确定性事实：payload binding：`o_driveToMesh` -> `o_data2Mesh [50:0]`。
- 确定性事实：ordered_path step_count=5，component_step_count=3；前序组件：`data_mux`(data_slot), `u_cpu_core`(cpu_top_all), `u_memory_slot`(memory_slot)。
- 确定性事实：branch_points=3，join_points=3，blocking_points=0。
- outputs/effects=`o_driveToMesh`。
- AI 推断（confidence=medium, review_status=needs_review, requires_rtl_source_review=true）：The manual should focus on the data_mux as the central routing and arbitration point, and describe the round-trip path from mesh to CPU/memory and back.
  - review_status：`needs_review`；requires_rtl_source_review=`True`；证据：`ev:cpu_slot:flow:flow_000_cpu_slot_i_driveFromMesh`, `ev:cpu_slot:semantic_flow:flow_000_cpu_slot_i_driveFromMesh`。
- 证据缺口：
  - 证据缺口：field=`semantic_flow.i_driveFromMesh`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:cpu_slot:semantic_flow:flow_000_cpu_slot_i_driveFromMesh`

### 6.3 `IONetwork.i_driveEast_10`

- 确定性事实：flow_id=`flow_000_IONetwork_i_driveEast_10`；title=`i_driveEast_10 to o_driveEast_10, o_driveLocal_10, o_driveSouth_10`；manual_importance=`high`。
- 确定性事实：trigger_event=`i_driveEast_10`；证据：`ev:IONetwork:flow:flow_000_IONetwork_i_driveEast_10`。
- 确定性事实：payload binding：`i_driveEast_10` -> `i_eastInMsg_51_10 [50:0]`, `i_driveEast_10` -> `i_eastInMsg_51_11 [50:0]`, `o_driveEast_10` -> `o_eastMsg_51_10 [50:0]`, `o_driveEast_10` -> `o_eastMsg_51_11 [50:0]`, `o_driveEast_11` -> `o_eastMsg_51_10 [50:0]`, `o_driveEast_11` -> `o_eastMsg_51_11 [50:0]`, `o_driveLocal_00` -> `o_localMsg_51_00 [50:0]`, `o_driveLocal_00` -> `o_localMsg_51_01 [50:0]`, ... +22。
- 确定性事实：ordered_path step_count=17，component_step_count=4；前序组件：`node_10`(nodeTop), `node_00`(nodeTop), `node_11`(nodeTop), `node_01`(nodeTop)。
- 确定性事实：branch_points=4，join_points=4，blocking_points=0。
- outputs/effects=`o_driveEast_10`, `o_driveLocal_10`, `o_driveSouth_10`, `o_driveLocal_00`, `o_driveSouth_00`, `o_driveWest_00`, `o_driveEast_11`, `o_driveLocal_11`, `o_driveNorth_11`, `o_driveLocal_01`, `o_driveNorth_01`, `o_driveWest_01`。
- AI 推断（confidence=high, review_status=ready）：The manual should emphasize how a single event injection at node_10 fans out to all twelve outputs through the 2x2 mesh, and how the 51-bit payload is routed alongside.
  - review_status：`ready`；requires_rtl_source_review=`False`；证据：`ev:IONetwork:flow:flow_000_IONetwork_i_driveEast_10`, `ev:IONetwork:semantic_flow:flow_000_IONetwork_i_driveEast_10`。
- 证据缺口：
  - 证据缺口：field=`semantic_flow.i_driveEast_10`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_000_IONetwork_i_driveEast_10`

### 6.4 `IONetwork.i_driveEast_11`

- 确定性事实：flow_id=`flow_001_IONetwork_i_driveEast_11`；title=`i_driveEast_11 to o_driveEast_11, o_driveLocal_11, o_driveNorth_11`；manual_importance=`high`。
- 确定性事实：trigger_event=`i_driveEast_11`；证据：`ev:IONetwork:flow:flow_001_IONetwork_i_driveEast_11`。
- 确定性事实：payload binding：`i_driveEast_11` -> `i_eastInMsg_51_10 [50:0]`, `i_driveEast_11` -> `i_eastInMsg_51_11 [50:0]`, `o_driveEast_10` -> `o_eastMsg_51_10 [50:0]`, `o_driveEast_10` -> `o_eastMsg_51_11 [50:0]`, `o_driveEast_11` -> `o_eastMsg_51_10 [50:0]`, `o_driveEast_11` -> `o_eastMsg_51_11 [50:0]`, `o_driveLocal_00` -> `o_localMsg_51_00 [50:0]`, `o_driveLocal_00` -> `o_localMsg_51_01 [50:0]`, ... +22。
- 确定性事实：ordered_path step_count=17，component_step_count=4；前序组件：`node_11`(nodeTop), `node_01`(nodeTop), `node_10`(nodeTop), `node_00`(nodeTop)。
- 确定性事实：branch_points=4，join_points=4，blocking_points=0。
- outputs/effects=`o_driveEast_11`, `o_driveLocal_11`, `o_driveNorth_11`, `o_driveLocal_01`, `o_driveNorth_01`, `o_driveWest_01`, `o_driveEast_10`, `o_driveLocal_10`, `o_driveSouth_10`, `o_driveLocal_00`, `o_driveSouth_00`, `o_driveWest_00`。
- AI 推断（confidence=medium, review_status=ready）：Emphasize the mesh traversal and branching nature of the event, and de-emphasize payload routing and backpressure due to lack of evidence.
  - review_status：`ready`；requires_rtl_source_review=`False`；证据：`ev:IONetwork:flow:flow_001_IONetwork_i_driveEast_11`, `ev:IONetwork:semantic_flow:flow_001_IONetwork_i_driveEast_11`。
- 证据缺口：
  - 证据缺口：field=`semantic_flow.i_driveEast_11`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_001_IONetwork_i_driveEast_11`

### 6.5 `cpu_top_all.i_dataRoutDriveToLsu_1`

- 确定性事实：flow_id=`flow_000_cpu_top_all_i_dataRoutDriveToLsu_1`；title=`i_dataRoutDriveToLsu_1 to o_drv2ICache, o_lsuDriveToDataRout_1`；manual_importance=`high`。
- 确定性事实：trigger_event=`i_dataRoutDriveToLsu_1`；证据：`ev:cpu_top_all:flow:flow_000_cpu_top_all_i_dataRoutDriveToLsu_1`。
- 确定性事实：payload binding：`o_lsuDriveToDataRout_1` -> `o_lsuToDataRoutData_105 [104:0]`。
- 确定性事实：ordered_path step_count=81，component_step_count=78；前序组件：`DRSelector`(cSelector2_65b_cpu), `lsu_inst`(lsu), `intAndExc_inst`(intAndExc), `goDelay5`(delay8U), `lsuToDataRoutDelay0`(delay16U), `lsuDelayFifo`(cFifo1), `lsuToIcacheDelay`(delay8U), `lsuDriveToLaunchDelayFifo1`(cFifo1)。
- 确定性事实：branch_points=25，join_points=25，blocking_points=21。
- outputs/effects=`o_drv2ICache`, `o_lsuDriveToDataRout_1`。
- AI 推断（confidence=medium, review_status=needs_review, requires_rtl_source_review=true）：The 105-bit payload accompanies the o_lsuDriveToDataRout_1 event, carrying load result data back to the DataRout unit.
  - review_status：`needs_review`；requires_rtl_source_review=`True`；证据：`ev:cpu_top_all:flow:flow_000_cpu_top_all_i_dataRoutDriveToLsu_1`, `ev:cpu_top_all:semantic_flow:flow_000_cpu_top_all_i_dataRoutDriveToLsu_1`。
- 证据缺口：
  - 证据缺口：field=`semantic_flow.i_dataRoutDriveToLsu_1`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:cpu_top_all:semantic_flow:flow_000_cpu_top_all_i_dataRoutDriveToLsu_1`

### 6.6 `cpu_top_all.i_driveFromStart_1`

- 确定性事实：flow_id=`flow_002_cpu_top_all_i_driveFromStart_1`；title=`i_driveFromStart_1 to o_drv2ICache, o_lsuDriveToDataRout_1`；manual_importance=`high`。
- 确定性事实：trigger_event=`i_driveFromStart_1`；证据：`ev:cpu_top_all:flow:flow_002_cpu_top_all_i_driveFromStart_1`。
- 确定性事实：payload binding：`i_driveFromStart_1` -> `i_startPc_32 [31:0]`, `o_lsuDriveToDataRout_1` -> `o_lsuToDataRoutData_105 [104:0]`。
- 确定性事实：ordered_path step_count=80，component_step_count=77；前序组件：`BranchMerge`(cMutexMerge4_32b), `branchDelay1`(delay8U), `fetchSele1`(cSelector2_1b), `fetch_inst`(fetch), `outStackSeleDelay0`(delay8U), `ifHelpDecExcDelayFifo`(cFifo1), `fetchToIcacheDelay`(delay4U), `ifExcDelayFifo`(cFifo1)。
- 确定性事实：branch_points=24，join_points=25，blocking_points=21。
- outputs/effects=`o_drv2ICache`, `o_lsuDriveToDataRout_1`。
- AI 推断（confidence=high, review_status=ready）：The manual should emphasize how a single start event flows through the CPU pipeline, highlighting key merge and split points.
  - review_status：`ready`；requires_rtl_source_review=`False`；证据：`ev:cpu_top_all:flow:flow_002_cpu_top_all_i_driveFromStart_1`, `ev:cpu_top_all:semantic_flow:flow_002_cpu_top_all_i_driveFromStart_1`。
- 证据缺口：
  - 证据缺口：field=`semantic_flow.i_driveFromStart_1`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:cpu_top_all:semantic_flow:flow_002_cpu_top_all_i_driveFromStart_1`

### 6.7 `execute.i_LsuDriveToExe_1`

- 确定性事实：flow_id=`flow_002_execute_i_LsuDriveToExe_1`；title=`execute flow from i_LsuDriveToExe_1`；manual_importance=`high`。
- 确定性事实：trigger_event=`i_LsuDriveToExe_1`；证据：`ev:execute:flow:flow_002_execute_i_LsuDriveToExe_1`。
- 确定性事实：payload binding：`i_LsuDriveToExe_1` -> `i_lsuToExeData_64 [63:0]`。
- 确定性事实：ordered_path step_count=10，component_step_count=9；前序组件：`lsuDelay0`(delay4U), `lsuMerge`(cMutexMerge2_1b), `rele0Merge`(cWaitMerge2_32_1_33b_exe), `rele2Merge`(cWaitMerge2_32_1_33b_exe), `rele0Selector`(cSelector2_33b_exe), `rele2Selector`(cSelector2_33b_exe), `rs1Merge`(cMutexMerge2_32b_exe), `rs2Merge`(cMutexMerge2_32b_exe)。
- 确定性事实：branch_points=2，join_points=8，blocking_points=6。
- 证据缺口：Knowledge IR did not find a module output endpoint for this flow.。
- AI 推断（confidence=medium, review_status=needs_review, requires_rtl_source_review=true）：The 64-bit LSU data payload is carried alongside the drive event and is split into 32-bit halves for rs1 and rs2 based on address comparison.
  - review_status：`needs_review`；requires_rtl_source_review=`True`；证据：`ev:execute:flow:flow_002_execute_i_LsuDriveToExe_1`, `ev:execute:semantic_flow:flow_002_execute_i_LsuDriveToExe_1`。
- 证据缺口：
  - 证据缺口：field=`internal_event_flow.i_LsuDriveToExe_1`；reason=no module event output reached from i_LsuDriveToExe_1；evidence=`ev:execute:knowledge_module`
  - 证据缺口：field=`semantic_flow.i_LsuDriveToExe_1`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:execute:semantic_flow:flow_002_execute_i_LsuDriveToExe_1`

### 6.8 `execute.i_grfDriveToExecute_1`

- 确定性事实：flow_id=`flow_001_execute_i_grfDriveToExecute_1`；title=`execute flow from i_grfDriveToExecute_1`；manual_importance=`high`。
- 确定性事实：trigger_event=`i_grfDriveToExecute_1`；证据：`ev:execute:flow:flow_001_execute_i_grfDriveToExecute_1`。
- 确定性事实：payload binding：`i_grfDriveToExecute_1` -> `i_grfToExecuteData_64 [63:0]`。
- 确定性事实：ordered_path step_count=9，component_step_count=8；前序组件：`grfResSplitter`(cSplitter2_64b_exe), `rele1Merge`(cWaitMerge2_32_1_33b_exe), `rele3Merge`(cWaitMerge2_32_1_33b_exe), `rele1Selector`(cSelector2_33b_exe), `rele3Selector`(cSelector2_33b_exe), `rs1Merge`(cMutexMerge2_32b_exe), `rs2Merge`(cMutexMerge2_32b_exe), `regMerge`(cWaitMerge2_64b_exe)。
- 确定性事实：branch_points=3，join_points=7，blocking_points=5。
- 证据缺口：Knowledge IR did not find a module output endpoint for this flow.。
- AI 推断（confidence=low, review_status=needs_review, requires_rtl_source_review=true）：The manual should emphasize that this flow is an internal pipeline stage that terminates at a delay element, not a complete event path to a module output.
  - review_status：`needs_review`；requires_rtl_source_review=`True`；证据：`ev:execute:flow:flow_001_execute_i_grfDriveToExecute_1`, `ev:execute:semantic_flow:flow_001_execute_i_grfDriveToExecute_1`。
- 证据缺口：
  - 证据缺口：field=`internal_event_flow.i_grfDriveToExecute_1`；reason=no module event output reached from i_grfDriveToExecute_1；evidence=`ev:execute:knowledge_module`
  - 证据缺口：field=`semantic_flow.i_grfDriveToExecute_1`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:execute:semantic_flow:flow_001_execute_i_grfDriveToExecute_1`

### 6.9 `grf.i_driveFromExe_1`

- 确定性事实：flow_id=`flow_000_grf_i_driveFromExe_1`；title=`i_driveFromExe_1 to o_grfDriveToExe_1`；manual_importance=`high`。
- 确定性事实：trigger_event=`i_driveFromExe_1`；证据：`ev:grf:flow:flow_000_grf_i_driveFromExe_1`。
- 确定性事实：payload binding：`o_grfDriveToExe_1` -> `o_grfDataToExe_64 [63:0]`。
- 确定性事实：ordered_path step_count=3，component_step_count=1；前序组件：`cFifo1_2`(cFifo1_grf)。
- 确定性事实：branch_points=0，join_points=0，blocking_points=1。
- outputs/effects=`o_grfDriveToExe_1`。
- AI 推断（confidence=medium, review_status=ready）：Emphasize the single-step FIFO buffering and note payload shaping as a separate concern.
  - review_status：`ready`；requires_rtl_source_review=`False`；证据：`ev:grf:flow:flow_000_grf_i_driveFromExe_1`, `ev:grf:semantic_flow:flow_000_grf_i_driveFromExe_1`。
- 证据缺口：
  - 证据缺口：field=`semantic_flow.i_driveFromExe_1`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:grf:semantic_flow:flow_000_grf_i_driveFromExe_1`

### 6.10 `grf.i_driveFromExp_1`

- 确定性事实：flow_id=`flow_001_grf_i_driveFromExp_1`；title=`i_driveFromExp_1 to o_grfDriveToExp_1`；manual_importance=`high`。
- 确定性事实：trigger_event=`i_driveFromExp_1`；证据：`ev:grf:flow:flow_001_grf_i_driveFromExp_1`。
- 确定性事实：payload binding：`i_driveFromExp_1` -> `i_expAddr_8 [7:0]`, `i_driveFromExp_1` -> `i_expDataToGrf_64 [63:0]`, `o_grfDriveToExp_1` -> `o_grfDataToExp_192 [191:0]`。
- 确定性事实：ordered_path step_count=3，component_step_count=1；前序组件：`cFifo1_5`(cFifo1_grf)。
- 确定性事实：branch_points=0，join_points=0，blocking_points=1。
- outputs/effects=`o_grfDriveToExp_1`。
- AI 推断（confidence=medium, review_status=needs_review, requires_rtl_source_review=true）：Emphasize the single-stage FIFO buffering and the decoupling of event drive from payload routing.
  - review_status：`needs_review`；requires_rtl_source_review=`True`；证据：`ev:grf:flow:flow_001_grf_i_driveFromExp_1`, `ev:grf:semantic_flow:flow_001_grf_i_driveFromExp_1`。
- 证据缺口：
  - 证据缺口：field=`semantic_flow.i_driveFromExp_1`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:grf:semantic_flow:flow_001_grf_i_driveFromExp_1`

## 7. 内部组件与 Assign 影响

### 7.1 组件 family 概览

下表只陈述 Manual Context 记录到的 family 名称和实例数量，不额外解释 family 的 RTL 行为语义。

| Component family | Instance count |
| --- | --- |
| `ArbMerge` | 3 |
| `Fifo1` | 119 |
| `MutexMerge` | 53 |
| `PmtFifo1` | 9 |
| `SelSplit` | 115 |
| `WaitMerge` | 30 |
| `eventSource` | 2 |

### 7.2 Assign 影响样本

assign 的 lhs/rhs 来自确定性解析事实；解释字段只有在 Semantic Layer 提供 claim 时才写成 AI 推断，否则写为证据缺口。

| 模块 | Assign | Impact area | LHS | RHS 摘要 | 解释状态 | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `async2sync` | `assign_0` | unknown | `rst_sync_n` | rst_s2 | 证据缺口：No Semantic Layer assignment interpretation is available. | `ev:async2sync:assignments` |
| `execute` | `assign_1` | control_path | `{w_c_1,w_addtype1_3,w_msr_1,w_bfi_1,w_bfc_1,w_sbfx_1,w_ubfx_1,w_msbit_5,w_lsbit_5, w_isMultiLS_1,w_n_4,w_registerList_16, w_pc_32, w_load_1, w_loadStoreWidth_2, w_loadSign_1, w_isLS_1, w_writeRd_1, w_dHi_4, w_dLo_4, w_shift_3, w_P_1, w_W_1, w_U_1, w_S_1, w_grfFlag_1, w_opNot_1, w_isXt_1, w_shiftC_1, w_shiftS_1, w_shiftNum_1, w_revType_2, w_satqS_1, w_mulDivS_1, w_insPath_8, w_op3_32, w_op2_32, w_op1_32}` | i_launchDataToExe_207 | 证据缺口：No Semantic Layer assignment interpretation is available. | `ev:execute:assignments` |
| `execute` | `assign_2` | control_path | `o_grfFlag_1` | w_grfFlag_1 | 证据缺口：No Semantic Layer assignment interpretation is available. | `ev:execute:assignments` |
| `execute` | `assign_38` | data_path | `w_lsuR1Data_32` | w_rs1Addr_4 == w_preRdHiAddr_4 ? i_lsuToExeData_64[63:32] : i_lsuToExeData_64[31:0] | 证据缺口：No Semantic Layer assignment interpretation is available. | `ev:execute:assignments` |
| `execute` | `assign_39` | data_path | `w_lsuR2Data_32` | w_rs2Addr_4 == w_preRdHiAddr_4 ? i_lsuToExeData_64[63:32] : i_lsuToExeData_64[31:0] | 证据缺口：No Semantic Layer assignment interpretation is available. | `ev:execute:assignments` |
| `execute` | `assign_53` | data_path | `o_exeToLaunchData_96` | {w_nzcv_4,{28{1'b0}},r_resMutexMergeToFinalWaitMergeData_64} | 证据缺口：No Semantic Layer assignment interpretation is available. | `ev:execute:assignments` |
| `execute` | `assign_56` | data_path | `w_address_32` | w_P_1 == 1'b1 ? o_executeDataToLsu_163[31:0] : o_executeDataToLsu_163[63:32] | 证据缺口：No Semantic Layer assignment interpretation is available. | `ev:execute:assignments` |
| `execute` | `assign_58` | data_path | `o_exeToExcpData_36` | {w_pc_32,w_excNum_4} | 证据缺口：No Semantic Layer assignment interpretation is available. | `ev:execute:assignments` |
| `execute` | `assign_0` | control_path | `o_wen_2` | i_wen_2 | 证据缺口：No Semantic Layer assignment interpretation is available. | `ev:execute:assignments` |
| `grf` | `assign_1` | control_path | `w_lauindex2_4` | i_rsAddr_8[7:4] | AI 推断（confidence=high, review_status=ready）：Read address nibble extraction for register file operand ports. | `ev:grf:assignments` |
| `grf` | `assign_2` | data_path | `o_grfDataToLaunch_64` | {r_rsValue_32[1], r_rsValue_32[0]} | AI 推断（confidence=high, review_status=ready）：Registered read data output for Launch, Exe, Lsu, and Wb ports. | `ev:grf:assignments` |
| `grf` | `assign_3` | control_path | `w_exeindex1_4` | i_rs2Addr_8[3:0] | AI 推断（confidence=high, review_status=ready）：Read address nibble extraction for register file operand ports. | `ev:grf:assignments` |
| `grf` | `assign_4` | control_path | `w_exeindex2_4` | i_rs2Addr_8[7:4] | AI 推断（confidence=high, review_status=ready）：Read address nibble extraction for register file operand ports. | `ev:grf:assignments` |
| `grf` | `assign_5` | data_path | `o_grfDataToExe_64` | {r_rsValue_32[3], r_rsValue_32[2]} | AI 推断（confidence=high, review_status=ready）：Registered read data output for Launch, Exe, Lsu, and Wb ports. | `ev:grf:assignments` |
| `grf` | `assign_6` | control_path | `w_lsuindex1_4` | i_rs3Addr_8[3:0] | AI 推断（confidence=high, review_status=ready）：Read address nibble extraction for register file operand ports. | `ev:grf:assignments` |
| `grf` | `assign_7` | control_path | `w_lsuindex2_4` | i_rs3Addr_8[7:4] | AI 推断（confidence=high, review_status=ready）：Read address nibble extraction for register file operand ports. | `ev:grf:assignments` |
| `grf` | `assign_8` | data_path | `o_grfDataToLsu_64` | {r_rsValue_32[5], r_rsValue_32[4]} | AI 推断（confidence=high, review_status=ready）：Registered read data output for Launch, Exe, Lsu, and Wb ports. | `ev:grf:assignments` |
| `grf` | `assign_9` | control_path | `w_wbindex1_4` | i_rs4Addr_8[3:0] | AI 推断（confidence=high, review_status=ready）：Read address nibble extraction for register file operand ports. | `ev:grf:assignments` |

## 8. 证据缺口与 Review 问题

- Validation：`passed` / issues=0。
- Validation issues：0。

### 8.1 Evidence gaps

- 证据缺口：field=`parser_stats.unresolved_instance_count`；reason=8 unresolved parser instances remain.；evidence=`ev:project:parser_stats`
- 证据缺口：field=`parser_stats.warning_count`；reason=8 parser warnings are present.；evidence=`ev:project:parser_stats`
- 证据缺口：field=`initMode_pad connectivity`；reason=The compact context shows initMode_pad as a control input but does not specify how it connects to u_cpu or io_slot. Its role in conditioning the drive flow is unclear.；evidence=`ev:arm_soc_top:semantic_module`
- 证据缺口：field=`gpio_data_o top-level connection`；reason=io_slot has a gpio_data_o output, but no top-level data output is listed in the interface. It may be unconnected or connected to a pad not captured in the context.；evidence=`ev:arm_soc_top:semantic_module`
- 证据缺口：field=`Mesh routing logic and payload decoding`；reason=The compact context does not provide details on how the mesh (uut) decodes the 51-bit payload to route drive events and data to specific peripherals. RTL source review is needed to understand the addressing scheme and routing logic.；evidence=`ev:IONet_slot:semantic_module`
- 证据缺口：field=`Free signal generation logic`；reason=The compact context does not specify how i_freeFCPU and o_free2CPU are generated or their relationship to the drive event flow. RTL source review is needed to understand the handshake protocol.；evidence=`ev:IONet_slot:semantic_module`
- 证据缺口：field=`Delay element purpose and implementation`；reason=The compact context shows a delay element (delayUart0) on the NoC channel 0 path, but does not explain its purpose or implementation details. RTL source review is needed to understand the delay value and rationale.；evidence=`ev:IONet_slot:semantic_module`
- 证据缺口：field=`semantic_flow.i_drvFCPU`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONet_slot:semantic_flow:flow_000_IONet_slot_i_drvFCPU`
- 证据缺口：field=`module structure and reset chain`；reason=The compact context lacks the module port list, internal flip-flop declarations, and the clock signal. The exact reset polarity and the number of synchronizer stages are unknown.；evidence=`ev:async2sync:semantic_module`
- 证据缺口：field=`semantic_flow.i_driveFromMesh`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:cpu_slot:semantic_flow:flow_000_cpu_slot_i_driveFromMesh`
- 证据缺口：field=`semantic_flow.i_driveEast_10`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_000_IONetwork_i_driveEast_10`
- 证据缺口：field=`semantic_flow.i_driveEast_11`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_001_IONetwork_i_driveEast_11`
- 证据缺口：field=`semantic_flow.i_driveLocal_00`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_002_IONetwork_i_driveLocal_00`
- 证据缺口：field=`semantic_flow.i_driveLocal_01`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_003_IONetwork_i_driveLocal_01`
- 证据缺口：field=`semantic_flow.i_driveLocal_10`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_004_IONetwork_i_driveLocal_10`
- 证据缺口：field=`semantic_flow.i_driveLocal_11`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_005_IONetwork_i_driveLocal_11`
- 证据缺口：field=`semantic_flow.i_driveNorth_01`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_006_IONetwork_i_driveNorth_01`
- 证据缺口：field=`semantic_flow.i_driveNorth_11`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_007_IONetwork_i_driveNorth_11`
- 证据缺口：field=`semantic_flow.i_driveSouth_00`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_008_IONetwork_i_driveSouth_00`
- 证据缺口：field=`semantic_flow.i_driveSouth_10`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_009_IONetwork_i_driveSouth_10`
- 证据缺口：field=`semantic_flow.i_driveWest_00`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_010_IONetwork_i_driveWest_00`
- 证据缺口：field=`semantic_flow.i_driveWest_01`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:IONetwork:semantic_flow:flow_011_IONetwork_i_driveWest_01`
- 证据缺口：field=`Event-payload contracts for i_dataRoutDriveToLsu_1 and i_drvFICache`；reason=The event-payload contracts for these inputs have low confidence and no associated payloads. The RTL source is needed to determine if these events carry implicit data or are purely control signals.；evidence=`ev:cpu_top_all:semantic_module`
- 证据缺口：field=`Assignments with conditional logic (assign index 20)`；reason=The compact context does not provide the full RTL source for assignments. The ternary operator in assign index 20 (w_exeTrueNum_4) suggests conditional data path selection, but the exact condition and data path semantics are unclear without the RTL source.；evidence=`ev:cpu_top_all:semantic_module`
- 证据缺口：field=`semantic_flow.i_dataRoutDriveToLsu_1`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:cpu_top_all:semantic_flow:flow_000_cpu_top_all_i_dataRoutDriveToLsu_1`
- 证据缺口：field=`semantic_flow.i_driveFromStart_1`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:cpu_top_all:semantic_flow:flow_002_cpu_top_all_i_driveFromStart_1`
- 证据缺口：field=`semantic_flow.i_drvFICache`；reason=Semantic Layer requested RTL source review for this flow.；evidence=`ev:cpu_top_all:semantic_flow:flow_001_cpu_top_all_i_drvFICache`
- 证据缺口：field=`internal_event_flow.i_LsuDriveToExe_1`；reason=no module event output reached from i_LsuDriveToExe_1；evidence=`ev:execute:knowledge_module`
- 证据缺口：field=`internal_event_flow.i_grfDriveToExecute_1`；reason=no module event output reached from i_grfDriveToExecute_1；evidence=`ev:execute:knowledge_module`
- 证据缺口：field=`internal_event_flow.i_launchDriveToExecute_1`；reason=no module event output reached from i_launchDriveToExecute_1；evidence=`ev:execute:knowledge_module`

### 8.2 Review questions

- The compact context shows initMode_pad as a control input but does not specify how it connects to u_cpu or io_slot. Its role in conditioning the drive flow is unclear.（subject=`initMode_pad connectivity`；evidence=`ev:arm_soc_top:semantic_module`）
- io_slot has a gpio_data_o output, but no top-level data output is listed in the interface. It may be unconnected or connected to a pad not captured in the context.（subject=`gpio_data_o top-level connection`；evidence=`ev:arm_soc_top:semantic_module`）
- The compact context does not provide details on how the mesh (uut) decodes the 51-bit payload to route drive events and data to specific peripherals. RTL source review is needed to understand the addressing scheme and routing logic.（subject=`Mesh routing logic and payload decoding`；evidence=`ev:IONet_slot:semantic_module`）
- The compact context does not specify how i_freeFCPU and o_free2CPU are generated or their relationship to the drive event flow. RTL source review is needed to understand the handshake protocol.（subject=`Free signal generation logic`；evidence=`ev:IONet_slot:semantic_module`）
- The compact context shows a delay element (delayUart0) on the NoC channel 0 path, but does not explain its purpose or implementation details. RTL source review is needed to understand the delay value and rationale.（subject=`Delay element purpose and implementation`；evidence=`ev:IONet_slot:semantic_module`）
- Review semantic meaning for flow flow_000_IONet_slot_i_drvFCPU.（subject=`flow_000_IONet_slot_i_drvFCPU`；evidence=`ev:IONet_slot:flow:flow_000_IONet_slot_i_drvFCPU`, `ev:IONet_slot:semantic_flow:flow_000_IONet_slot_i_drvFCPU`）
- The compact context lacks the module port list, internal flip-flop declarations, and the clock signal. The exact reset polarity and the number of synchronizer stages are unknown.（subject=`module structure and reset chain`；evidence=`ev:async2sync:semantic_module`）
- Review semantic meaning for flow flow_000_cpu_slot_i_driveFromMesh.（subject=`flow_000_cpu_slot_i_driveFromMesh`；evidence=`ev:cpu_slot:flow:flow_000_cpu_slot_i_driveFromMesh`, `ev:cpu_slot:semantic_flow:flow_000_cpu_slot_i_driveFromMesh`）
- Review semantic meaning for flow flow_003_IONetwork_i_driveLocal_01.（subject=`flow_003_IONetwork_i_driveLocal_01`；evidence=`ev:IONetwork:flow:flow_003_IONetwork_i_driveLocal_01`, `ev:IONetwork:semantic_flow:flow_003_IONetwork_i_driveLocal_01`）
- Review semantic meaning for flow flow_004_IONetwork_i_driveLocal_10.（subject=`flow_004_IONetwork_i_driveLocal_10`；evidence=`ev:IONetwork:flow:flow_004_IONetwork_i_driveLocal_10`, `ev:IONetwork:semantic_flow:flow_004_IONetwork_i_driveLocal_10`）
- Review semantic meaning for flow flow_005_IONetwork_i_driveLocal_11.（subject=`flow_005_IONetwork_i_driveLocal_11`；evidence=`ev:IONetwork:flow:flow_005_IONetwork_i_driveLocal_11`, `ev:IONetwork:semantic_flow:flow_005_IONetwork_i_driveLocal_11`）
- Review semantic meaning for flow flow_006_IONetwork_i_driveNorth_01.（subject=`flow_006_IONetwork_i_driveNorth_01`；evidence=`ev:IONetwork:flow:flow_006_IONetwork_i_driveNorth_01`, `ev:IONetwork:semantic_flow:flow_006_IONetwork_i_driveNorth_01`）
- Review semantic meaning for flow flow_007_IONetwork_i_driveNorth_11.（subject=`flow_007_IONetwork_i_driveNorth_11`；evidence=`ev:IONetwork:flow:flow_007_IONetwork_i_driveNorth_11`, `ev:IONetwork:semantic_flow:flow_007_IONetwork_i_driveNorth_11`）
- Review semantic meaning for flow flow_008_IONetwork_i_driveSouth_00.（subject=`flow_008_IONetwork_i_driveSouth_00`；evidence=`ev:IONetwork:flow:flow_008_IONetwork_i_driveSouth_00`, `ev:IONetwork:semantic_flow:flow_008_IONetwork_i_driveSouth_00`）
- Review semantic meaning for flow flow_009_IONetwork_i_driveSouth_10.（subject=`flow_009_IONetwork_i_driveSouth_10`；evidence=`ev:IONetwork:flow:flow_009_IONetwork_i_driveSouth_10`, `ev:IONetwork:semantic_flow:flow_009_IONetwork_i_driveSouth_10`）
- Review semantic meaning for flow flow_011_IONetwork_i_driveWest_01.（subject=`flow_011_IONetwork_i_driveWest_01`；evidence=`ev:IONetwork:flow:flow_011_IONetwork_i_driveWest_01`, `ev:IONetwork:semantic_flow:flow_011_IONetwork_i_driveWest_01`）
- The event-payload contracts for these inputs have low confidence and no associated payloads. The RTL source is needed to determine if these events carry implicit data or are purely control signals.（subject=`Event-payload contracts for i_dataRoutDriveToLsu_1 and i_drvFICache`；evidence=`ev:cpu_top_all:semantic_module`）
- The compact context does not provide the full RTL source for assignments. The ternary operator in assign index 20 (w_exeTrueNum_4) suggests conditional data path selection, but the exact condition and data path semantics are unclear without the RTL source.（subject=`Assignments with conditional logic (assign index 20)`；evidence=`ev:cpu_top_all:semantic_module`）
- Review semantic meaning for flow flow_000_cpu_top_all_i_dataRoutDriveToLsu_1.（subject=`flow_000_cpu_top_all_i_dataRoutDriveToLsu_1`；evidence=`ev:cpu_top_all:flow:flow_000_cpu_top_all_i_dataRoutDriveToLsu_1`, `ev:cpu_top_all:semantic_flow:flow_000_cpu_top_all_i_dataRoutDriveToLsu_1`）
- Confirm parser evidence gap: no module event output reached from i_LsuDriveToExe_1（subject=`internal_event_flow.i_LsuDriveToExe_1`；evidence=`ev:execute:knowledge_module`）

## 9. 证据边界与写作规则

- 主证据为 Manual Context；最终手册不要直接把 parser JSON、Knowledge IR、AI Context 或 Semantic Layer 当作主输入。
- deterministic_fact 可以直接陈述；derived_fact 必须说明是派生事实。
- ai_inferred 必须标注为推断、可能或需要 review，不能写成确定事实。
- human_asserted 必须标注为人工断言；evidence_gap 必须写入证据不足或待审查章节。
- 不得补写 Manual Context 中不存在的连接、接口、flow、FSM、always 行为、寄存器更新条件或时序保证。
- drive 是主要事件信号；free 只在影响 drive availability/backpressure 时重点解释。

- 手册生成策略：`manual_context_evidence_bound_markdown`；llm_freeform_generation=`False`。
- 主输入入口：`project_context.json`, `system_topology.json`, `interface_index.json`, `flow_index.json`, `evidence_index.json`, `modules/<module>/module_context.json`, `modules/<module>/interfaces.json`, `modules/<module>/flows/<flow_id>.json`。
