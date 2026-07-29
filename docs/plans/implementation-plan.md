# 求职邮件智能管理系统开发实施计划

> 文档状态：已结合第一阶段实际结果完成首次审核
> 审核日期：2026-07-27
> 当前进度：前八阶段已完成；第九阶段 Vue 3 核心页面已实现并接通现有 API，
> 已完成首轮真实 FastAPI/MySQL 浏览器验收；下一项实现 163、126、QQ、Gmail
> 和自定义 IMAP/SMTP Provider 预设，并继续补齐端到端验证和查询接口
> 关联文档：`docs/phase-1/`、`docs/architecture/multi-agent-system-design.md`

## 文档审核结论

本计划的总体方向可行：先验证参考链路，再独立实现 FastAPI、MySQL、LangGraph 和 Vue 系统，并把模型推理、确定性业务规则与高风险动作执行分开。

本次审核已修正以下关键问题：

- 按实际记录将第一阶段标记为已完成，不再重复安排参考项目、IMAP 和 SMTP 验证。
- 不把参考项目描述为已实现 LangGraph checkpoint 或可恢复 `interrupt()`；该能力应在正式系统中另行验证。
- 邮件幂等键补充 `UIDVALIDITY`，并将 `Message-ID` 作为跨文件夹或异常 UID 场景的辅助去重依据。
- 将原始邮件、模型分析、人工确认结果和外部动作执行记录分开建模。
- 统一求职邮件分类枚举，区分“邮件类别”和“申请阶段”。
- 明确 Agent 只生成结构化建议，关键状态更新、日程创建、归档和发送均由业务规则与人工审核控制。
- 将 DeepSeek/Qwen 放入可替换模型适配层，不在业务代码中绑定单一供应商。

## 一、项目开发目标

本项目拟实现一个面向求职场景的大模型与多智能体协作邮件管理系统，完成以下核心流程：

```text
邮箱同步
→ 邮件解析
→ 求职邮件识别与分类
→ 关键信息抽取
→ 求职记录创建或匹配
→ 生成求职状态变更建议
→ 生成面试、任务及截止日期建议
→ 回复草稿生成
→ 用户审核关键动作
→ 执行获批的状态变更、日程创建或邮件发送
```

项目采用以下技术栈：

- 前端：Vue 3、TypeScript、Element Plus
- 后端：Python、FastAPI
- AI 框架：LangChain、LangGraph
- 大语言模型：DeepSeek、Qwen（通过统一模型适配层接入，主备方案待技术验证）
- 邮件协议：IMAP、SMTP
- 数据库：MySQL

---

## 二、整体开发原则

### 1. 先完成最小闭环

第一版只要求跑通一封邮件的完整处理过程：

```text
输入或同步一封邮件
→ AI 分类
→ 抽取公司、岗位、时间等信息
→ 创建或更新求职记录
→ 生成回复草稿
→ 用户审核和修改
→ SMTP 发送
```

不要一开始就实现：

- 多邮箱同时同步
- 复杂权限管理
- 第三方日历
- 附件智能解析
- 多个 Agent 自主协商
- 自动无审核发送
- 大规模定时任务

### 2. LangGraph 只负责工作流编排

适合设计为 Agent 或 LangGraph 节点的功能：

- 邮件分类
- 关键信息抽取
- 求职状态判断
- 回复内容生成
- 人工审核中断

适合设计为普通 Service 的功能：

- IMAP 收取邮件
- SMTP 发送邮件
- 邮件正文解析
- 数据库存取
- 求职记录匹配
- 状态机合法性校验
- 日程保存
- 邮件去重
- 重试和异常处理

### 3. 高风险操作必须人工确认

以下操作必须经过统一审核流程；正式系统优先评估使用 LangGraph `interrupt()`、持久化 checkpoint 与数据库审核任务实现：

- 发送邮件
- 修改求职状态
- 创建重要日程
- 归档或删除邮件

尤其是邮件发送，模型只能生成草稿或发送建议，不得直接执行 SMTP 发送。

---

## 三、具体开发阶段

### 第一阶段：跑通参考项目与核心技术链路（已完成）

#### 完成时间

2026-07-15 至 2026-07-16。

