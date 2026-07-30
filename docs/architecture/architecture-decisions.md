# 正式系统项目骨架架构决策

> 状态：第二阶段骨架决策已收敛
> 版本：v1.1
> 日期：2026-07-27
> 适用范围：MVP 后端、前端、工作流和基础设施骨架
> 业务基线：`docs/requirements/mvp-scope-and-acceptance.md`

## 1. 决策目标

本文只冻结会直接影响项目目录、依赖、数据库迁移和首批接口的架构决策。没有证据表明必须提前确定的内容继续保持可替换，避免为了“架构完整”引入超出毕业设计范围的基础设施。

决策遵循以下原则：

- MySQL 是业务数据唯一真相源。
- LangGraph 负责有状态推理、路由、受限重试和暂停恢复。
- Agent 只读取受控上下文并产生结构化结果或建议动作。
- FastAPI 业务服务负责权限、事务、状态机和动作执行。
- 外部写动作必须经过审核、幂等和审计。
- 优先完成可复现的单机 MVP，不提前引入分布式系统复杂度。

## 2. 决策总览

| 编号 | 决策 | MVP 结论 |
|---|---|---|
| AD-01 | 仓库结构 | 前后端单仓：`backend/` + `frontend/` |
| AD-02 | 后端分层 | API、Application、Domain、Agents、Workflows、Infrastructure |
| AD-03 | 数据库访问 | MySQL 8 + SQLAlchemy 2 + PyMySQL + Alembic，同步访问 |
| AD-04 | 接口执行模型 | 有界操作同步执行；不引入 Celery/RQ |
| AD-05 | API 与前端通信 | REST `/api/v1` + 状态轮询 |
| AD-06 | 身份与权限 | 单用户本地演示，不实现登录系统 |
| AD-07 | 模型接入 | 统一 `LLMProvider`；DeepSeek 首实现，Qwen 可替换 |
| AD-08 | 多智能体拓扑 | 确定性 Orchestrator + 4 个核心 Agent |
| AD-09 | Tool 边界 | Agent 只使用只读查询和纯校验工具 |
| AD-10 | 状态与持久化 | State 管单次运行，SQLite checkpoint 管恢复，MySQL 管业务事实 |
| AD-11 | LangGraph Store | MVP 不启用，不复制 MySQL 权威数据 |
| AD-12 | Human-in-the-Loop | `review_tasks` + `interrupt/resume` |
| AD-13 | 外部动作一致性 | 独立 Executor + 动作幂等键 + `UNKNOWN` 结果 |
| AD-14 | Prompt 与结构化输出 | 版本化 Prompt 文件 + Pydantic Schema |
| AD-15 | 时间与隐私 | UTC 持久化、保留原文/时区；最小化模型输入和日志 |
| AD-16 | 测试策略 | 单元、集成、工作流和端到端四层测试 |
| AD-17 | 数据模型 | 13 张业务表，合并过细实体但保留事实/建议/审核/执行边界 |

### 2.1 用户提供的 LangChain 参考如何落地

| 能力 | MVP 决策 | 项目用途 |
|---|---|---|
| Message / Prompt | 必须使用 | 每个 Agent 独立 Prompt，统一消息构造与版本记录 |
| Tools | 受限使用 | 只读业务查询、时间规范化和纯校验；不暴露 SMTP 等写动作 |
| Structured Output | 必须使用 | 分类、抽取、申请建议和回复元数据通过 Pydantic Schema |
| Agent | 使用专业 Agent | 每个 Agent 具有独立目标、上下文、工具、输出和测试 |
| Middleware | 最小使用 | 请求 ID、日志脱敏和运行上下文；HITL 由 Graph 实现 |
| Memory | 分层使用 | 单次运行用 State，恢复用 checkpoint，业务事实用 MySQL |
| RAG | 不进入 MVP | 当前邮件、申请和用户数据可以通过精确查询获得，不需要向量检索 |

### 2.2 用户提供的 LangGraph 参考如何落地

- `StateGraph`、State、Node、Edge 和条件路由作为工作流基础。
- Retry、Timeout、Error Handling 和最大重试次数进入节点执行规范。
- Checkpointer、`thread_id`、`interrupt()` 和 `Command(resume=...)` 支撑审核恢复。
- Tool Calling 只用于 AD-09 规定的受控工具。
- MVP 前端不展示 Token 级消息流，先通过状态轮询展示节点进度。
- 专业 Agent 初期可以是普通节点；只有内部流程复杂时再拆为 SubGraph。
- Runtime Context 注入 `user_id`、`request_id`、模型配置和只读服务端口，避免全局变量和硬编码。
- Orchestrator、共享 State 和 HITL 体现多 Agent 协作，不为了展示并行而破坏依赖顺序。

