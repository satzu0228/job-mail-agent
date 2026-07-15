# 环境与运行记录

## 基本信息

- 日期：2026-07-15
- 操作系统：Windows
- Python 版本：3.11.15（Conda 环境 `email-ai-agent-ref`）
- 参考项目分支：main
- 参考项目 Commit ID：f54ad9d37e2dbe5a6510095acbcf8b6fbf6a79ba
- 模型供应商及模型：
- 测试邮箱服务商：

## 安装步骤

待记录实际执行的命令和结果。

## 最终依赖版本

待运行成功后记录，尤其关注：

- langchain
- langgraph
- langsmith
- openai
- python-dotenv
- jinja2

## 对参考项目的本地修改

| 文件 | 修改原因 | 修改内容 | 是否考虑迁移 |
|---|---|---|---|
| `agents/filtering_agent.py` | 兼容 LangChain 1.x | `PromptTemplate` 改从 `langchain_core.prompts` 导入 | 否，仅兼容修复 |
| `agents/summarization_agent.py` | 兼容 LangChain 1.x 并修复参数错误 | 更新导入；`input_var` 改为 `input_variables` | 否，仅兼容修复 |
| `agents/response_agent.py` | 兼容 LangChain 1.x | `PromptTemplate` 改从 `langchain_core.prompts` 导入 | 否，仅兼容修复 |
| `references/Email-AI-Agent/.gitignore` | 防止泄露密钥和提交运行缓存 | 忽略 `.env`、虚拟环境、Python 缓存和日志 | 是，安全配置可借鉴 |
| `experiments/email-ai-agent/run_mock.py` | 安全运行模拟邮件 | 新增不调用 IMAP/SMTP 的实验入口 | 是，作为测试思路参考 |
| `experiments/email-ai-agent/test_imap.py` | 安全验证真实测试邮箱 | 只读打开 INBOX，使用 `BODY.PEEK` 检查最近邮件 | 是，作为 IMAP 集成测试参考 |
| `core/email_imap.py` | 让参考项目自身兼容 163 IMAP | 支持端口和超时；按能力发送 RFC 2971 ID；使用 `BODY.PEEK`；补充状态检查和连接清理 | 是，后续需封装为正式邮箱适配层 |
| `core/email_sender.py` | 让参考项目兼容 163 SMTP | 465 端口使用隐式 TLS `SMTP_SSL`，其他端口保留 STARTTLS | 是，后续需改为显式邮箱配置策略 |
| `experiments/email-ai-agent/test_smtp.py` | 安全验证 SMTP 发件 | 默认只预览；带 `--confirm` 时向配置邮箱自身发送固定测试邮件 | 是，作为 SMTP 集成测试参考 |
| `agents/filtering_agent.py` | 修复模型解释文本导致的分类误判 | 改为 JSON 固定标签和精确解析，失败时进入 `needs_review` | 是，正式系统应采用更强的结构化输出 |
| `agents/summarization_agent.py` | 输出适配中文求职场景 | 摘要提示词改为简体中文并要求保留关键时间信息 | 是 |
| `agents/response_agent.py`、`utils/formatter.py` | 输出中文回复 | 回复正文、称呼、主题和落款改为中文 | 是 |

## 遇到的问题

| 问题 | 原因 | 解决方式 | 证据 |
|---|---|---|---|
| `ModuleNotFoundError: langchain.prompts` | 参考项目未锁依赖版本，旧导入路径不适用于 LangChain 1.3.13 | 改从 `langchain_core.prompts` 导入 | 项目模块导入测试 |
| 模型输出 `informational` 却被判定为 `spam` | 原实现对整段解释文本进行关键词包含判断，解释中的 “no ... spam” 被误匹配 | 只接受固定 JSON 标签或纯标签，其他输出回退到人工审核 | 2026-07-15 首次模拟运行 |
| IMAP 测试长时间无返回，最终 `LOGIN => socket error: EOF` | 初版测试入口没有套接字超时；163 服务端在登录阶段关闭连接 | 为测试入口增加 15 秒超时和分阶段输出，继续检查授权码或服务端安全限制 | 2026-07-15 首次 163 IMAP 测试 |
| 163 登录成功但无法以只读模式打开 `INBOX` | `readonly=True` 使用 `EXAMINE`，服务端未接受该模式 | 测试脚本回退到 `SELECT INBOX`，邮件仍使用 `BODY.PEEK` 获取 | 2026-07-15 |
| 163 返回 `SELECT Unsafe Login` | 网易要求第三方 IMAP 客户端发送 RFC 2971 ID 信息 | 在登录后、打开收件箱前发送最小客户端 ID | 2026-07-15 |
