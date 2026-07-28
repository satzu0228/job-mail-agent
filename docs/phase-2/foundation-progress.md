# 第二阶段完成记录：MVP 边界与正式系统骨架

> 日期：2026-07-27 至 2026-07-28
> 阶段状态：已完成
> 完成里程碑：MVP、架构边界、正式后端骨架和数据库逻辑 ER 已冻结

本文同时保留紧接第二阶段完成的首批 ORM 和 Classification/Extraction 前置验证证据；
这些代码的阶段归属分别是第三阶段和第五阶段，当前总体进度以
`docs/phase-3/database-and-api-progress.md` 为准。

## 1. 本阶段目标

将第一阶段验证过的参考项目能力迁移到本项目自己的正式架构中，先冻结 MVP、技术边界
和数据模型，再建立可运行、可迁移、可测试的后端基础。

## 2. 已完成工作

### 2.1 需求与架构

- 冻结 MVP 范围、非目标和 AC-01 至 AC-10 验收场景。
- 确定 Classification、Extraction、Application、Reply 四个核心 Agent。
- 确定 Validation Node 和 Orchestrator 为确定性组件，不额外包装为 Agent。
- 确定 MySQL 保存业务事实，SQLite checkpointer 保存 LangGraph 运行恢复状态。
- 确定 MVP 不引入 Redis、Celery/RQ、RAG 和 LangGraph Store。
- 将业务数据模型收敛为 12 张核心表。

### 2.2 后端骨架

- 建立 FastAPI 应用工厂、`/api/v1` 路由和健康检查。
- 建立 Pydantic Settings 配置和 `.env` 加载。
- 建立 SQLAlchemy 2 Base、Session 和稳定约束命名规则。
- 建立 PyMySQL 的 MySQL 连接配置。
- 建立 Alembic 环境、迁移模板和测试目录。
- 使用独立 Conda 环境安装正式后端依赖。

### 2.3 首批 ORM 与迁移

已实现：

1. `users`
2. `email_accounts`
3. `job_applications`
4. `emails`

迁移版本：

```text
20260727_0001
```

实现内容包括：

- `BIGINT UNSIGNED` 自增主键；
- `DATETIME(6)` 时间字段；
- JSON、LONGTEXT 和字符串字段；
- Python `StrEnum` 与数据库 `VARCHAR + CHECK`；
- 用户、邮箱账户、求职申请和邮件之间的外键关系；
- 邮箱账户唯一约束；
- IMAP `(account_id, source_folder, uid_validity, imap_uid)` 幂等约束；
- 求职申请乐观锁 `version`；
- `credential_ref` 凭据引用，数据库不保存邮箱授权码；
- 升级和逆依赖顺序降级逻辑。

### 2.4 MySQL 索引修正

`message_id` 使用 `VARCHAR(998)` 完整保存。由于 `utf8mb4` 下完整索引可能超过
InnoDB 索引键长度，使用非唯一前缀索引：

```text
INDEX ix_emails_message_id (message_id(191))
```

`Message-ID` 仍然只作为辅助去重依据，不能替代 IMAP UID 幂等键。

### 2.5 Classification 与 Extraction Schema

已完成两个 Agent 的 Pydantic 输入/输出契约：

- 共享 `PreparedEmail`、附件元数据和证据结构；
- Classification 的求职相关性、九类枚举、优先级、是否回复、后续能力和置信度；
- Classification 对 `NON_JOB` 与后续处理能力的一致性校验；
- Extraction 的公司、岗位、阶段、事件、联系人、时间、地点、链接和材料结构；
- 每个抽取值保存置信度和原文证据；
- 时间同时保存原文、带时区标准值、IANA 时区、歧义和人工确认标记；
- 缺失字段与实际空值进行双向一致性校验；
- 所有 Schema 禁止未知字段，并使用版本号支持后续演进。

Windows 不自带完整 IANA 时区数据库，因此增加轻量 `tzdata` 运行依赖，保证
`Asia/Shanghai` 等时区在 Conda 和部署环境中行为一致。

### 2.6 Classification 与 Extraction 正式 Agent

已在正式后端目录中完成：

- 使用官方 `langchain-deepseek` 接入 `deepseek-chat`，通过统一工厂隔离模型供应商；
- Qwen 仅保留配置扩展位，MVP 不额外安装第二套模型 SDK；
- Classification 和 Extraction 的可调用 Agent，输出继续由 Pydantic 严格校验；
- 两份纳入 Git 的 v1 版本化 Prompt；
- 面试邀请、拒信和非求职促销三封脱敏邮件 Fixture；
- 本地 Fixture 运行入口 `python -m app.cli.analyze_fixture <fixture>`；
- Agent 不写数据库、不发送邮件，也不直接执行归档或状态修改。

已使用真实 DeepSeek 对三个脱敏 Fixture 完成基线运行：