## 3. AD-01：前后端单仓结构

### 决策

正式代码采用：

```text
job-mail-agent/
├── backend/
├── frontend/
├── docs/
├── experiments/
├── references/
└── tests/fixtures/
```

早期预留的根目录 `src/` 已确认没有业务代码并移除；不得把正式代码放入 `references/`。

### 原因

- Vue 和 FastAPI 的构建、依赖与测试方式不同，分开更清晰。
- 单仓便于毕业设计演示、版本管理和接口联调。
- 不采用多仓库，避免增加发布与同步成本。

## 4. AD-02：后端分层与目录

### 决策

```text
backend/
├── app/
│   ├── api/
│   │   └── v1/                  # FastAPI 路由和依赖
│   ├── application/             # 用例编排、事务边界
│   ├── domain/                  # 枚举、领域模型、状态机和策略
│   ├── agents/                  # 专业 Agent 及其 Schema
│   ├── workflows/               # LangGraph State、节点、路由和恢复
│   ├── infrastructure/
│   │   ├── db/                  # ORM、Session、Repository 实现
│   │   ├── email/               # IMAP/SMTP Provider
│   │   ├── llm/                 # DeepSeek/Qwen 适配
│   │   ├── checkpoint/          # LangGraph checkpointer 配置
│   │   └── security/            # 凭据加密、密码和令牌
│   ├── prompts/                 # 版本化 Prompt
│   ├── core/                    # 配置、日志、异常、启动生命周期
│   └── main.py
├── migrations/                  # Alembic
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── workflow/
│   └── e2e/
├── pyproject.toml
└── .env.example
```

### 边界

- `api` 不直接调用 ORM、IMAP、SMTP 或模型。
- `application` 调用领域规则、工作流和基础设施端口。
- `domain` 不依赖 FastAPI、LangChain、SQLAlchemy 或邮箱协议。
- `agents` 不持有数据库 Session 和邮箱凭据。
- `infrastructure` 实现领域/application 定义的端口。
- ORM 模型只存在于 `infrastructure/db`，不得作为 LangGraph State 传递。

## 5. AD-03：MySQL、ORM 与迁移

### 决策

- 数据库：MySQL 8.x，InnoDB，字符集 `utf8mb4`。
- ORM：SQLAlchemy 2.x。
- DBAPI：PyMySQL。
- 迁移：Alembic。
- MVP 使用同步 SQLAlchemy Session。
- 连接开启 `pool_pre_ping`，并配置合理的 `pool_recycle`。
- 所有 DDL 通过 Alembic 迁移执行，不在应用启动时调用 `create_all()` 代替迁移。

SQLAlchemy 官方 MySQL 文档将 PyMySQL 列为推荐方言之一，并提供 `mysql+pymysql` 连接方式；Alembic 是 SQLAlchemy 的迁移工具。MVP 的 `imaplib`、`smtplib` 和主要模型调用均包含阻塞式 I/O，统一同步边界比混合 async Session 更容易测试和排错。

### 不选择

- 不使用 SQLite 代替业务 MySQL。
- 不在 MVP 中使用 SQLAlchemy AsyncSession/`asyncmy`。
- 不直接拼接 SQL。
- 不引入第二套业务数据库。

## 6. AD-04：接口执行模型与后台任务

### 决策

- 邮箱连接测试、有限数量的手动同步和单封邮件分析先同步执行。
- 使用普通 `def` FastAPI 路由承载阻塞式基础设施调用。
- 前端对明确的运行状态接口进行轮询。
- MVP 不使用 FastAPI `BackgroundTasks` 承载必须可靠恢复的工作流。
- MVP 不引入 Celery、RQ、Redis 或 RabbitMQ。
- 第十阶段采用随 FastAPI 生命周期启动的轻量轮询线程；账户的下次执行时间写入
  MySQL，并通过 `SELECT ... FOR UPDATE SKIP LOCKED` 抢占到期账户。