#### 阶段目标

确认大模型、LangGraph、IMAP 和 SMTP 能正常运行，为后续独立开发验证技术可行性。

#### 开发内容

1. 克隆并运行 Email-AI-Agent。
2. 配置 DeepSeek API。
3. 使用模拟邮件测试邮件分类、摘要生成和回复草稿生成。
4. 准备一个专门的测试邮箱。
5. 跑通 IMAP 邮件读取。
6. 跑通 SMTP 邮件发送。
7. 阅读参考项目中的 State、节点和条件路由，并确认其没有 checkpoint、LangGraph `interrupt()`、可恢复中断或真正的 Agent 工具协作。
8. 记录可以借鉴的设计思路，不直接在参考仓库中继续开发完整系统。

#### 重点验证

- DeepSeek 是否能正常调用。
- 邮件正文是否能正确解析。
- 识别参考项目对 HTML/MIME 的支持边界，为正式解析器设计测试。
- 中文主题和正文是否乱码。
- 至少一种测试邮箱是否能通过 IMAP、SMTP 连接；本阶段实际验证的是 163。
- 参考项目的人工审核位于何处，是否具备中断恢复能力。
- 用户审核后是否能正常发送测试邮件。

#### 阶段成果

```text
输入一封模拟邮件
→ 模型完成分类
→ 生成摘要
→ 生成回复草稿
→ 用户确认
→ SMTP 发送
```

#### 实际验收结果

- DeepSeek 模型调用、模拟邮件分类、中文摘要和回复草稿生成均已通过。
- 163 IMAP 登录、中文邮件读取、SMTP SSL 自发自收均已通过。
- 跨邮箱端到端闭环已通过，回复实际到达收件箱。
- 已完成工作流、外部副作用、已知缺陷和复用方式分析。
- 已确认参考项目的人工审核只是阻塞式 `input()`，不存在可恢复 checkpoint；HTML-only 邮件、安全 MIME 解析、修改/拒绝审核分支仍属于正式系统待验证项。

验收证据见 `docs/phase-1/test-results.md`、`workflow-analysis.md`、`known-issues.md` 和 `reuse-assessment.md`。

---

### 第二阶段：冻结 MVP 边界并搭建项目骨架（已完成）

#### 阶段目标

评审现有架构草案，冻结第一版业务边界与关键技术决策，在本仓库中搭建正式后端基础结构。参考项目只用于对照，不作为正式源码依赖。

MVP 业务范围、非目标和验收场景已冻结，具体见 `docs/requirements/mvp-scope-and-acceptance.md`。后续架构设计不得静默扩大或削弱该基线。

#### MVP 功能范围

1. 添加一个邮箱账户。
2. 手动同步邮箱邮件。
3. 查看邮件列表和邮件详情。
4. 对单封邮件进行 AI 分析。
5. 自动识别求职邮件类型。
6. 抽取公司、岗位和时间信息。
7. 创建或更新求职记录。
8. 生成邮件回复草稿。
9. 用户修改并确认草稿。
10. 发送邮件。
11. 在求职看板中查看状态。
12. 按用户规则归档低优先级邮件，并支持恢复。

第一版只支持一个已验证的测试邮箱 Provider 也可以满足闭环，但数据模型和接口不得写死 163。第三方日历、附件智能解析、多邮箱并发同步和复杂权限不进入首个纵向切片。

#### 已收敛的骨架决策

1. MySQL 保存业务数据，SQLAlchemy 2 + PyMySQL 同步访问，Alembic 管理迁移。
2. LangGraph State 管单次运行，官方 SQLite saver 管 MVP checkpoint，MySQL 管审核和动作事实。
3. MVP 不启用 LangGraph Store，不复制用户、公司、岗位等权威业务数据。
4. DeepSeek 首实现，Qwen 通过统一模型接口保留替换能力。
5. 确定性 Orchestrator 协调 Classification、Extraction、Application、Reply 四个核心 Agent；不实现 Review Agent 和 LLM Supervisor。
6. 有界手动同步与单封分析先同步执行，不引入 Celery/RQ。
7. Vue 使用 REST + 状态轮询。
8. MVP 数据库只保存 `credential_ref`，授权码从进程环境变量或受控 `.env` 配置读取，不写入数据库。

