# 基于大语言模型与多智能体协作的求职邮件智能管理系统设计稿

> 状态：总体设计稿 v0.3；四 Agent/12表骨架已收敛
> 日期：2026-07-16
> 目的：将 Email-AI-Agent 的概念验证链路演进为可服务化、可持久化、可审核的求职领域 Multi-Agent 系统。
> 约束：MVP 骨架以 `architecture-decisions.md` 为准；实验性增强仍可调整。
> 业务范围基线：`docs/requirements/mvp-scope-and-acceptance.md`；架构调整不得静默扩大或削弱该基线。

## 1. 设计背景

第一阶段已跑通 Email-AI-Agent 的完整链路：

```text
IMAP 收件
→ LLM 分类
→ LLM 摘要
→ LLM 回复
→ 终端人工确认
→ SMTP 发件
```

同时确认该项目本质上是一个固定 LangGraph Workflow，而不是严格意义上的 Multi-Agent 系统：

- 图内只有分类、摘要、回复三个固定节点；
- 节点不能动态选择工具或委派任务；
- 节点间没有专业 Agent 的 Handoff、反馈或协作；
- Human-in-the-Loop 只是阻塞式 `input()`；
- IMAP、SMTP、第二次审核和发送均在图外；
- 没有数据库、checkpoint、幂等、审计和服务化接口。

因此，正式系统不在参考项目中继续堆叠功能，而是保留已验证的协议经验和工作流思想，在自己的 FastAPI/LangGraph 项目中重新设计。

## 2. 设计目标与非目标

### 2.1 核心目标

1. 通过 IMAP 同步求职邮件，通过 SMTP 发送已审核回复。
2. 使用专业智能体协作完成求职邮件识别、信息抽取、申请匹配、状态建议和回复生成。
3. 将模型建议与确定性业务规则分离。
4. 通过持久化 Human-in-the-Loop 阻止模型直接执行高风险动作。
5. 将邮件处理结果关联到公司、岗位和求职申请时间线。
6. 支持面试、笔试、材料截止日期的任务和日程建议。
7. 保存模型运行、人工修改和最终动作的审计记录。
8. 通过对比实验验证 Multi-Agent 相对单模型和固定 Workflow 的价值。

### 2.2 非目标

- 不实现完整企业邮箱客户端。
- 不实现招聘平台或 ATS 的全部功能。
- 不允许模型绕过人工审核直接发信、改关键状态或创建日程。
- 不为了 Agent 数量把 MIME 解析、数据库 CRUD 等确定性逻辑包装成 Agent。
- 第一版不追求支持所有邮箱服务商，先以已验证的 163 测试邮箱完成闭环，再抽象 Provider。

## 3. 从 Email-AI-Agent 到正式系统的改造关系

| Email-AI-Agent 现状 | 正式系统设计 | 处理方式 |
|---|---|---|
| `main.py` 同步终端程序 | FastAPI API + 有界同步用例 + Vue 页面 | 重写 |
| `EmailState` 使用 `Dict[str, Any]` | Pydantic 强类型工作流状态 | 重写 |
| 分类→摘要→回复固定路径 | 确定性 Orchestrator 协调四个核心 Agent 与 HITL | 借鉴后重构 |
| 每封邮件重新编译图 | 应用启动时编译并复用图 | 重写 |
| `input()` 人工审核 | LangGraph interrupt/checkpoint + 审核表 | 重写 |
| IMAP 每次读取全部邮件 | UID/UIDVALIDITY 增量同步与幂等 | 改造后复用经验 |
| 只解析 `text/plain` | 安全 MIME/HTML/附件解析 | 重写 |
| SMTP 直接发送 | 仅执行已审核、带幂等键的发送命令 | 改造后复用协议经验 |
| Agent 与 SMTP 重复格式化 | Agent 只生成正文，Formatter 统一组装一次 | 重写 |
| `split("@")` 解析地址 | 标准邮件地址解析与校验 | 重写 |
| Gmail 草稿实际发送邮件 | 数据库存草稿；可选同步邮箱 Drafts | 不采用原实现 |
| DeepSeek 地址和模型硬编码 | DeepSeek/Qwen 统一模型适配层 | 重写 |
| 日志输出完整邮箱和 State | 结构化日志、追踪 ID、隐私脱敏 | 重写 |

参考项目只保留在 `references/Email-AI-Agent`，正式源码不得从该路径直接 import。

## 4. 总体架构草案