- 轮询器只触发现有幂等 IMAP 同步和 LangGraph 工作流。业务结果仍由 MySQL 与
  加密 checkpoint 保证，进程内线程不保存任务真相。

### 原因

FastAPI 会把普通 `def` 路由放入线程池，适合调用不支持 `await` 的阻塞库。`BackgroundTasks` 是进程内机制，不是持久队列；工作流可靠恢复由 LangGraph checkpoint 和 MySQL 运行记录承担，不能把内存后台任务当作可靠性保证。

### 升级条件

只有出现以下情况才升级为独立调度器或任务队列：

- 部署从本机单实例扩展到多主机；
- 单次处理量明显超过有界手动同步；
- 需要多 Worker 抢占、重试或任务限流；
- 实测请求时长影响演示稳定性。

## 7. AD-05：API 与前端通信

### 决策

- API 前缀统一为 `/api/v1`。
- 使用 REST 接口。
- 分析接口返回业务结果或 `workflow_run_id`、状态和待审核信息。
- Vue 使用轮询获取工作流状态，不在 MVP 中引入 WebSocket。
- SSE 可作为后续增强，不影响领域和工作流接口。

### 初始资源

```text
/api/v1/email-accounts
/api/v1/emails
/api/v1/workflow-runs
/api/v1/applications
/api/v1/tasks
/api/v1/drafts
/api/v1/reviews
/api/v1/actions
/api/v1/automation-rules
/api/v1/reminders
```

## 8. AD-06：单用户演示边界

### 决策

- MVP 只面向本机单用户演示，不实现登录、JWT、注册和角色权限。
- 创建一个演示用户，使用配置中的 `DEMO_USER_ID` 作为运行上下文。
- 业务表仍保留 `user_id`，避免后续扩展时重构数据模型。
- MVP 不部署到公网；如果后续公开部署，认证是部署前置条件。

### 原因

登录并非求职邮件核心闭环。暂缓认证可以减少密码哈希、Token、登录页和权限测试，同时保留清晰的数据归属。

## 9. AD-07：统一模型适配层

### 决策

业务代码只依赖：

```text
LLMProvider
├── invoke(messages, options)
├── invoke_structured(messages, output_schema, options)
└── health_check()
```

- DeepSeek 作为首个实现和默认测试模型。
- Qwen 保留第二实现位置，不要求在首个纵向切片同时完成。
- Provider、模型名、Base URL、超时和重试从配置加载。
- API Key 只从环境变量或密钥机制加载。
- Agent 不直接实例化供应商 SDK。

## 10. AD-08：多智能体拓扑

### 决策

MVP 使用确定性 Orchestrator 协调四个核心 Agent：

```text
Classification Agent
    ↓
Extraction Agent
    ↓
Application Agent
    ↓
Reply Agent（按需）
    ↓
Deterministic Validation
    ├── PASS
    └── HUMAN_REVIEW
```

### 说明

- Orchestrator 是 LangGraph 路由逻辑，不调用 LLM。
- Agent 是否执行由分类、缺失字段、`should_reply` 和审核规则决定。
- Classification、Extraction、Application 和 Reply 分别对应课题明确要求的四类智能体。
- Schema、状态机、证据完整性、时间歧义和动作风险由确定性 Validation Node 校验。
- 不实现 Review Agent 和 LLM Supervisor，减少模型调用、Prompt 和异常分支。

### Agent 判定

每个专业 Agent 必须具有：

- 独立目标和 Prompt；
- 最小上下文；
- 强类型输入输出；
- 受控工具；
- 校验或错误回退；
- 独立运行记录和测试。

只包装一次模型调用、没有独立职责的函数仍称为节点，不强行称为 Agent。

## 11. AD-09：Tool 与外部动作边界

### Agent 可使用

- 查询申请候选；
- 查询申请时间线；
- 查询用户回复偏好和已有关联申请；
- 日期时间规范化；
- 邮件地址解析；
- 状态迁移合法性检查；
- URL 格式校验；
- 查询自动化规则。

### Agent 不可使用

- IMAP 同步或修改邮件状态；
- SMTP 发送；
- 创建/修改申请；
- 创建/修改任务或日程；
- 归档或删除邮件；
- 写入审核结论；
- 读取邮箱授权码或模型 API Key。

参考资料中“IMAP、SMTP、数据库、日历都可做 Tool”是 LangChain 能力层面的示例，不等于本项目应把所有能力暴露给模型。读取类能力可以封装成 Tool，外部写动作必须留在确定性 Executor。