完整理由、代价和升级条件见 `docs/architecture/architecture-decisions.md`。

#### 冻结项目结构

```text
job-email-agent/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── application/
│   │   ├── domain/
│   │   ├── agents/
│   │   ├── workflows/
│   │   ├── infrastructure/
│   │   ├── prompts/
│   │   ├── core/
│   │   └── main.py
│   ├── tests/
│   ├── migrations/
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   └── src/
├── docs/
└── README.md
```

#### 后端职责结构

```text
backend/app/
├── api/
│   └── v1/
├── application/
│   └── # 用例编排和事务边界
├── domain/
│   └── # 枚举、领域模型、状态机和策略
├── agents/
│   ├── classification/
│   ├── extraction/
│   ├── application/
│   └── reply/
├── workflows/
│   └── # State、节点、路由、checkpoint 和恢复
├── infrastructure/
│   ├── db/
│   ├── email/
│   ├── llm/
│   ├── checkpoint/
│   └── security/
├── prompts/
├── core/
│   └── # 配置、日志、异常和生命周期
└── main.py
```

求职记录候选查询和状态机校验由确定性工具实现；Application Agent 只读取候选、比较上下文并提出结构化匹配/阶段建议，不直接写数据库。

---

### 第三阶段：设计数据库并建立基础接口（已完成）

#### 阶段目标

确定核心数据结构，完成数据库迁移和基础增删改查接口。

#### 核心数据表

MVP 逻辑 ER 已精简为12张表：

1. `users`
2. `email_accounts`
3. `emails`
4. `email_analyses`
5. `job_applications`
6. `application_events`
7. `tasks`
8. `reply_drafts`
9. `workflow_runs`
10. `review_tasks`
11. `action_executions`
12. `automation_rules`

字段、关系、约束、状态机和迁移顺序以 `docs/database/database-er-design.md` 为准，不能混淆原始数据、模型建议、人工确认值和最终动作。

建议对以下组合设置唯一约束：

```text
account_id + source_folder + uid_validity + imap_uid
```

`source_folder` 表示首次同步文件夹，用于防止同一邮件重复同步；归档或恢复只更新 `current_folder`，不改变原始幂等键。`Message-ID` 需要单独保存并建立适当索引，作为跨文件夹、邮件移动或服务端 UID 异常场景的辅助去重依据，但不能假定所有邮件都具有可靠且唯一的 `Message-ID`。

后期增强可增加 `notifications`、`reply_templates` 或独立 Prompt 元数据表；MVP Prompt 先使用纳入 Git 的版本化文件。

#### 阶段成果

- 数据库表创建完成。
- Alembic 数据库迁移可正常执行。
- FastAPI 能连接 MySQL。
- 完成邮件、求职记录、日程和草稿的基础接口。
- Swagger 接口文档可正常访问。

---

### 第四阶段：实现邮件接入与解析（已完成）

#### 阶段目标

先解决邮件如何进入系统的问题，不急着接入完整 Agent。

#### 开发内容

实现邮箱账户配置接口：

```http
POST /api/email-accounts
GET /api/email-accounts
POST /api/email-accounts/{id}/test-connection
```

实现手动同步接口：

```http
POST /api/email-accounts/{id}/sync
```

同步流程：

```text
连接 IMAP
→ 获取邮件 UID
→ 判断邮件是否已存在
→ 下载邮件
→ 解析邮件头和正文
→ 保存数据库
```

需要处理：

- 发件人和收件人
- 邮件主题
- 接收时间
- 纯文本正文
- HTML 正文
- 字符编码
- MIME 多段内容
- 引用回复和签名内容

前期只同步收件箱和最近一定数量的邮件，不做全邮箱历史同步、大附件下载和实时推送。

#### 阶段成果

```text
点击“同步邮件”
→ 从测试邮箱获取新邮件
→ 邮件保存至 MySQL
→ 通过 Swagger 查看邮件内容
```

---

### 第五阶段：实现单封邮件 AI 分析（已完成）

#### 阶段目标

先完成分类和信息抽取，不急着编写完整多 Agent 工作流。