```text
┌──────────────────────── Vue 3 ────────────────────────┐
│ 邮件中心 │ 求职看板 │ 申请详情 │ 日程任务 │ 草稿审核 │
└──────────────────────────┬────────────────────────────┘
                           │ REST + 状态轮询
┌────────────────────── FastAPI ────────────────────────┐
│ 认证与账户 │ 邮件 API │ 申请 API │ 审核 API │ 统计 API │
│                                                        │
│ Application 用例编排                                    │
│ 手动 IMAP 同步 → MIME 解析 → 去重 → 触发 LangGraph       │
└──────────────────────────┬────────────────────────────┘
                           │
┌────────────── LangGraph Multi-Agent Runtime ──────────┐
│ Deterministic Orchestrator                              │
│   ├── Classification Agent                             │
│   ├── Extraction Agent                                 │
│   ├── Application Agent                                │
│   └── Reply Agent                                      │
│   Validation Node（确定性）                            │
│                                                        │
│ SQLite Checkpoint → Human-in-the-Loop → Resume         │
└──────────────────────────┬────────────────────────────┘
                           │ 仅通过受控 Tool/Service
┌──────────────────── Domain Services ──────────────────┐
│ ApplicationService │ PolicyEngine │ TaskService        │
│ DraftService │ CalendarService │ ActionExecutor        │
└──────────────────────────┬────────────────────────────┘
                           │
┌────────────────── Infrastructure ─────────────────────┐
│ MySQL │ SQLite Checkpoint │ IMAP/SMTP │ DeepSeek/Qwen  │
└────────────────────────────────────────────────────────┘
```

### 4.1 分层原则

- Vue 不直接访问模型、数据库或邮箱协议。
- FastAPI 负责身份、权限、API、任务编排和事务边界。
- LangGraph 负责需要推理、委派、反馈和暂停恢复的流程。
- Agent 默认只能使用只读工具或生成“建议动作”。
- 所有数据库写入、SMTP 发送、日程创建由确定性服务执行。
- 关键动作必须具有用户授权、幂等键和审计记录。

## 5. Multi-Agent 判定标准

本系统中的专业 Agent 必须同时具备：

1. 独立任务目标和系统 Prompt；
2. 独立、最小化的上下文；
3. 强类型输入输出 Schema；
4. 与职责相匹配的受控工具；
5. 自己的验证、重试或澄清逻辑；
6. 通过共享状态或 Handoff 与其他 Agent 协作；
7. 可独立测试和评估。

仅调用一次 LLM 的简单函数可以作为工作流节点，但不应为了论文表述强行称为自治 Agent。MVP 只保留课题明确要求的四个核心 Agent，不实现 LLM Supervisor 和 Review Agent。

## 6. Agent 团队设计

为了控制毕业设计范围，MVP 采用 **确定性 Orchestrator + 4 个核心 Agent**。四个 Agent 分别负责邮件分类、信息抽取、求职状态管理和回复生成。Schema、状态机、时间歧义和动作风险由确定性 Validation Node 检查。

### 6.1 Deterministic Orchestrator

| 项目 | 设计 |
|---|---|
| 目标 | 根据结构化状态和确定性规则协调专业 Agent，决定下一步、一次重试和人工审核 |
| 输入 | 邮件处理状态、Agent 结果、置信度、错误和重试次数 |
| 实现 | LangGraph 条件边、`Command` 和路由函数，不调用模型 |
| 输出 | `next_agents`、路由原因、是否暂停、待补充信息 |
| 禁止 | 直接写数据库、直接发送邮件、编造专业 Agent 结果 |

输入模糊或多个结果冲突时直接进入 Human-in-the-Loop，不再增加审核模型调用。

### 6.2 Classification Agent（邮件分类）

职责：

- 判断邮件是否与求职相关；
- 分类为 `INTERVIEW`、`ASSESSMENT`、`OFFER`、`REJECTION` 等；
- 判断优先级、是否需要后续动作和是否可能需要回复；
- 返回证据、置信度和不确定项。

示例输出：

```json
{
  "is_job_related": true,
  "category": "INTERVIEW",
  "priority": "HIGH",
  "should_reply": true,
  "required_capabilities": ["extract", "match_application", "draft_reply"],
  "confidence": 0.96,
  "evidence": ["邮件明确邀请候选人参加线上面试"]
}
```

### 6.3 Extraction Agent（结构化信息抽取）

职责：

