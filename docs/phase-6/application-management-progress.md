# 第六阶段进展：求职记录匹配与状态管理

> 开始日期：2026-07-28
> 完成日期：2026-07-28
> 阶段状态：已完成
> 当前里程碑：确定性候选查询、Application Agent、状态机与人工审核执行闭环

## 1. 阶段目标

将第五阶段持久化的当前邮件分析转化为可审核的求职申请建议：

```text
读取当前求职分析
→ 确定性查询并评分候选申请
→ Application Agent 比较候选并提出结构化建议
→ 创建申请关联/新建审核任务
→ 用户批准、修改或拒绝
→ 幂等执行关联或新建
→ 状态机校验阶段建议
→ 独立阶段审核
→ 更新申请并保存时间线事件
```

本阶段不整合 LangGraph checkpoint，不生成回复草稿、日程任务或归档动作；这些能力
仍按实施计划在后续阶段完成。

## 2. 已完成

- 新增 Application Agent 的 `application-input.v1` 和 `application-output.v1`
  Pydantic Schema、正式 Agent 与版本化 `v1` Prompt；
- Agent 只接收邮件分析事实和最多 10 个只读候选快照，不持有 Session 或 ORM
  对象，不具有创建、关联或修改申请的权限；
- 新增 `POST /api/v1/emails/{id}/match-application`；
- 候选查询限定当前用户，最多读取最近 100 条申请，再按公司、岗位、联系人邮箱、
  历史同发件人关联邮件和时间接近度确定性评分；
- 候选不足阈值时不交给模型伪造匹配；同公司多岗位、前两名分数接近或最高分不足时
  明确携带冲突原因；
- 校验 Agent 选择与排序只能引用输入候选，并禁止 Agent 改写 Extraction Agent
  提出的阶段；
- 每个当前分析版本使用稳定幂等键，只创建一个匹配审核任务；模型调用期间不持有
  数据库事务；
- 匹配、新建和阶段变更均为 `HIGH` 风险，默认进入 `PENDING` 审核，不因高置信度
  直接写入业务状态；
- 新增审核任务列表、详情与决策 API；
- 审核决策校验任务版本和目标申请版本，防止旧页面覆盖新状态；
- 批准关联或新建后写入 `action_executions`，重复提交已成功决策时返回既有执行，
  不重复创建申请或时间线事件；
- 关联/新建完成后，合法阶段建议生成独立
  `UPDATE_APPLICATION_STAGE` 审核任务，不在第一次审核中隐式修改阶段；
- 同阶段面试改期、二面通知等只写入时间线事件，不执行
  `INTERVIEW → INTERVIEW` 伪迁移；
- 非法倒退或跳转由确定性状态机拒绝，不创建可执行阶段任务；
- 阶段批准后同时保留 `previous_stage`、`proposed_stage`、
  `confirmed_stage`、来源邮件、工作流和审核任务信息；
- 拒信批准后将申请阶段更新为 `REJECTED`，并将业务状态更新为 `CLOSED`；
- 普通 `PATCH /job-applications/{id}` 仍不暴露 `current_stage` 和 `status`。

## 3. 状态机

当前 MVP 允许：

```text
APPLIED → ASSESSMENT
APPLIED → INTERVIEW
ASSESSMENT → INTERVIEW
INTERVIEW → OFFER
APPLIED/ASSESSMENT/INTERVIEW → REJECTED
APPLIED/ASSESSMENT/INTERVIEW/OFFER → WITHDRAWN
```

同阶段建议返回 `NO_CHANGE` 并转为时间线事件；其他未列出的迁移返回 `REJECTED`。
状态机只判断确定性合法性，不替代用户对关键阶段变化的确认。

## 4. 接口语义

```http
POST /api/v1/emails/{id}/match-application
GET  /api/v1/review-tasks
GET  /api/v1/review-tasks/{id}
POST /api/v1/review-tasks/{id}/decision
```

