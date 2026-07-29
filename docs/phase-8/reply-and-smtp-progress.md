# 第八阶段完成记录：回复生成、审核与 SMTP 幂等发送

## 1. 阶段结论

第八阶段后端纵向闭环已完成。正式系统现在具备 Reply Agent、版本化 Prompt、强类型
输入输出、确定性主题/地址/称呼/签名/MIME 格式化、回复草稿版本管理、`SEND_REPLY`
高风险审核任务，以及独立于 Agent 和 LangGraph 的 SMTP 幂等 Executor。

用户于 2026-07-29 明确确认后，本阶段已使用受控 163 测试账户完成真实外部发信
验收：先自发一封字段明确的英文面试邀请，经 IMAP 增量同步、真实 DeepSeek 四
Agent、三段审核和 SMTP Executor 回复，再次同步确认回复实际进入收件箱。

## 2. 已完成内容

### 2.1 Reply Agent

- 新增 `reply-input.v1` 与 `reply-output.v1` Pydantic Schema；
- 输入包含原始邮件、当前分类/抽取结果、关联申请和用户回复偏好；
- 输出只包含是否回复、核心正文、事实、不确定项和置信度；
- Prompt 明确禁止生成地址、主题、称呼、签名、MIME 头或调用 SMTP；
- `should_reply=false` 时不创建草稿和审核任务。

### 2.2 确定性格式化与草稿版本

- 收件人只取原邮件 `Reply-To` 或 `From`，不接受模型生成地址；
- 主题由规则添加一次 `Re:`，已有回复前缀时不重复添加；
- Formatter 统一添加称呼和用户签名；
- 拦截地址、主题、姓名和 Message-ID 中的换行注入；
- 同一邮件的草稿版本递增，重新生成会将旧 `PENDING` 草稿和审核任务标记为
  `EXPIRED`；
- 只有最新 `PENDING` 草稿可编辑、批准，旧版本和终态草稿不可修改或发送。

### 2.3 审核与工作流

- 每个可回复草稿创建 `SEND_REPLY/HIGH` 审核任务；
- 用户可以直接批准、提交修改后批准或拒绝；
- 模型原稿保存在 `generated_body`，人工稿保存在 `reviewed_body`；
- 批准只冻结草稿为 `APPROVED` 或 `MODIFIED_AND_APPROVED`，不调用 SMTP；
- LangGraph 升级为 `job-mail-workflow.v2`，申请关联和阶段审核完成后按需运行
  Reply Agent，并增加第三段可恢复草稿审核；
- SMTP 始终留在图外的确定性 Executor，工作流恢复不会触发发信。

### 2.4 SMTP 幂等 Executor

- 新增 `POST /api/v1/reply-drafts/{draft_id}/send`；
- 发送前重新校验用户归属、邮箱启用状态、最新草稿版本、批准状态、审核任务版本、
  收件人、主题和客户端幂等键；
- `action_executions` 记录每次 SMTP 尝试、开始/完成时间、Message-ID、结果和错误；
- 已成功请求重复提交直接返回原执行记录，不再次调用 SMTP；
- 同一幂等键在失败后重复提交也返回原结果；明确核对后可使用新幂等键重试
  `FAILED`；
- SMTP 提交期间断连标记 `UNKNOWN`，任何新幂等键都不会自动重试；
- 正在执行的不同请求返回冲突，防止并发双发；
- SMTP Adapter 只传输已格式化的 `EmailMessage`，不修改正文。

### 2.5 API

```http
POST /api/v1/emails/{email_id}/generate-reply
POST /api/v1/review-tasks/{task_id}/decision
POST /api/v1/reply-drafts/{draft_id}/send
```

生成接口支持显式指定 `workflow_run_id`，未指定时使用当前分析关联的可审计工作流。
发送请求必须同时提交草稿版本和调用方幂等键。

## 3. 验证结果

执行：

```powershell
conda run -n job-mail-agent python -m ruff check app tests
conda run -n job-mail-agent python -m pytest
```

结果：

- Ruff：通过；
- Pytest：`92 passed`；
- 覆盖 Reply Schema 约束、Header Injection、确定性格式化、SMTP 不改写正文、
  提交断连 `UNKNOWN`、成功请求幂等复用、`UNKNOWN` 禁止重试，以及三段
  LangGraph `interrupt/resume`。

### 3.1 真实 163 / DeepSeek / MySQL 闭环

- 测试邀请邮件入库 ID：`15`；
- Classification：`INTERVIEW`，`should_reply=true`；
- Extraction：公司 `Xinghai Technology`、岗位 `Backend Engineer`、面试时间
  `2026-08-05 14:00 Asia/Shanghai`；
- 新建申请 ID：`4`，最终阶段 `INTERVIEW`；
- 工作流 ID：`fd9e0117-b8b4-48e4-ae59-2873b7bcbc3d`，最终 `SUCCEEDED`；
- 三项审核：`CREATE_APPLICATION`、`UPDATE_APPLICATION_STAGE`、`SEND_REPLY`
  均为 `SUCCEEDED`；
- 草稿 ID：`1`，版本 `1`，状态 `APPROVED`；
- SMTP 执行 ID：`7`，`attempt_no=1`，状态 `SUCCEEDED`；
- 相同发送幂等键重复提交返回执行 ID `7`，未产生第二次 SMTP 调用；
- 回复经 IMAP 同步入库为邮件 ID `16`，解析状态 `SUCCEEDED`。

## 4. 实施问题与处理

| 问题 | 风险 | 处理 |
|---|---|---|
| 发送接口与已有基础草稿 PATCH 并存 | 绕过审核发送 | PATCH 只能编辑最新 `PENDING` 草稿；发送仍要求高风险审核已批准 |
| SMTP 连接在 DATA 提交期间中断 | 服务器可能已接收，盲目重试会双发 | 记录 `UNKNOWN` 并禁止自动重试 |
| 并发请求看到 `RUNNING` 执行 | 第一请求仍在发送时第二请求误判并重试 | 不擅自把活动请求改为 `UNKNOWN`，不同幂等键直接返回冲突 |
| 工作流恢复可能重放节点 | 重复创建草稿或误发 | 草稿按邮件版本化，审核任务有唯一幂等键；SMTP 完全位于图外 |
| 审核任务在 `rollback()` 后读取过期 ORM 属性 | 隐式开启事务，随后 `begin()` 报事务重入 | 回滚前冻结 `action_type/draft_id`，新增回归测试 |
| PowerShell 管道传入中文测试 Fixture 出现编码替换 | 抽取信息失真，产生不明确申请建议 | 拒绝该审核并取消运行，改用纯英文受控 Fixture 重新验收 |

## 5. 未完成边界

- 前端回复审核与发送页面属于第九阶段；
- SMTP `RUNNING` 的超时人工核对/对账接口可在后续运维增强中补充，本阶段选择
  “宁可阻塞，不自动重发”。

下一步进入第九阶段，开发 Vue 3 邮箱、分析、申请与回复审核页面。