- 提取公司、岗位、联系人、阶段、时间、地点、链接、材料和截止日期；
- 调用时间规范化、时区转换、附件文本提取等工具；
- 区分原始文本、标准化值和不确定信息；
- 发现冲突时标记待人工确认。

可用工具：

- `normalize_datetime(raw_text, timezone)`
- `extract_attachment_text(attachment_id)`
- `resolve_company_alias(name)`
- `validate_meeting_url(url)`（只校验，不自动打开）

输出必须保留原始证据，例如：

```json
{
  "company": {"value": "星海科技", "source": "邮件签名"},
  "position": {"value": "后端开发工程师", "source": "邮件主题"},
  "event_time": {
    "raw": "本周五下午两点",
    "normalized": "2026-07-17T14:00:00+08:00",
    "confidence": 0.88
  },
  "missing_fields": []
}
```

### 6.4 Application Agent（求职记录与状态）

职责：

- 使用公司、岗位、联系人和时间查询已有申请；
- 比较同公司多岗位候选；
- 输出唯一匹配、多个候选或未匹配；
- 基于邮件类别提出求职阶段变更建议；
- 查询当前时间线，避免重复事件和非法状态回退。

只读工具：

- `search_applications(company, position, time_range)`
- `get_application(application_id)`
- `get_application_timeline(application_id)`
- `check_stage_transition(current_stage, proposed_stage)`

该 Agent 只能提出：

```json
{
  "match_status": "MATCHED",
  "application_id": 1024,
  "proposed_stage": "INTERVIEW",
  "confidence": 0.91,
  "requires_human_confirmation": false,
  "reason": "公司、岗位和流程时间一致"
}
```

实际写数据库由 `ApplicationService` 在规则校验或人工确认后执行。

### 6.5 Reply Agent（回复生成）

职责：

- 根据 Classification、Extraction 和 Application 结果再次判断是否应回复；
- 读取用户署名、语气偏好和申请上下文；
- 只生成回复正文，不添加主题、称呼和签名；
- 列出使用的事实和仍不确定的表述。

输出：

```json
{
  "should_reply": true,
  "body": "感谢您的面试邀请。我确认可以参加……",
  "facts_used": ["面试时间：2026-07-17 14:00"],
  "uncertain_claims": [],
  "confidence": 0.94
}
```

最终主题、称呼、签名和 MIME 由确定性 `EmailFormatter` 统一组装一次。

### 6.6 Validation Node（确定性校验，不是 Agent）

职责：

- 校验四个 Agent 输出是否通过 Pydantic Schema；
- 校验分类枚举、置信度、字段证据和必填信息；
- 校验时间是否缺少年份、日期或时区；
- 校验申请阶段迁移是否合法；
- 校验草稿收件人、事实引用和不确定项；
- 判断保存结果、原 Agent 重试一次或进入 Human-in-the-Loop。

Validation Node 不调用模型，规则稳定且容易单元测试。

## 7. 协作工作流设计

```text
确定性预处理
  ↓
Deterministic Orchestrator
  ↓
Classification Agent
  ├── NON_JOB → 保存分类 → 结束/提出归档建议
  ├── 低置信度 → Human-in-the-Loop
  └── JOB_RELATED
          ↓
    Extraction Agent
          ↓
    Application Agent
          ↓
    Orchestrator 根据 should_reply 决定
          ├── Reply Agent（需要回复）
          └── 跳过回复（无需回复）
          ↓
      Validation Node
          ├── PASS → 保存结果/生成审核任务
          ├── RETRY → 原 Agent，最多 1 次
          └── HUMAN_REVIEW → Human-in-the-Loop
                          ↓
                    用户接受/修改/拒绝
                          ↓
                    Action Planner
                          ↓
                    确定性 Executor
              数据库更新 / SMTP / 日程创建
```

### 7.1 可并行部分

第一版优先采用清晰的顺序流程，不实现并行 Agent。后续性能优化时，才考虑在 Classification 后并行预加载只读上下文：

- 用户偏好和申请候选的预加载；

Application Agent 必须等待核心抽取结果，Reply Agent 必须等待申请上下文，不能为了展示并行而破坏依赖关系。

### 7.2 校验与升级

| 校验问题 | 处理方式 |
|---|---|
| Schema 格式错误 | 原 Agent 重试一次 |
| 时间或地点缺失/冲突 | Human-in-the-Loop |
| 申请记录匹配冲突 | Human-in-the-Loop |
| 回复包含不确定事实 | Human-in-the-Loop |
| 多个 Agent 结果互相矛盾 | Human-in-the-Loop |

