# 第五阶段进展：单封邮件 AI 分析

> 开始日期：2026-07-28
> 完成日期：2026-07-28
> 阶段状态：已完成
> 当前里程碑：分类、抽取、统一分析 API 与版本化持久化通过真实模型联调

## 1. 阶段目标

复用已经完成的 Classification/Extraction 离线切片，建立正式单封邮件分析链路：

```text
读取已解析邮件事实
→ 构造最小化 PreparedEmail
→ Classification Agent
→ NON_JOB 安全短路，或进入 Extraction Agent
→ Schema 与确定性规则校验
→ 版本化写入 email_analyses
```

本阶段不实现 Application Agent、申请状态变更、回复草稿或 LangGraph 工作流。

## 2. 已完成

- 新增 `POST /api/v1/emails/{id}/classify`，返回严格的
  `ClassificationOutput`；
- 新增 `POST /api/v1/emails/{id}/extract`，内部先分类，非求职邮件返回 409，
  不调用 Extraction Agent；
- 新增 `POST /api/v1/emails/{id}/analyze`，执行分类、条件抽取并保存当前分析版本；
- 邮件详情返回唯一 `current_analysis`，展示当前分类、抽取、置信度、证据和状态，
  历史版本仍保留在数据库中；
- ORM 邮件事实确定性映射为 `PreparedEmail`，MySQL 无时区 UTC 时间恢复为
  带 UTC 偏移的模型输入；
- 只向模型传递 `analysis_text` 和必要头部，不发送清洗前 HTML、授权码或附件内容；
- 附件只传递有效的文件名、类型和大小元数据，过滤超大邮件占位等无文件名记录；
- 解析失败或没有分析文本的邮件返回 409，不进入模型；
- 模型调用前结束数据库读取事务，网络等待期间不持有数据库事务或行锁；
- Classification 失败、Extraction 失败和底层结构化校验异常统一转换为安全的
  502 错误，不向 API 回显正文或原始模型异常；
- `analyze` 通过邮件行锁和 `(email_id, version)` 唯一约束切换唯一当前版本；
- `NON_JOB` 分析保存分类事实和空抽取结果，不伪造公司、岗位或时间字段；
- 时间不确定、模型不确定项继续映射为 `PENDING_CONFIRMATION`，不直接产生任务或
  修改申请状态。

## 3. 接口语义

```http
POST /api/v1/emails/{id}/classify
POST /api/v1/emails/{id}/extract
POST /api/v1/emails/{id}/analyze
```

- `classify` 和 `extract` 用于独立调试，不创建不完整的当前分析版本；
- `extract` 会执行一次分类以确保输入确实为求职邮件；
- `analyze` 是正式持久化入口，返回分析 ID、版本、状态、分类和可选抽取结果；
- 重复调用 `analyze` 会创建新版本并取消旧版本的 `is_current`，不会覆盖历史事实。

## 4. 验证证据

- Ruff：通过；
- 自动化测试：59 个通过；
- OpenAPI 包含三个第五阶段接口；
- 覆盖求职邮件完整编排、`NON_JOB` 短路、解析失败拦截、模型异常脱敏、
  UTC 输入恢复、附件元数据过滤、版本持久化和 409 错误边界；
- 使用仓库内脱敏面试邀请 Fixture 调用正式 `/analyze`；
- 真实 DeepSeek 返回 `INTERVIEW`，分类置信度 0.95；
- Extraction Agent 正常执行，整体置信度 0.95；
- 分析以 `VALID`、版本 1 写入真实 MySQL；
- 真实 MySQL 连续写入两个分析版本后，邮件详情只返回版本 2 的
  `current_analysis`，置信度与当前版本一致；
- 联调创建的临时账户、邮件和分析记录已删除，真实测试邮箱的 8 封邮件未修改。

## 5. 开发问题与处理

| 问题 | 原因 | 处理与结果 |
|---|---|---|
| `email_analyses` 要求求职分析同时具有分类与抽取 | 只持久化 `/classify` 会形成不完整当前版本 | 独立接口只返回结果；仅 `/analyze` 创建正式版本 |
| MySQL 时间是无时区 UTC，Agent Schema 要求带时区 | 数据库和 API/模型时间边界不同 | 构造 `PreparedEmail` 时确定性恢复为 UTC aware datetime |
| 模型网络调用可能长期占用数据库事务 | 先读 ORM 再直接调用模型会保留隐式事务 | 先复制最小事实并结束读取事务，模型完成后开启短写事务 |
| 真实邮箱内容属于敏感数据 | 阶段实施不自动授权向外部模型发送真实邮件 | 未发送真实邮箱正文；改用已脱敏 Fixture 完成同一正式 API 和 MySQL 联调 |
| `/extract` 遇到 `NON_JOB` 不应强行生成字段 | Extraction Schema 明确只接受求职分类 | 返回 409 并保证 Extraction Agent 调用次数为 0 |

## 6. 当前边界与下一步

- 三个接口当前同步执行，符合 MVP 有界单封分析决策；
- `classify` 或 `extract` 的独立结果不写库，审计事实以 `/analyze` 版本为准；
- 当前不根据模型结果创建申请、任务或回复草稿；
- 下一步进入第六阶段：确定性查询候选申请，由 Application Agent 提出匹配和阶段
  建议，再由状态机与人工确认控制业务写入。
