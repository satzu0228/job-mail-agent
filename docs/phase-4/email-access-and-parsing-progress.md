# 第四阶段进展：邮件接入与解析

> 开始日期：2026-07-28
> 完成日期：2026-07-28
> 阶段状态：已完成
> 当前里程碑：真实 163 邮箱接入、安全解析与 MySQL 幂等验收通过

## 1. 阶段目标

在不接入完整 Agent 工作流的前提下，建立邮件进入系统的确定性链路：

```text
邮箱账户配置
→ IMAP/SMTP 独立连接测试
→ 只读同步 INBOX
→ MIME/HTML 安全解析
→ UID/UIDVALIDITY/Message-ID 幂等判断
→ 写入 MySQL
→ 通过邮件查询 API 查看
```

## 2. 已完成

- 新增邮箱账户创建和列表接口；
- 列表响应只返回脱敏邮箱地址，不返回 `credential_ref` 或授权码；
- 数据库仅保存 `credential_ref`，授权码从进程环境变量或受控 `.env` 读取；
- 新增 IMAP、SMTP 独立连接测试，失败信息不回显底层异常和凭据；
- 新增 `POST /api/v1/email-accounts/{id}/sync` 手动同步接口；
- IMAP 以 `readonly=True` 打开 `INBOX`，使用 `BODY.PEEK`，不主动改变未读状态；
- 首次同步和 UIDVALIDITY 变化时只处理最近的有界邮件，正常情况下按最后 UID
  增量拉取；
- 以账户、来源文件夹、UIDVALIDITY 和 UID 作为主幂等键，以 Message-ID 作为
  UIDVALIDITY 变化等场景的辅助去重依据；
- 支持中文主题、显示名、地址、日期、纯文本、HTML 和 MIME 多段正文；
- HTML 使用允许列表清洗，移除脚本、事件属性、危险协议和所有远程图片；
- 原始安全正文与 `analysis_text` 分开，后者去除常见引用回复和签名；
- 仅保存附件文件名、类型、大小、Content-ID 和 inline 标记，不持久化附件内容；
- 超过配置上限的邮件只取头部，保存跳过下载元数据并标为 `PARTIAL`；
- 单封解析异常保存 `FAILED` 占位事实，不回滚已经成功的整批邮件；
- 同步结果返回 examined、created、skipped 和 failed 数量，并更新账户同步游标。

## 3. 接口

```http
POST /api/v1/email-accounts
GET  /api/v1/email-accounts
POST /api/v1/email-accounts/{id}/test-connection
POST /api/v1/email-accounts/{id}/sync
GET  /api/v1/emails
GET  /api/v1/emails/{id}
```

账户创建请求中的 `credential_ref` 示例为
`JOB_MAIL_EMAIL_CREDENTIAL_TEST_163`。该名称对应本地安全配置，不能把真实授权码
直接填入此字段。

## 4. 验证证据

- Ruff：通过；
- 自动化测试：50 个通过；
- 新增覆盖：凭据引用、中文 MIME、HTML-only、危险 HTML、远程跟踪图片、
  附件元数据、超大邮件降级、UIDVALIDITY 变化和只读拉取；
- `alembic upgrade head`：真实 MySQL 8 通过；
- `alembic check`：无未生成迁移差异；
- 真实 MySQL 事务内创建账户和邮件后，按 IMAP 主幂等键及 Message-ID
  查询均命中，随后整体回滚，未保留验证数据；
- OpenAPI 已包含四个第四阶段接口，且响应 Schema 不暴露授权码和凭据引用。
- 真实 163 邮箱 IMAP SSL 993 与 SMTP SSL 465 均登录成功；
- 首次只读同步检查 8 封、新增 8 封、失败 0 封；
- 第二次增量同步没有新 UID，新增 0 封，MySQL 邮件总数保持 8；
- 8 个 `(source_folder, uid_validity, imap_uid)` 身份均唯一，无重复 Message-ID；
- 8 封邮件全部为 `SUCCEEDED`，均有 `analysis_text`；
- 7 封 HTML 邮件未检出脚本、事件属性、远程图片或 `javascript:` 协议。

## 5. 开发问题与处理

| 问题 | 原因 | 处理与结果 |
|---|---|---|
| 实施计划曾写“数据库保存应用层加密密文”，架构决策和 ER 写 `credential_ref` | 文档在不同阶段形成了不一致表述 | 以 AD-15 和现有 ER 为准，数据库只存引用；同步修正实施计划 |
| 仅用进程环境变量会使普通 `uvicorn` 无法读取本地 `.env` 中的动态凭据名 | Pydantic Settings 只加载已声明字段，不会把任意键写回 `os.environ` | 凭据解析器显式读取与 Settings 相同的根目录及后端 `.env`，进程环境变量优先 |
| UIDVALIDITY 变化后沿用旧 UID 游标会漏信 | UID 只在同一 UIDVALIDITY 内有效 | 客户端先读取 UIDVALIDITY；变化时从新 UID 空间重新选择最近有界邮件 |
| 真实 163 SMTP 成功但 IMAP 在打开 INBOX 时失败 | 网易要求登录后、打开文件夹前发送 RFC 2971 `ID` | 将第一阶段已验证经验迁入正式 Provider Adapter；增加回归测试后 IMAP/SMTP 均实连成功 |
| 下载完整 MIME 会把大附件一并拉取 | IMAP 完整消息包含附件 | 先读取 `RFC822.SIZE`，超过上限时只取 Header 并记录降级状态 |
| HTML 清洗不能依赖前端自觉 | 邮件正文是不可信输入，详情接口可能被多端消费 | 后端解析时执行允许列表清洗，移除脚本、事件属性、危险 URL 和远程图片 |

## 6. 当前边界与下一步

- 本阶段只验证账户接入、确定性解析和入库，不触发 Agent、SMTP 发送或自动归档；
- 测试邮箱当前 8 封邮件没有附件，因此附件元数据能力由自动化 MIME Fixture 验证；
- 第二次同步按最后 UID 增量查询，没有新 UID，因此 `examined`、`created` 和
  `failed` 均为 0；数据库唯一身份数保持 8，满足不重复入库要求；
- 下一步进入第五阶段，复用已完成的 Classification/Extraction 离线切片，补齐
  单封邮件 classify、extract、analyze API 及正式分析结果持久化。