## 12. AD-10：三层状态与持久化

### 决策

```text
LangGraph State
  └── 单次 workflow run 内的结构化工作状态

LangGraph Checkpoint
  └── 按 thread_id 保存 State 快照，用于 interrupt/resume 和故障恢复

MySQL
  └── 邮件、分析、申请、任务、草稿、审核和动作的权威业务记录
```

### MVP checkpointer

- 使用官方 `langgraph-checkpoint-sqlite` 的持久化 saver。
- checkpoint 数据库放在运行数据目录，不提交 Git。
- `thread_id` 使用 `workflow_runs.thread_id` 中保存的 UUID。
- checkpoint 序列化内容需要加密，密钥从环境变量读取。
- State 只保存业务 ID、结构化结果和必要上下文，不保存邮箱授权码、API Key、ORM Session 或完整附件。

### 原因

LangGraph 官方 checkpointer 集成目前列出内存、SQLite、PostgreSQL、MongoDB、Redis 等实现，没有官方 MySQL saver。为 MySQL 自行实现 `BaseCheckpointSaver` 会增加与毕业设计核心无关的维护风险；引入 PostgreSQL 又会形成第二套服务端数据库。因此单机 MVP 使用 SQLite 保存框架 checkpoint，MySQL 继续保存全部业务事实。

SQLite checkpoint 只属于工作流运行基础设施，不纳入业务 ER 图。未来若部署为多进程/多实例服务，再把 checkpointer 替换为受支持的共享持久化后端。

## 13. AD-11：LangGraph Store 暂不进入 MVP

### 决策

MVP 不编译或配置 LangGraph Store。

用户提供的 Store 参考映射调整为：

| 参考内容 | MVP 真相源 | 处理 |
|---|---|---|
| 用户回复风格、语言偏好 | MySQL `users.reply_preferences` | 运行时查询并注入 Context |
| 用户基础信息 | MySQL `users` | 不复制到 Store |
| 简历信息 | MVP 范围外 | 后续设计独立表和隐私策略 |
| 公司和岗位 | MySQL `job_applications` | MVP 直接保存在申请记录 |
| Offer/面试回复模板 | 版本化 Prompt 或后续 `reply_templates` | MVP 不做长期记忆 |

### 原因

LangGraph Store 适合跨 thread 的动态长期记忆和语义检索，但本项目中的用户偏好、公司、岗位和模板都是确定、可编辑、可审计的数据。将它们同时保存在 Store 和 MySQL 会产生双写与一致性问题。

如果后期引入 Store，只允许保存可重建的衍生记忆，例如：

- 从多次人工修改中归纳的非权威回复风格；
- 可删除的语义检索索引；
- 不参与权限和状态判断的个性化缓存。

任何 Store 内容都不得作为发送邮件、修改申请阶段或创建日程的唯一依据。

## 14. AD-12：Human-in-the-Loop 一致性

### 决策

HITL 由两部分共同实现：

```text
LangGraph interrupt/checkpoint
  └── 保存工作流暂停位置

MySQL review_tasks
  └── 同表保存建议动作、审核决定和当前状态
```

- `workflow_runs.thread_id` 关联 checkpoint。
- 进入中断前，先以幂等方式创建 `review_tasks`。
- `interrupt()` payload 只携带 JSON 可序列化的动作 ID 和展示摘要。
- 用户提交决定时校验用户、动作状态和资源版本。
- MySQL 审核成功后使用相同 `thread_id` 恢复工作流。
- 恢复节点可能从头执行，因此 `interrupt()` 前的写入必须是幂等 upsert。
- 非幂等外部动作放在恢复后的独立 Executor 节点。

MySQL 是审核状态的业务真相源；checkpoint 丢失时不得仅凭审核记录直接猜测图执行位置，而应进入人工恢复或重建流程。

## 15. AD-13：外部动作与幂等

### 决策

所有外部写动作采用：

```text
ReviewTask(PENDING)
→ 用户决定或显式自动化规则
→ ActionExecution(PENDING)
→ Executor
→ SUCCEEDED / FAILED / UNKNOWN
```

