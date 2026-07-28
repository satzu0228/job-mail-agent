# 第三阶段进展：数据库与基础接口

> 开始日期：2026-07-27
> 完成日期：2026-07-28
> 阶段状态：已完成
> 当前里程碑：12 表、基础 API 与真实 MySQL 验收完成

## 1. 阶段目标

按已冻结的 12 表逻辑 ER 分批实现 ORM 和 Alembic 迁移，建立邮件、求职申请、
任务和回复草稿等基础业务接口。第三阶段完成不等于完整 Agent 工作流完成。

## 2. 已完成

- FastAPI、SQLAlchemy 2、PyMySQL 和 Alembic 正式骨架；
- `users`、`email_accounts`、`job_applications`、`emails` 四个 ORM 模型；
- 首批迁移 `20260727_0001`；
- 本地 MySQL 8 的 `upgrade head`、`current` 和 `check`；
- 为后续持久化提前完成 Classification/Extraction Schema、Agent 和三个真实模型基线；
- `email_analyses` ORM 模型与第二批迁移 `20260728_0002`；
- 分析结果映射、Repository 和事务用例，可版本化保存 Classification/Extraction
  结果，并在同一邮件下切换唯一当前版本；
- 分类、抽取完整结构化结果、字段证据、缺失字段和时间不确定性均可追踪；
- 第二批迁移的 MySQL 离线 DDL、单步降级 SQL、ORM 元数据及事务规则测试。
- 第二迁移已在本地 MySQL 8 完成 `upgrade head`、`current` 和 `check`，
  当前版本为 `20260728_0002 (head)`，且无未生成的迁移差异。
- `workflow_runs`、`application_events`、`tasks`、`reply_drafts`、
  `review_tasks`、`action_executions`、`automation_rules` 七个 ORM 模型；
- 第三迁移 `20260728_0003`，在建表后补齐三个循环依赖外键；
- 邮件、求职记录、任务和回复草稿的用户隔离 Repository 与事务用例；
- 邮件只读接口，求职记录和任务的创建/查询/受控更新接口，以及回复草稿的
  创建/查询/正文编辑接口；
- 普通申请 PATCH 不暴露 `current_stage/status`，草稿 PATCH 不暴露批准或发送状态；
- API 输入时间必须带时区，写入 MySQL 前统一转换为 UTC，输出统一为带 `Z` 的 ISO 8601；
- Swagger/OpenAPI 路由与关键安全边界测试；
- 真实 MySQL 完成 `upgrade head`、`current` 和 `check`，当前版本为
  `20260728_0003 (head)`，无未生成迁移差异；
- 四组列表接口在真实库返回 200，申请和任务在真实事务内完成创建验证后整体回滚。

当前数据库完成度为 12/12 张核心表。Ruff 检查通过，40 个自动化测试通过。

## 3. 开发过程遇到的问题

| 问题 | 原因 | 处理方式与验证 |
|---|---|---|
| `message_id` 完整索引可能超过 InnoDB 键长度 | 字段为 `VARCHAR(998)`，`utf8mb4` 最多占用 4 字节 | 保留完整字段，改用 `message_id(191)` 非唯一前缀索引；IMAP UID 组合键仍是主要幂等依据 |
| 真实数据库执行 downgrade 会删除已建业务表 | downgrade 本身是破坏性操作，本阶段只需要验证迁移可逆性 | 不在真实库执行 downgrade，改用离线 DDL 和自动化测试验证逆依赖删除顺序 |
| Windows 环境缺少完整 IANA 时区数据 | `zoneinfo` 依赖系统时区数据库 | 增加轻量 `tzdata` 依赖，`Asia/Shanghai` 校验通过 |
| DeepSeek 抽取时间时遗漏 UTC 偏移 | 模型返回了 `Asia/Shanghai`，但 `normalized` 是无偏移 ISO 字符串 | Prompt 明确要求 `+08:00`；确定性校验层只在时区有效且无夏令时歧义时补齐偏移，三个真实 Fixture 通过 |
| 结构化输出首次解析失败会中断完整 CLI | LangChain 在 Pydantic 校验阶段直接拒绝无时区时间 | 保持最终 Schema 严格，不放宽为无时区时间；修复确定性规范化后重新运行真实 Classification → Extraction 链路 |
| 在第三阶段完成前提前实现了第五阶段部分能力 | 为隔离模型、Schema、IMAP 和数据库问题，优先做了离线 AI 切片，但没有先确认阶段顺序变更 | 保留可复用的 Agent 代码，停止继续扩展第五阶段；后续严格回到第三阶段，跨阶段验证必须先说明并取得用户确认 |
| 项目中存在空测试目录和生成缓存 | 开发安装和测试产生了缓存与 `egg-info`，初始测试骨架还保留未使用占位目录 | 删除失效 `.gitkeep`、空测试占位、根目录重复环境示例和生成缓存；`application`、`workflows`、`checkpoint`、`email`、`security` 属于冻结架构，继续保留 |
| `conda run` 转发 Ruff 输出时出现 GBK 编码异常 | Conda 基础环境按 GBK 编码输出，无法编码工具输出中的替换字符 | 改为直接调用 `job-mail-agent` 环境内的 Python；Ruff 和 40 个测试通过 |
| 第二迁移首次无法连接真实 MySQL | `backend/.env` 当时配置的 `job_mail` 凭据被 MySQL 以 1045 拒绝 | 用户更新本地密码后重新执行成功；`upgrade head`、`current`、`check` 均通过 |
| ORM 元数据排序提示三表循环依赖 | `workflow_runs.pending_review_task_id` 与审核、草稿链路形成循环 | 对后补的工作流审核外键设置 `use_alter`，迁移仍显式先建表后加约束；`alembic check` 不再告警 |

## 4. 当前边界与风险

- 当前三个 Fixture 只能证明首批代表场景可运行，不能代表九类邮件的完整准确率；
- 基础 API 不包含关键申请阶段变更、草稿批准、发送、归档和其他外部动作，
  这些操作必须在后续 HITL 审核与 Executor 中实现；
- IMAP 同步、MIME/HTML 安全解析、Application/Reply Agent、LangGraph、HITL
  和前端属于后续开发。

## 5. 下一步

1. 进入第四阶段，实现邮箱账户配置和连接测试；
2. 实现 IMAP 手动同步、UID 幂等与最近邮件拉取；
3. 实现 MIME、字符集、纯文本/HTML 正文解析和 HTML 安全清洗；
4. 将解析后的邮件事实写入现有 `emails` 表，并通过 Swagger 验证。