#### 1. 邮件分类

接口：

```http
POST /api/emails/{id}/classify
```

分类结果建议包括：

- `INTERVIEW`：面试邀请、安排或变更
- `ASSESSMENT`：笔试、在线测评或编程测试
- `OFFER`：录用意向、正式 Offer 或 Offer 沟通
- `REJECTION`：拒信或流程终止
- `MATERIAL_REQUEST`：材料补充要求
- `APPLICATION_UPDATE`：投递确认、流程进展或状态通知
- `RECRUITER_COMMUNICATION`：招聘人员一般沟通
- `JOB_RELATED_OTHER`：其他求职相关邮件
- `NON_JOB`：广告、订阅和其他非求职邮件

“面试改期”等更细粒度信息使用 `event_type` 或子类型表达，不另建一套与数据库、API 和前端不一致的顶层枚举。

建议使用结构化输出：

```json
{
  "is_job_related": true,
  "category": "INTERVIEW",
  "confidence": 0.94,
  "reason": "邮件包含面试时间和会议链接"
}
```

#### 2. 信息抽取

接口：

```http
POST /api/emails/{id}/extract
```

抽取内容包括：

- 公司名称
- 岗位名称
- 城市
- 事件类型
- 面试或笔试时间
- 截止日期
- 地点
- 会议链接
- 联系人及联系方式
- 材料要求
- 原始时间文本、标准化时间、时区和不确定性
- 字段来源证据与缺失字段

建议使用 Pydantic 定义结构化输出。

#### 3. 统一分析接口

```http
POST /api/emails/{id}/analyze
```

执行流程：

```text
读取邮件
→ 判断是否为求职邮件
→ 分类
→ 信息抽取
→ 保存分析结果
```

---

### 第六阶段：实现求职记录和状态管理

#### 阶段目标

将邮件分析结果转化为求职流程数据。

> 阶段状态：已完成（2026-07-28）。实现证据见
> `docs/phase-6/application-management-progress.md`。

#### 开发内容

实现求职记录匹配：

```http
POST /api/emails/{id}/match-application
```

先由确定性规则和数据库查询产生候选，再由 Application Agent 或评分逻辑结合上下文排序：

1. 公司名称
2. 岗位名称
3. 发件邮箱
4. 已有关联邮件
5. 时间范围

唯一高置信候选可提出关联建议；无法匹配、同公司多岗位、多个候选接近或关键信息冲突时进入人工确认。Agent 只有只读查询权限，不直接创建申请或写入阶段。

定义求职状态机，例如：

```text
APPLIED → ASSESSMENT
APPLIED → INTERVIEW
ASSESSMENT → INTERVIEW
INTERVIEW → OFFER
APPLIED → REJECTED
ASSESSMENT → REJECTED
INTERVIEW → REJECTED
```

同一阶段内的“面试改期/二面通知”应记录为时间线事件，而不是伪造一次 `INTERVIEW → INTERVIEW` 阶段迁移。大模型负责提出语义判断和 `proposed_stage`，状态机负责校验；只有规则允许且按策略完成确认后，才写入用户确认的当前阶段。模型建议、确认值和最终执行结果必须分别保留。

#### 阶段成果

```text
分析邮件
→ 匹配求职记录
→ 判断新状态
→ 状态机校验
→ 进入审核或执行获批变更
→ 保存状态变化事件
```

---

### 第七阶段：实现 LangGraph 工作流

> 实施状态：已完成。分类、抽取、申请匹配、Validation、两段人工审核、
> SQLite checkpoint 和恢复 API 已整合；Reply Agent 按阶段边界留到第八阶段。

#### 阶段目标

在分类、抽取、匹配和状态管理分别可运行后，再整合成 LangGraph 工作流。

#### 推荐能力与节点

```text
load_email
classify_email
extract_information
match_application
determine_status
validate_status
propose_schedule
generate_reply
validate_results
human_review
save_result
```

正式系统采用确定性 Orchestrator 协调 Classification、Extraction、Application 和 Reply 四个核心 Agent。Schema、时间歧义、状态机和动作风险由确定性 Validation Node 校验。MIME 解析、数据库 CRUD、SMTP、日程和归档不包装成 Agent。