## 8. 强类型 LangGraph State 草案

```python
class JobMailGraphState(BaseModel):
    run_id: str
    account_id: int
    email_id: int

    parsed_email: ParsedEmail
    classification: ClassificationResult | None = None
    extraction: ExtractionResult | None = None
    application: ApplicationDecision | None = None
    draft: DraftResult | None = None
    validation: ValidationResult | None = None

    active_agent: str | None = None
    retry_counts: dict[str, int] = Field(default_factory=dict)
    errors: list[AgentError] = Field(default_factory=list)

    review_task_ids: list[str] = Field(default_factory=list)
    human_decision: HumanDecision | None = None
    approved_review_task_ids: list[str] = Field(default_factory=list)
```

设计要求：

- 原始模型建议与人工确认结果分开；
- Agent 不直接保存 ORM 对象和邮箱密码；
- 节点只返回自己负责的状态片段；
- 每个结果包含 Schema 版本、模型、置信度和证据；
- 重试次数、错误和审核状态可持久化恢复。

## 9. Human-in-the-Loop 设计

### 9.1 必须暂停的场景

- 即将通过 SMTP 发送邮件；
- 关键求职阶段发生变化且置信度不足；
- 新建求职申请或存在多个匹配候选；
- 创建、修改或删除日程；
- 自动归档邮件；
- Validation Node 检测到事实冲突或隐私风险。

### 9.2 审核状态

```text
PENDING → APPROVED
        → MODIFIED_AND_APPROVED
        → REJECTED
        → CANCELLED
        → EXPIRED
```

数据库需要保存：模型原稿、人工修改稿、审核人、审核时间、决策原因和后续执行结果。

### 9.3 恢复流程

```text
LangGraph interrupt
→ checkpoint 保存 thread_id/run_id
→ FastAPI 返回审核任务
→ Vue 展示邮件、证据、Agent 结果和动作
→ 用户提交决定
→ FastAPI 校验权限和当前版本
→ LangGraph resume
→ Executor 再次执行幂等和安全校验
```

## 10. 确定性服务与工具边界

| 服务 | 职责 | Agent 权限 |
|---|---|---|
| `EmailSyncService` | IMAP 增量同步、UID 去重 | 不由 Agent 直接控制 |
| `MimeParser` | MIME/HTML/附件安全解析 | 只读调用 |
| `ApplicationQueryTool` | 查询申请和时间线 | 只读 |
| `ApplicationService` | 创建申请、变更阶段 | 仅 Executor 在获批后调用 |
| `PolicyEngine` | 状态迁移、置信度、动作规则 | Agent 可查询，不能绕过 |
| `DraftService` | 保存模型草稿和人工版本 | 工作流可写草稿，不等于发送 |
| `EmailFormatter` | 主题、地址、称呼、签名、MIME | 确定性调用且只执行一次 |
| `SmtpExecutor` | 发送已批准邮件 | 仅获批 Action 可调用 |
| `CalendarService` | 创建/更新日程 | 仅获批 Action 可调用 |
| `AuditService` | 保存运行、审核和动作日志 | 所有关键步骤调用 |

## 11. 数据模型

MVP 精简逻辑 ER、12 张表的职责、字段、约束、迁移顺序和验收清单已经收敛，见 `docs/database/database-er-design.md`。

数据模型的核心边界是：

```text
emails（邮件事实）
→ email_analyses（模型推断）
→ review_tasks（建议动作与审核决定）
→ action_executions（执行结果）
```

LangGraph SQLite checkpoint 不属于业务 ER，不作为邮件、申请、审核或动作的真相源。

## 12. FastAPI 接口草案

```text
POST   /api/email-accounts
POST   /api/email-accounts/{id}/test
POST   /api/email-accounts/{id}/sync
GET    /api/emails
GET    /api/emails/{id}
POST   /api/emails/{id}/analyze
GET    /api/workflow-runs/{run_id}

GET    /api/applications
GET    /api/applications/{id}
PATCH  /api/applications/{id}

GET    /api/reviews?status=PENDING
GET    /api/reviews/{id}
POST   /api/reviews/{id}/approve
POST   /api/reviews/{id}/modify-and-approve
POST   /api/reviews/{id}/reject

GET    /api/tasks
GET    /api/calendar-events
GET    /api/automation-rules
POST   /api/automation-rules
```

所有修改类接口必须校验用户、资源版本和幂等键。