- 每个逻辑动作具有唯一 `idempotency_key`。
- Executor 先以原子方式取得执行权，再调用业务服务或外部系统。
- 已 `SUCCEEDED` 的动作不会再次执行。
- SMTP 在“服务器可能已接受、客户端却未收到确认”的情况下标记为 `UNKNOWN`。
- `UNKNOWN` 不自动重试，必须先由用户核对。
- 数据库状态更新和任务创建可以通过事务与唯一约束实现可重试幂等。

不宣称 SMTP 具有框架无法提供的 Exactly Once 保证。

## 16. AD-14：Prompt、结构化输出与版本

### 决策

- 每个 Agent 使用独立 Prompt。
- Prompt 保存在 `backend/app/prompts/`，纳入 Git。
- 每次运行记录 `prompt_version`、模型供应商和模型名。
- 分类、抽取、匹配建议和回复元数据使用 Pydantic Schema。
- 模型自由文本不能直接参与路由和数据库状态变更。
- Schema 校验失败执行有限重试，仍失败则进入人工处理。
- 回复正文可以是文本，但必须配套 `facts_used`、`uncertain_claims` 等结构化字段。

## 17. AD-15：时间、敏感数据与日志

### 时间

- 数据库标准时间统一保存 UTC。
- 同时保存原始时间文本和解析时区。
- API 输出 ISO 8601 带时区值。
- 用户默认时区保存在 `users.timezone`。
- 模糊时间不得自动成为已确认任务。

### 敏感数据

- MVP 邮箱授权码只通过 `credential_ref` 从环境变量或密钥配置读取，不写入数据库。
- 模型 API Key 不入库。
- HTML、链接和附件均按不可信输入处理。
- 发给模型的正文按任务裁剪，默认不发送不需要的历史引用和附件。

### 日志

- 使用 `request_id`、`workflow_run_id`、`thread_id` 和业务实体 ID 关联日志。
- 邮箱地址脱敏。
- 不记录授权码、API Key、完整 checkpoint、完整正文和完整模型输入。
- 需要审计的模型结果保存到受控业务表，而不是依赖普通应用日志。

## 18. AD-16：测试结构

### 单元测试

- MIME 和地址解析；
- 日期规范化；
- 分类/阶段枚举；
- 状态机；
- 幂等键；
- Pydantic Schema；
- HTML 清洗。

### 集成测试

- MySQL Repository 和 Alembic；
- 163 IMAP/SMTP Provider；
- LLMProvider 结构化输出；
- SQLite checkpoint 暂停、进程重启和恢复；
- `credential_ref` 安全配置读取。

### 工作流测试

- `NON_JOB` 提前结束；
- 四个 Agent 按确定性路由执行；
- 结构化校验失败进入有限重试或人工审核；
- 低置信度进入人工审核；
- 审核批准、修改和拒绝；
- 重复 resume 不重复执行动作。

### 端到端测试

以 `mvp-scope-and-acceptance.md` 中全部 AC 场景为准。

## 19. AD-17：精简数据模型

MVP 使用 13 张业务表：

```text
users
email_accounts
emails
email_analyses
job_applications
application_events
tasks
reply_drafts
workflow_runs
review_tasks
action_executions
automation_rules
reminders
```

主要合并策略：

- 公司和岗位直接保存在申请记录；
- 邮件正文和附件元数据并入邮件表；
- 四 Agent 运行轨迹并入 `workflow_runs.agent_trace`；
- 建议动作和审核决定合并为 `review_tasks`；
- 邮件通过可空 `application_id` 直接关联一个申请。
- 内部日历继续复用 `tasks`，仅用 `reminders` 记录已投递与已读状态，不另建
  `schedules` 或复制日程事实。

字段和约束以 `database-er-design.md` 为准。

## 20. 骨架阶段暂不冻结的事项

以下事项不阻塞创建项目骨架：

- Qwen 是否作为 MVP 备用模型实际启用；
- 多主机部署时采用何种独立调度器；
- SSE 是否替代轮询；
- 多实例部署时选择何种共享 checkpointer；
- LangGraph Store 和语义记忆是否进入增强范围；
- 外部日历和第二邮箱 Provider。

## 21. 决策依据

- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph Memory](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [LangChain Runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [FastAPI 并发与 `def`/`async def`](https://fastapi.tiangolo.com/async/)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [SQLAlchemy MySQL/MariaDB](https://docs.sqlalchemy.org/en/20/dialects/mysql.html)
- [Alembic Documentation](https://alembic.sqlalchemy.org/en/latest/)