#### 推荐流程

```text
START
  ↓
load_email
  ↓
classify_email
  ↓
是否为求职邮件？
  ├─ 否 → save_result → END
  └─ 是
      ↓
extract_information
      ↓
match_application
      ↓
determine_status
      ↓
validate_status
      ↓
是否需要人工确认？
  ├─ 是 → interrupt
  └─ 否
      ↓
propose_schedule
      ↓
是否需要回复？
  ├─ 否 → save_result → END
  └─ 是
      ↓
generate_reply
      ↓
validate_results
      ↓
是否存在外部写动作或不确定项？
  ├─ 是 → human_review / interrupt
  └─ 否 → save_result
      ↓
save_result
      ↓
END
```

第一版保留分类、抽取、申请处理和回复四类核心 Agent，并由确定性 Orchestrator 协调。Validation Node 负责结构化校验，LangGraph 负责状态、路由、受限重试和人工中断，普通 Service/Executor 负责邮件协议、数据库、规则校验和获批动作执行。

---

### 第八阶段：实现回复生成、审核与发送（已完成）

> 阶段状态：已完成（2026-07-29）。实现证据见
> `docs/phase-8/reply-and-smtp-progress.md`；真实 DeepSeek、163 IMAP/SMTP、MySQL
> 三段审核闭环已通过。

#### 阶段目标

完成邮件回复闭环。

#### 回复生成接口

```http
POST /api/emails/{id}/generate-reply
```

回复生成时参考：

- 原始邮件
- 邮件类别
- 公司和岗位
- 用户姓名
- 用户回复偏好
- 相关时间信息

#### 审核流程

模型生成内容先保存到：

```text
reply_drafts.generated_body
```

用户可以：

- 直接通过
- 修改后通过
- 拒绝
- 重新生成

修改后的内容保存到：

```text
reply_drafts.reviewed_body
```

发送接口：

```http
POST /api/v1/reply-drafts/{id}/send
```

发送流程：

```text
检查草稿审核状态
→ 检查收件人和主题
→ 校验草稿版本、权限和发送幂等键
→ SMTP 发送
→ 更新发送状态
→ 保存发送时间
```

必须避免未审核发送、旧版本草稿发送、重复发送、收件人为空和错误标记发送成功。Agent 只生成正文，主题、称呼、签名和 MIME 由确定性 Formatter 统一组装一次，SMTP 层不得再次改写正文。

---

### 第九阶段：开发 Vue 前端

#### 阶段目标

围绕已完成的后端接口实现核心业务页面。

#### 多邮箱 Provider 扩展

邮箱配置不得在前端写死 163。第九阶段增加 Provider 预设层，在仍保持“单用户、
同一时间只启用一个邮箱账户”的前提下，支持：

- 163 邮箱；
- 126 邮箱；
- QQ 邮箱；
- Gmail；
- 自定义 IMAP/SMTP 邮箱。

选择预设 Provider 后，由前端自动填充 IMAP/SMTP 主机、端口和安全方式，普通用户
只需填写邮箱地址和后端凭据引用。服务器参数收纳在“高级设置”中；选择自定义邮箱
时才默认展开并要求用户填写。

本扩展继续使用现有 `credential_ref` 安全边界，不在浏览器、普通业务字段或日志中
保存授权码和应用专用密码。连接测试仍须分别展示 IMAP 和 SMTP 结果，不能因为收件
连接成功就把发件能力标记为可用。

Gmail 首版只支持应用专用密码方式，并在界面提示其账户需要满足 Google 的相关安全
条件；不实现“使用 Google 登录”。Outlook.com 和 Microsoft 365 不纳入本轮预设，
原因是当前密码登录适配层不能可靠支持 Exchange Online 的现代认证要求。后续应先
实现 OAuth2/XOAUTH2 凭据适配和令牌刷新，再启用 Outlook Provider，不能只增加一个
服务器地址选项就宣称支持。

多 Provider 验收至少覆盖：