## 13. 源码目录

正式项目采用仓库根目录下的 `backend/` 与 `frontend/`，不再放入预留 `src/`。后端分层和完整目录见 `docs/architecture/architecture-decisions.md`。

## 14. 分阶段实施路线

### 阶段 A：正式后端骨架

- FastAPI、配置、日志、异常和 MySQL 连接；
- 邮件/账户/申请/审核基础表；
- Provider 接口和 163 适配；
- 脱敏测试邮件 Fixture。

### 阶段 B：离线 Multi-Agent

- 强类型 State；
- 确定性 Orchestrator 与四个核心 Agent；
- 先使用 Fixture，不连接真实邮箱；
- 结构化输出、错误处理、重试和 tracing；
- 单模型与固定 Workflow 基线测试。

### 阶段 C：邮件与求职记录闭环

- IMAP 增量同步；
- 公司、岗位、申请和时间线；
- Application Agent 数据库只读工具；
- 草稿、审核和 SMTP Executor。

### 阶段 D：Vue 与 Human-in-the-Loop

- 邮件中心、求职看板、申请详情；
- 待审核草稿页面；
- interrupt/checkpoint 暂停恢复；
- 审核差异和动作审计。

### 阶段 E：日程、统计与实验

- 面试/笔试/材料任务；
- 日程建议与确认执行；
- 统计图表；
- 消融实验、性能测试和论文材料。

## 15. 实验与论文验证设计

### 15.1 对比方案

| 方案 | 描述 |
|---|---|
| Baseline A | 单次 LLM Prompt 完成分类、抽取、状态和回复 |
| Baseline B | Email-AI-Agent 式固定分类→摘要→回复 Workflow |
| Proposed | 确定性 Orchestrator + 四个核心 Agent + Validation + HITL |

### 15.2 指标

- 分类 Accuracy、Macro-F1；
- 结构化抽取 Precision、Recall、F1；
- 申请匹配准确率；
- 状态建议准确率；
- 回复事实一致性和幻觉率；
- 人工修改率；
- 时间/截止日期遗漏率；
- 端到端任务成功率；
- 平均调用次数、Token、延迟和成本。

至少准备面试、笔试、Offer、拒信、材料补充、状态通知、非求职邮件和模糊/冲突场景的脱敏测试集。对比实验用于证明 Multi-Agent 带来的收益是否足以覆盖额外调用成本。

## 16. 安全与可靠性要求

- 邮箱授权码、API Key 不进入数据库明文和日志；
- 发给模型的数据遵循最小必要原则；
- 邮箱地址和正文默认在日志中脱敏；
- HTML、链接和附件按不可信输入处理；
- 所有外部写动作要求审核、权限和幂等；
- Agent 循环有最大次数、超时和成本上限；
- 低置信度、冲突或 Schema 校验失败进入人工处理；
- 保存原始建议、人工决定和最终执行结果，支持审计。

## 17. 设计决策状态

已收敛：

1. MySQL 保存业务数据，官方 SQLite saver 保存 MVP checkpoint；
2. 有界手动操作同步执行，不引入 Celery/RQ；
3. DeepSeek 首实现，Qwen 通过统一接口保留替换能力；
4. MVP 实际验证一个 163 测试账户；
5. MVP 只使用本地 `tasks` 和日历视图；
6. Vue 使用 REST + 状态轮询；
7. MVP 不启用 LangGraph Store；
8. 使用确定性 Orchestrator + 四个核心 Agent，不实现 Review Agent 和 LLM Supervisor；
9. 业务表精简为12张，建议动作与审核合并为 `review_tasks`；
10. 低优先级归档由 `automation_rules`、Policy 和 IMAP Executor 完成。

仍待实验阶段确定：

1. 测试集最终规模和标注规范；
2. Qwen 是否进入 MVP 备用模型实测；
3. 多实例部署时的共享 checkpointer；
4. 定时同步、SSE、第二 Provider 和外部日历等增强能力。

这些决策应通过小型技术验证后确定，不在本设计稿中假定为事实。

## 18. 参考资料

- Email-AI-Agent：<https://github.com/parthshr370/Email-AI-Agent>
- LangChain Multi-Agent：<https://docs.langchain.com/oss/python/langchain/multi-agent>
- LangGraph Overview：<https://docs.langchain.com/oss/python/langgraph/overview>
- LangGraph Workflows and Agents：<https://docs.langchain.com/oss/python/langgraph/workflows-agents>