- `match-application` 要求邮件已有当前求职分析；无分析或 `NON_JOB` 返回 409；
- 返回候选、Agent 原始建议和审核任务 ID，`requires_human_confirmation`
  固定为 true；
- 冲突场景可在 `reviewed_payload` 中明确或修改申请 ID、申请版本、公司、岗位和
  建议阶段；
- `approve=false` 只记录拒绝结果，不执行申请写入；
- `approve=true` 先校验审核任务版本、目标资源版本、关联冲突和必要字段，再执行；
- 阶段变化始终需要第二个独立审核任务，避免“批准关联”被扩大解释为“批准改阶段”。

## 5. 验证证据

- Ruff：通过；
- 自动化测试：73 个通过；
- OpenAPI 已包含匹配与审核接口；
- 覆盖 7 条实施计划中的核心合法迁移；
- 覆盖同阶段事件与 `OFFER → INTERVIEW` 非法回退；
- 覆盖 Application Agent 版本化 Prompt、结构化输出和关联 ID 必填约束；
- 覆盖公司、岗位、联系人邮箱和时间因素组合评分，以及无关申请低分；
- 覆盖匹配接口只返回待审核建议、不直接暴露状态写入口；
- 使用本地真实 MySQL 和 Stub Application Agent 完成
  “匹配审核 → 新建申请 → 阶段审核 → `INTERVIEW` → 三条时间线事件”闭环；
- MySQL 闭环同时暴露并修复 `workflow_runs/review_tasks` 循环外键下的插入顺序，
  现显式先持久化工作流再创建审核任务；
- 联调结束后临时分析、申请、工作流、审核、事件和执行记录均已清理，相关表临时
  记录计数回到 0；
- 第六阶段未调用真实邮箱、未发送邮件，也未把真实邮件正文发送给模型。

## 6. 开发问题与处理

| 问题 | 原因 | 处理与结果 |
|---|---|---|
| Application Agent 需要申请上下文但不能拥有数据库写权限 | Agent 直接访问 ORM 会混淆推理和业务执行 | Service 确定性查询并转换为只读候选 Schema 后再调用 Agent |
| 同公司多岗位容易产生错误唯一匹配 | 公司一致不能证明岗位一致 | 分数接近或岗位缺失时显式标记冲突，始终进入人工审核 |
| 关联申请与修改阶段是两个不同授权 | 一次批准不应被扩大为多个关键动作 | 第一次审核只关联/新建，合法阶段建议生成第二个审核任务 |
| 同阶段通知不能伪造阶段迁移 | 二面或改期仍属于 `INTERVIEW` | 不更新 `current_stage`，只保存带来源和确认值的时间线事件 |
| 用户审核期间申请可能被其他请求更新 | 审核载荷可能基于旧版本 | 同时检查审核任务乐观锁和目标申请 `resource_version` |
| 重复提交审核可能重复创建业务数据 | HTTP 重试与页面重复点击不可避免 | 审核任务、执行记录使用幂等键，成功任务重复提交返回既有执行 |
| 工作流与待审核任务存在循环外键 | ORM 同批 flush 时可能先插入审核任务 | 先 flush `workflow_runs`，再插入 `review_tasks` 并回填待审核任务 ID；真实 MySQL 验证通过 |

## 7. 当前边界与下一步

- 当前 `phase-6-standalone.v1` 工作流记录用于持久化 Agent 轨迹和审核关系，不是
  第七阶段的完整 LangGraph 图；
- 当前只执行 `APPLICATION` 类型审核动作，任务、SMTP 和 IMAP Executor 尚未接入；
- 若阶段建议非法，系统保留 Agent 原始建议和校验结果，但不会创建阶段执行任务；
- 下一步进入第七阶段：将已独立验证的分类、抽取、申请匹配和审核节点整合进
  LangGraph，并接入 SQLite checkpointer、interrupt 与恢复幂等。