1. 每个预设能映射到预期的 IMAP/SMTP 配置，切换 Provider 不遗留上一个预设值。
2. 自定义 Provider 能保存用户填写的主机、端口和安全方式。
3. 连接测试独立展示收件和发件结果，失败信息不泄露凭据。
4. 现有 163 真实邮箱同步、分析、审核和 SMTP 发送回归不受影响。
5. 前端测试覆盖 Provider 预设映射、自定义模式和高级设置显隐。

认证边界依据：

- [Google：使用应用专用密码登录](https://support.google.com/mail/answer/185833)
- [Microsoft：Exchange Online 停用基本身份验证](https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/deprecation-of-basic-authentication-exchange-online)
- [Microsoft：IMAP/POP/SMTP OAuth 认证](https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth)

#### 页面顺序

1. 邮箱配置
2. 邮件列表
3. 邮件详情
4. AI 分析结果
5. 回复审核
6. 求职看板
7. 求职详情
8. 系统日历
9. 智能任务审核中心

邮件中心采用三栏布局：

```text
左侧：邮箱账户、文件夹、邮件分类
中间：邮件列表
右侧：邮件详情和 AI 分析结果
```

求职看板按以下状态展示：

- 已投递
- 笔试
- 面试
- Offer
- 已拒绝

---

### 第十阶段：实现自动同步和提醒

#### 阶段目标

核心功能稳定后，将手动同步升级为定时同步。

#### 同步流程

```text
定时任务触发
→ 查询启用同步的邮箱账户
→ 获取新邮件 UID
→ 跳过已存在邮件
→ 解析邮件
→ 保存数据库
→ 调用分析工作流
→ 更新求职看板
```

建议先设置为每 5～10 分钟同步一次。

前期只实现系统内部日历：

```text
邮件提取时间
→ 保存 schedules 表
→ 前端日历展示
→ 到期前生成系统提醒
```

内部日历完成后，再考虑导出 `.ics` 文件或接入第三方日历。

---

### 第十一阶段：系统测试与优化

测试不能等到第十一阶段才开始。每个阶段都应同步增加单元测试、集成测试或脱敏 Fixture；本阶段负责补齐端到端、异常、安全、性能和回归测试。

#### 功能测试

- 邮箱连接
- 邮件同步
- 邮件去重
- 邮件正文解析
- AI 分类
- 信息抽取
- 求职记录匹配
- 状态更新
- 日程创建
- 回复生成
- 人工审核
- SMTP 发送

#### 异常测试

- 邮箱授权码错误
- IMAP 连接超时
- SMTP 发送失败
- DeepSeek API 超时
- 模型返回格式错误
- 邮件正文为空
- HTML 邮件解析失败
- 时间表达模糊
- 用户拒绝审核
- 重复点击发送
- 工作流中断后恢复
- IMAP `UIDVALIDITY` 变化
- 模型结构化输出 Schema 校验失败
- 并发审核或发送同一草稿

#### 安全处理

- 邮箱授权码不能明文展示或写入普通数据库字段。
- 日志中不能输出授权码。
- API 参数必须校验。
- 防止重复发送邮件。
- 防止直接渲染不可信 HTML。
- 用户只能访问自己的数据；单用户 MVP 也应保留资源归属边界。
- `.env` 不能提交到 Git。

---

### 第十二阶段：论文实验与效果评价

#### 测试数据

根据时间与标注成本准备可复现、类别相对均衡的脱敏或模拟邮件集。可将 200～500 封作为目标范围，但先完成 30～50 封开发集和明确的标注规范，再根据实验稳定性扩充，不能只追求数量。

- 投递确认
- 笔试通知
- 面试邀请
- 面试改期
- 材料补充
- Offer
- 拒信
- 普通邮件
- 广告邮件
- 订阅邮件

前期开发先准备 30～50 封，系统稳定后再扩充。

#### 1. 邮件分类实验

评价指标：

- Accuracy
- Precision
- Recall
- F1-score
- 混淆矩阵
- Macro-F1（类别不均衡时作为重点指标）

#### 2. 信息抽取实验

按字段级 Precision、Recall、F1 和完全匹配率统计：

- 公司名称准确率
- 岗位名称准确率
- 时间提取准确率
- 截止日期准确率
- 地点提取准确率
- 邮件链接提取准确率

#### 3. 求职状态更新实验

比较三种方案：

1. 纯大模型判断
2. 规则关键词判断
3. 大模型加状态机校验

比较内容：

- 状态判断准确率
- 非法状态跳转次数
- 人工审核次数
- 错误更新次数
- 申请匹配准确率

实验结论可重点说明：

> 大语言模型具有较好的语义理解能力，但可能产生不稳定或不符合业务规则的状态更新；引入状态机校验和人工审核后，可以提高求职流程管理的准确性与可靠性。

#### 4. 回复生成评价

评价维度：

- 内容相关性
- 语言礼貌性
- 信息完整性
- 表达自然度
- 是否可以直接发送
- 用户修改程度

可统计：

- 直接通过率
- 修改后通过率
- 重新生成率
- 拒绝率

同时统计端到端任务成功率、时间/截止日期遗漏率、回复事实一致性、平均调用次数、Token、延迟和成本，用于判断 Multi-Agent 的收益是否覆盖额外复杂度。

---

## 四、推荐的实际开发顺序

```text
1. [已完成] 跑通参考项目并测试 DeepSeek、IMAP、SMTP 和端到端链路
2. [已完成] 完成源码分析、缺陷清单和复用评估
3. [已完成] 评审并冻结 MVP 业务范围、核心枚举、审核边界和验收标准
4. [已完成] 收敛项目骨架、State/checkpoint/Store、多 Agent 和基础设施决策
5. [已完成] 设计数据库逻辑 ER、约束、状态边界和迁移顺序
6. [已完成] 新建 FastAPI 项目并建立配置、SQLAlchemy、Alembic 和测试骨架
7. [已完成] 实现首批四个 ORM 模型、`20260727_0001` 迁移和离线 DDL 测试
8. [已完成] 在 MySQL 8 测试库验证 upgrade、current 和 schema check；downgrade 使用自动化离线测试
9. [已完成] 使用三个脱敏 Fixture 运行分类、抽取真实模型基线
10. 实现邮箱账户管理、Provider Adapter 和手动增量同步
11. 完成邮件列表、详情和安全正文解析接口
12. 实现求职记录候选匹配、状态建议和状态机校验
13. 实现任务/日程建议与审核数据模型
14. 实现回复草稿、统一格式化和审核状态机
15. 整合 LangGraph 协作工作流、checkpoint 与恢复接口
16. 实现获批动作 Executor 和带幂等保护的 SMTP 发送
17. 开发最小 Vue 邮件中心与审核页面，完成首个纵向闭环
18. 开发求职看板、申请详情和系统日历
19. 增加定时同步、提醒和必要的可观测性
20. 持续补齐单元、集成、端到端、异常和安全测试
21. 扩充并标注实验数据，完成基线、消融和效果评价
22. 整理论文、演示数据和答辩材料
```

---

## 五、当前最应该开始的任务

第一阶段已经完成，无需再次把“重新运行参考项目、编写 IMAP/SMTP 脚本”作为当前主任务。现在应先完成架构评审到正式开发的交接：

```text
第一步：[已完成] 冻结 MVP 验收场景、分类/阶段枚举和人工审核策略
第二步：[已完成] 收敛影响项目骨架的架构决策
第三步：[已完成] 制作数据库逻辑 ER 图并确定迁移顺序
第四步：[已完成] 创建 FastAPI、SQLAlchemy、Alembic 与测试骨架
第五步：[已完成] 实现 `users`、`email_accounts`、`job_applications` 和 `emails` ORM 模型及首批迁移
第六步：[已完成] 在 MySQL 8 测试库执行 upgrade、current 和 schema check
第七步：[已完成] 用三个脱敏 Fixture 完成分类与抽取真实模型基线
第八步：实现 `email_analyses` ORM、迁移和分析结果持久化
第九步：在正式模块及其集成测试中验证结构化输出和 interrupt/resume
第十步：完成申请匹配、草稿审核和 SMTP 发送的首个纵向闭环
```

当前阶段不需要先开发完整 Vue 页面。可以先通过 Swagger 和自动化测试跑通后端，但在验证可恢复 Human-in-the-Loop 时应尽早制作一个最小审核页面，避免直到后期才发现前后端审核状态难以衔接。
