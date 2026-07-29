# 第七阶段完成记录：LangGraph 工作流

## 1. 阶段范围

本阶段把第五、六阶段已经独立验证的分类、抽取、申请匹配、状态机和人工审核整合
为可中断、可持久化和可恢复的 LangGraph 工作流。Reply Agent、回复草稿、SMTP、
任务日程和归档仍按实施计划留在后续阶段。

正式流程为：

```text
load_email
→ classify_email
→ NON_JOB：persist_analysis → finalize
→ JOB_RELATED：extract_information
→ validate_results
→ persist_analysis
→ match_application
→ human_review / interrupt
→ execute_review
→ 如有阶段建议，再次 human_review / interrupt
→ execute_review
→ finalize
```

## 2. 已完成功能

- 新增强类型 `WorkflowState`，保存工作流、邮件、结构化 Agent 输出、审核任务、
  重试次数和失败摘要，不保存 ORM Session、凭据或附件内容。
- 新增确定性 `JobMailGraph`，Orchestrator 不调用模型，按分类结果和审核状态路由。
- Classification、Extraction、Application Agent 顺序执行；`NON_JOB` 不调用后续
  Agent。
- 新增 `validate_results` 确定性节点，Pydantic Schema 和申请状态机继续作为关键
  校验边界。
- Classification、Extraction 和 Application 节点失败时最多重试一次，仍失败则
  将 `workflow_runs` 标记为 `FAILED`。
- `interrupt()` 前幂等创建 MySQL `review_tasks`；恢复使用
  `Command(resume=...)` 和相同 `thread_id`。
- 申请关联/新建和阶段变化保持两次独立审核。审核决定先写 MySQL，图恢复后才由
  Executor 执行获批动作。
- `ActionExecution`、审核任务和申请事件沿用第六阶段唯一键、版本和事务边界，
  重复审核不会重复执行。
- `workflow_runs.agent_trace` 保存三个 Agent 的 Prompt 版本、输入摘要、结构化输出、
  置信度、状态、耗时和脱敏错误。
- 新增 `POST /api/v1/emails/{email_id}/workflow-runs` 和
  `GET /api/v1/workflow-runs/{run_id}`；原独立分析和匹配接口保留。
- 原审核决策接口自动识别第七阶段工作流并恢复图；第六阶段独立工作流仍保持兼容。

## 3. Checkpoint 与安全

- 使用 `langgraph 1.2.10`、`langgraph-checkpoint-sqlite 3.1.0`。
- 使用 `EncryptedSerializer` 和 `pycryptodome 3.23.0` 对 SQLite checkpoint
  进行 AES 静态加密。
- 密钥由 `JOB_MAIL_CHECKPOINT_ENCRYPTION_KEY` 提供，只接受 16、24 或 32 字节
  AES 密钥的十六进制表示。
- State 节点写入统一转换为 JSON 数据，并为反序列化器设置空的自定义模块白名单，
  避免 checkpoint 被篡改后反序列化任意项目类型。
- checkpoint 文件位于运行数据目录并由 `.gitignore` 排除；MySQL 仍是邮件、分析、
  审核和动作的唯一业务真相源。

## 4. 验证结果

### 自动化测试

- 全量测试：`81 passed`。
- Ruff：`All checks passed!`。
- `git diff --check`：通过，仅存在 Windows 换行转换提示。
- 新增覆盖：
  - `NON_JOB` 提前结束；
  - 求职邮件两次中断和恢复；
  - 审核拒绝后取消；
  - Agent 首次失败后受限重试；
  - 关闭并重新创建图、重新打开 SQLite 后继续恢复；
  - checkpoint 文件中不存在明文测试正文；
  - AES 密钥格式校验；
  - 工作流启动 API 契约。

### 真实 MySQL 闭环

使用现有测试邮件和 Stub Agent 执行完整两段审核：

```text
WAITING_REVIEW
→ 批准新建申请
→ WAITING_REVIEW
→ 批准阶段变化
→ SUCCEEDED
```

结果为 2 个审核执行、3 条申请时间线事件，最终申请阶段为 `INTERVIEW`。联调结束后
临时工作流、分析、审核、执行、申请和事件均已清理；复查相关临时记录为 0。

### 真实 DeepSeek

脱敏面试 Fixture 经正式 Classification 和 Extraction Agent 再次验证：

- 分类：`INTERVIEW`；
- 分类置信度：1.0；
- 抽取置信度：1.0；
- 公司：星海科技；
- 岗位：后端开发工程师；
- 面试时间、回复截止时间和会议链接均成功抽取。

完整图的确定性编排和 MySQL 写入使用 Stub Agent 验证，真实模型的三个专业 Agent
已分别在第五、六阶段及本次 Fixture 验证中通过。

## 5. 开发问题与处理

| 问题 | 原因 | 处理 |
|---|---|---|
| Conda 环境缺少 LangGraph | 前六阶段尚未进入正式工作流 | 增加 LangGraph、SQLite saver 和加密依赖 |
| 恢复时 `human_review` 的中断前逻辑再次执行 | LangGraph 从中断节点开头恢复 | `mark_waiting` 设计为幂等赋值，并增加重放测试 |
| Pydantic 对象反序列化出现自定义模块警告 | 默认 msgpack 会记录项目类型 | State 写入改为 JSON，禁用自定义 msgpack 模块反序列化 |
| Executor 出现“事务已经开始” | 读取审核任务触发 SQLAlchemy autobegin 后再次 `begin()` | 读取状态后显式结束只读事务，再进入独立执行事务 |
| 沙箱内真实模型连接被系统拒绝 | 开发沙箱限制外部网络 | 经授权在沙箱外运行脱敏 Fixture，真实 DeepSeek 验证通过 |

## 6. 遗留边界

- 第七阶段不实现 Reply Agent、草稿、Formatter 或 SMTP；这些属于第八阶段。
- 低置信度或模糊抽取结果会保存为 `PENDING_CONFIRMATION`，且后续申请写动作仍须
  审核；面向分析字段逐项修改的独立审核动作和前端编辑器尚未实现。
- 不实现任务日程、归档、LangGraph Store、并行 Agent 或 LLM Supervisor。
- SQLite saver 面向单机 MVP；多进程或多实例部署前必须改为受支持的共享
  checkpointer。
- 本地启动工作流前必须在未提交的 `.env` 中配置 checkpoint 加密密钥。

下一步进入第八阶段：实现 Reply Agent、回复草稿审核、确定性邮件格式化和 SMTP
幂等发送。