- 面试邀请正确分类为 `INTERVIEW`，并抽取公司、岗位、联系人、会议链接、面试时间和回复截止时间；
- 拒信正确分类为 `REJECTION`，并提出 `REJECTED` 阶段建议；
- 促销邮件正确分类为 `NON_JOB`，提出归档建议且不进入 Extraction；
- 时间校验层可将模型返回的无偏移 ISO 时间与有效 IANA 时区组合为带偏移时间，
  当前面试时间和截止时间均规范为 `+08:00`。

## 3. 验证结果

### 3.1 自动化验证

```text
pytest：24 passed
Ruff：All checks passed
Python compileall：通过
Alembic upgrade --sql：通过
Alembic downgrade --sql：通过
```

自动化测试覆盖：

- ORM 元数据恰好包含首批四张业务表；
- UNSIGNED、JSON、LONGTEXT、字符集和排序规则；
- 枚举 CHECK 约束；
- 外键、唯一约束和索引；
- `message_id(191)` 前缀索引；
- Alembic 只有一个 head；
- upgrade 建表顺序；
- downgrade 逆依赖删表顺序。
- Classification/Extraction 输入输出序列化；
- 分类枚举、置信度和 `NON_JOB` 一致性；
- 未知模型字段拒绝；
- 带时区时间、时间歧义和人工确认规则；
- 字段证据及缺失字段一致性；
- Classification/Extraction 正式 Agent 的版本化 Prompt 装配和结构化调用边界。

### 3.2 真实 MySQL 8 验证

用户已通过 Navicat 创建本地 `job_mail_agent` 数据库和专用连接账号，并完成：

```text
alembic upgrade head
alembic current
alembic check
```

结果：

- 首次真实迁移成功；
- 当前版本为 `20260727_0001 (head)`；
- ORM 元数据与真实数据库之间没有待生成的迁移操作；
- Navicat 中可查看四张业务表和 `alembic_version`。

真实数据库未执行 downgrade，以避免无必要地删除已创建表。降级 SQL 和逆依赖顺序
已经由自动化测试验证。

## 4. 开发过程遇到的问题

| 问题 | 原因 | 处理方式与结果 |
|---|---|---|
| 技术栈和 Agent 数量一度偏多 | 早期方案同时考虑 Store、更多 Agent 和多种基础设施，超出毕业设计可控范围 | 收敛为四个核心 Agent、约 12 张表、MySQL 业务真相源和 SQLite checkpoint；MVP 不使用 Redis、任务队列、RAG 和 LangGraph Store |
| 文档入口和 README 数量不清晰 | 参考项目记录、正式设计和阶段证据混放 | 清理无必要 README，按需求、架构、数据库、计划和阶段分类，并规定每阶段只维护一份进展记录 |
| Conda 下载曾出现镜像连接失败 | 本地 Conda 配置的第三方镜像不可达 | 正式项目统一使用 `job-mail-agent` Conda 环境，通过项目 `pyproject.toml` 安装依赖；不在仓库创建 `.venv` |
| 开发过程中误创建了项目 `.venv` | 执行命令时沿用了旧的环境假设 | 已删除 `.venv`，清理运行说明并将 Conda 环境约束写入协作规则 |
| 通用 OpenAI 兼容接入会模糊供应商边界 | DeepSeek 虽兼容 OpenAI API，但 LangChain 已提供专用集成 | 使用官方 `langchain-deepseek`，Agent 只依赖统一模型工厂，Qwen 暂不安装额外 SDK |
| 测试和文档可能随小功能过度增长 | 早期按单个细节拆分验证会降低毕设开发效率 | 改为正式功能优先，只保留覆盖关键业务约束的集中测试，并只更新既有阶段文档 |

## 5. 完成边界

已经完成的是正式系统基础和首批邮件事实表，不代表完整业务系统已经完成。

尚未实现：

- 其余八张业务表和后续迁移；
- Application、Reply Agent；
- LangGraph 正式工作流和 HITL；
- IMAP 正式增量同步与 SMTP Executor；
- 业务 Repository、API 和 Vue 页面；
- Classification/Extraction 的分析结果持久化。

## 6. 阶段交接

第二阶段已经结束。以下连续开发项用于向第三阶段和第五阶段交接：

1. [已完成] 冻结两个 Agent 的 Pydantic 输入输出 Schema；
2. [已完成] 已准备并运行 3 封脱敏 Fixture，后续按基线错误补充边界样例；
3. [已完成] 建立模型适配接口并实现 DeepSeek，Qwen 仅保留扩展位；
4. [代码完成] 实现求职相关性、分类、优先级和置信度输出；
5. [代码完成] 实现公司、岗位、时间、地点、链接、截止日期等结构化抽取；
6. [已完成] 配置本地 DeepSeek Key，三个 Fixture 的真实分类与抽取基线通过；
7. 设计并实现 `email_analyses` ORM、迁移和分析结果持久化；
8. 暂不接入真实 IMAP、LangGraph 和前端。

完成 Fixture 驱动的分类与抽取后，再接入邮件同步和分析结果持久化，避免同时调试
邮箱、数据库、模型和工作流。
