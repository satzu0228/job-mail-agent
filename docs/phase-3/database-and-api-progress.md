# 第三阶段进展：数据库与基础接口

> 开始日期：2026-07-27
> 阶段状态：进行中
> 当前里程碑：实现 `email_analyses` 并持久化 Classification/Extraction 结果

## 1. 阶段目标

按已冻结的 12 表逻辑 ER 分批实现 ORM 和 Alembic 迁移，建立邮件、求职申请、
任务和回复草稿等基础业务接口。第三阶段完成不等于完整 Agent 工作流完成。

## 2. 已完成

- FastAPI、SQLAlchemy 2、PyMySQL 和 Alembic 正式骨架；
- `users`、`email_accounts`、`job_applications`、`emails` 四个 ORM 模型；
- 首批迁移 `20260727_0001`；
- 本地 MySQL 8 的 `upgrade head`、`current` 和 `check`；
- 为后续持久化提前完成 Classification/Extraction Schema、Agent 和三个真实模型基线；
- 当前 Ruff 检查通过，24 个自动化测试通过。

当前数据库完成度为 4/12 张核心表，基础业务 CRUD API 尚未开始。

## 3. 开发过程遇到的问题

| 问题 | 原因 | 处理方式与验证 |
|---|---|---|
| `message_id` 完整索引可能超过 InnoDB 键长度 | 字段为 `VARCHAR(998)`，`utf8mb4` 最多占用 4 字节 | 保留完整字段，改用 `message_id(191)` 非唯一前缀索引；IMAP UID 组合键仍是主要幂等依据 |
| 真实数据库执行 downgrade 会删除已建业务表 | downgrade 本身是破坏性操作，本阶段只需要验证迁移可逆性 | 不在真实库执行 downgrade，改用离线 DDL 和自动化测试验证逆依赖删除顺序 |
| Windows 环境缺少完整 IANA 时区数据 | `zoneinfo` 依赖系统时区数据库 | 增加轻量 `tzdata` 依赖，`Asia/Shanghai` 校验通过 |
| DeepSeek 抽取时间时遗漏 UTC 偏移 | 模型返回了 `Asia/Shanghai`，但 `normalized` 是无偏移 ISO 字符串 | Prompt 明确要求 `+08:00`；确定性校验层只在时区有效且无夏令时歧义时补齐偏移，三个真实 Fixture 通过 |
| 结构化输出首次解析失败会中断完整 CLI | LangChain 在 Pydantic 校验阶段直接拒绝无时区时间 | 保持最终 Schema 严格，不放宽为无时区时间；修复确定性规范化后重新运行真实 Classification → Extraction 链路 |
| 在第三阶段完成前提前实现了第五阶段部分能力 | 为隔离模型、Schema、IMAP 和数据库问题，优先做了离线 AI 切片，但没有先确认阶段顺序变更 | 保留可复用的 Agent 代码，停止继续扩展第五阶段；后续严格回到第三阶段，跨阶段验证必须先说明并取得用户确认 |
| 项目骨架存在空包、空测试目录和生成缓存 | 初始骨架预创建了未来目录，开发安装和测试又产生缓存与 `egg-info` | 删除未实现功能的空占位目录、失效 `.gitkeep`、根目录重复环境示例及全部生成缓存；需要实现对应模块时再创建目录 |
| `conda run` 转发 Ruff 输出时出现 GBK 编码异常 | Conda 基础环境按 GBK 编码输出，无法编码工具输出中的替换字符 | 改为直接调用 `job-mail-agent` Conda 环境内的 Python 解释器执行检查；Ruff 和 24 个测试均通过 |

## 4. 当前边界与风险

- 尚未实现 `email_analyses` 等其余 8 张表；
- 分类与抽取结果尚未写入 MySQL；
- 尚未建立 Repository、事务用例和邮件基础 API；
- 当前三个 Fixture 只能证明首批代表场景可运行，不能代表九类邮件的完整准确率；
- IMAP 同步、Application/Reply Agent、LangGraph、HITL 和前端属于后续开发。

## 5. 下一步

1. 实现 `email_analyses` ORM 模型；
2. 创建第二批 Alembic 迁移并完成 MySQL 升级验证；
3. 建立分析结果 Repository 和事务用例；
4. 将 Classification/Extraction 的结构化结果关联到 `emails`；
5. 提供单封邮件分析 API，再继续其余业务表和基础接口。
