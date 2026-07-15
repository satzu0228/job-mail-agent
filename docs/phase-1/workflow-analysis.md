# Email-AI-Agent 状态流与节点实现分析

## 1. 分析对象与结论摘要

- 参考仓库：`parthshr370/Email-AI-Agent`
- 基线 Commit：`f54ad9d37e2dbe5a6510095acbcf8b6fbf6a79ba`
- 本地运行环境：Python 3.11.15、LangChain 1.3.13、LangGraph 1.2.9
- 已验证模型：DeepSeek
- 已验证邮箱：163 测试邮箱

本项目当前实际实现并不是“多个自治 Agent 相互协商”的系统，而是一个由 LangGraph 编排的固定邮件处理工作流。图内注册了分类、摘要、回复三个节点；人工审核被作为回复节点内部的同步终端输入；IMAP 收件、邮件选择、发送确认和 SMTP 发件均在图外。

```text
IMAP/模拟邮件（图外）
        ↓
创建 EmailState（图外）
        ↓
filtering（图内，调用 LLM）
   ├── spam → END
   └── 其他 → summarization（图内，调用 LLM）
                         ↓
                    response（图内，调用 LLM）
                         └── 条件满足时调用终端人工审核
                         ↓
                        END
                         ↓
再次审核、发送/所谓 Gmail 草稿（图外）
                         ↓
SMTP（图外）
```

## 2. 程序入口和完整调用链

真实邮箱模式的入口为 `main.py`，执行顺序如下：

1. 从终端读取用户署名和收件人称呼。
2. 调用 `fetch_imap_emails()` 获取收件箱全部邮件。
3. 取列表最后 5 封，在终端中让用户选择一封。
4. 创建 `EmailState`，把选中邮件同时写入 `emails` 和 `current_email`。
5. 调用 `supervisor_langgraph()` 构建、编译并执行 LangGraph。
6. 图结束后打印回复，并在 `main.py` 中再次询问是否修改。
7. 询问发送或所谓 Gmail 草稿；选择发送后调用 `send_email()`。

模拟邮件入口不是原始 `main.py` 的一条完整分支。`core/email_ingestion.py` 只负责读取 `sample_emails.json`，本地使用 `experiments/email-ai-agent/run_mock.py` 将模拟邮件接入相同的 LangGraph 工作流。

## 3. EmailState 字段表

`EmailState` 使用 Python `dataclass` 定义，四个字段都采用可变容器，并通过 `default_factory` 为每个实例创建独立默认值。

| 字段 | 当前类型 | 初始值 | 写入位置 | 读取位置 | 实际用途 | 主要问题 |
|---|---|---|---|---|---|---|
| `emails` | `List[Dict[str, Any]]` | `[]` | `main.py`/模拟入口 | 当前图内基本不读取 | 保存本次待处理邮件集合 | 图实际只处理一封，列表与 `current_email` 职责重叠 |
| `history` | `List[Dict[str, Any]]` | `[]` | `response_node` | 最终日志 | 保存邮件 ID 和最终回复 | 缺少模型、时间、审核人、修改前后内容、发送结果等审计信息 |
| `metadata` | `Dict[str, Any]` | `{}` | `filtering_node` | 最终日志 | 以邮件 ID 保存分类 | 与 `current_email.classification` 重复，容易不一致 |
| `current_email` | `Dict[str, Any]` | `{}` | `main.py`、`supervisor_langgraph`、三个节点 | 三个节点和路由函数 | 当前处理邮件及分类、摘要、回复的动态载体 | `Dict[str, Any]` 无强类型约束，字段拼写和缺失难以及时发现 |

### 3.1 状态如何变化

初始状态：

```python
{
    "emails": [selected_email],
    "history": [],
    "metadata": {},
    "current_email": {
        "id": "8",
        "from": "...",
        "subject": "...",
        "body": "..."
    }
}
```

分类后新增：

```python
current_email["classification"] = "needs_review"
metadata["8"] = "needs_review"
```

摘要后新增：

```python
current_email["summary"] = "..."
```

回复后新增：

```python
current_email["response"] = "..."
history.append({"email_id": "8", "response": "..."})
```

`emails[0]` 与 `current_email` 通常指向同一个邮件字典，因此节点修改 `current_email` 时，`emails[0]` 也会同步出现分类、摘要和回复字段。这是 Python 可变对象引用产生的结果，并不是 LangGraph 自动复制或合并。

### 3.2 正式系统的状态方向

正式实现不应继续使用一个无限扩展的 `Dict[str, Any]`。建议至少明确区分：

- 原始邮件及解析结果；
- 分类建议及置信度；
- 结构化抽取结果；
- 申请匹配候选；
- 状态变更建议；
- 回复正文草稿；
- 人工审核状态；
- 已批准的外部动作；
- 节点错误与重试信息。

这些状态应采用 Pydantic 模型或等价强类型结构，并避免同一业务事实同时存放在多个字段。

## 4. Node 输入输出表

| 节点/函数 | 是否为已注册 Graph Node | 主要输入 | 主要输出/状态写入 | 外部调用 | 失败处理 |
|---|---:|---|---|---|---|
| `filtering_node` | 是 | `state.current_email.subject/body` | `current_email.classification`、`metadata[email_id]` | DeepSeek API、日志 | 模型或网络异常直接向上抛出；解析失败临时回退 `needs_review` |
| `summarization_node` | 是 | `state.current_email.body` | `current_email.summary` | DeepSeek API | 无节点级重试和降级，异常直接中断图 |
| `response_node` | 是 | 当前邮件、摘要、手工输入的收件人称呼和署名 | `current_email.response`、`history` | DeepSeek API；特定条件下读取终端输入 | 无模型重试；人工输入阻塞整个进程 |
| `post_filtering` | 否，条件路由函数 | 分类结果 | 返回 `END` 或 `summarization` 路由键 | 无 | 无显式异常处理 |
| `review_email` | 否，只是节点内普通函数 | 邮件、生成回复、终端输入 | 返回原回复或人工修改回复 | 标准输入/输出 | 无拒绝状态、无超时、无持久化 |

### 4.1 filtering_node

处理过程：

```text
读取主题和正文
→ 构造分类 Prompt
→ 调用 DeepSeek
→ 解析固定分类标签
→ 写入 current_email 和 metadata
```

当前枚举为 `spam`、`urgent`、`informational`、`needs_review`。原项目曾对整段模型解释执行关键词包含判断，实际出现“模型说没有 spam 特征，却被判成 spam”的问题；本地为运行验证改成了 JSON/纯标签精确解析。正式系统仍应改用框架支持的结构化输出、枚举校验、置信度和失败回退，而不是把临时解析函数直接视为最终方案。

### 4.2 summarization_node

处理过程：

```text
读取邮件正文
→ 调用 DeepSeek 生成 2~3 句摘要
→ 清理多余空白
→ 写入 current_email.summary
```

它没有接收主题、发件人、附件或历史线程，也没有输出结构化关键信息。摘要只是自由文本，不能替代正式系统需要的公司、岗位、时间、地点、链接、截止日期等结构化抽取结果。

### 4.3 response_node

处理过程：

```text
读取原邮件和摘要
→ 使用手工输入的 recipient_name、user_name
→ 调用 DeepSeek 生成回复正文
→ formatter 添加主题、称呼、落款
→ 若 needs_review 或回复包含英文 ?，调用 review_email
→ 写入 response 和 history
```

当前审核触发条件比较脆弱：

- 只看分类是否等于 `needs_review`；
- 只检查英文问号 `?`，不识别中文问号 `？`；
- 没有置信度、敏感动作、时间冲突、信息缺失等规则；
- 所有非 spam 邮件都会进入摘要和回复，即使 informational 通常无需回复。

## 5. Edge 和条件分支图

### 5.1 图结构

```text
                 ┌─────────────────────────┐
                 │       entry point       │
                 └────────────┬────────────┘
                              ↓
                 ┌─────────────────────────┐
                 │ filtering_node          │
                 │ 写 classification       │
                 └────────────┬────────────┘
                              ↓
                 ┌─────────────────────────┐
                 │ post_filtering           │
                 └────────┬───────────┬────┘
                     spam │           │ other
                          ↓           ↓
                       ┌─────┐  ┌─────────────────────┐
                       │ END │  │ summarization_node  │
                       └─────┘  │ 写 summary          │
                                └──────────┬──────────┘
                                           ↓
                                ┌─────────────────────┐
                                │ response_node       │
                                │ 写 response/history │
                                └──────────┬──────────┘
                                           ↓
                                        ┌─────┐
                                        │ END │
                                        └─────┘
```

### 5.2 Edge 表

| 来源 | 类型 | 条件/返回值 | 目标 | 含义 |
|---|---|---|---|---|
| 图入口 | Entry point | 固定 | `filtering` | 每封邮件先分类 |
| `filtering` | Conditional edge | 分类为 `spam`，路由函数返回 `END` | `END` | 垃圾邮件提前结束 |
| `filtering` | Conditional edge | 其他分类，返回 `summarization` | `summarization` | 所有非垃圾邮件继续摘要 |
| `summarization` | Normal edge | 无条件 | `response` | 摘要后必定生成回复 |
| `response` | Normal edge | 无条件 | `END` | 回复完成后结束图 |

### 5.3 路由实现问题

`post_filtering(state_update)` 声明了参数，却没有读取该参数，而是读取外层闭包中的 `state.current_email`。这使路由函数依赖外部可变对象，降低可测试性，也可能在并发或状态表示变化后产生错误。正确方向是只根据传入状态做纯函数式路由。

此外，图在每次调用 `supervisor_langgraph()` 时都会重新创建和编译。正式服务应在应用启动时构建一次图，通过依赖注入或单例方式复用编译结果。

## 6. Human-in-the-Loop 实现分析

### 6.1 当前实现

人工审核不是独立 Graph Node，也没有使用 LangGraph interrupt/checkpoint。它是 `response_node` 内的一次同步函数调用：

```python
if classification == "needs_review" or "?" in response:
    response = human_review_agent.review_email(email, response)
```

`review_email()` 通过终端 `input()` 询问是否修改：

- 输入 `y`：读取一行新文本并替换整个回复；
- 其他输入：直接保留模型回复。

图结束后，`main.py` 又进行一次英文修改询问，因此一次邮件可能被审核两次。

### 6.2 当前实现不具备的能力

- 没有真正的“拒绝草稿”状态；
- 没有审核任务 ID、审核人和审核时间；
- 没有保存模型原稿与人工修改稿；
- 没有 checkpoint，程序退出后无法恢复；
- Web 前端无法异步获取待审核任务；
- 阻塞终端输入不适合 FastAPI 服务；
- 审核后发送仍在图外，审核结论与最终动作缺少一致性约束；
- 没有防止重复发送的幂等键。

### 6.3 正式系统建议

```text
回复生成节点
  → 写入 Draft(status=PENDING_REVIEW)
  → LangGraph interrupt / 持久化 checkpoint
  → FastAPI 返回待审核任务
  → Vue 展示原邮件、抽取信息和草稿
  → 用户执行接受 / 修改 / 拒绝
  → 恢复工作流
  → 再次执行权限、状态和幂等校验
  → SMTP 发送
  → 保存发送结果和审计记录
```

“生成草稿”和“发送邮件”必须是两个分离动作；发送只能消费已经审核通过且未发送的草稿。

## 7. 图内/图外职责划分

| 能力 | 当前所在位置 | 是否在 LangGraph 图内 | 说明 |
|---|---|---:|---|
| 加载模拟邮件 | `email_ingestion.py`/实验入口 | 否 | 图执行前准备输入 |
| IMAP 登录、检索和解析 | `email_imap.py`、`main.py` | 否 | 图执行前一次性获取收件箱 |
| 邮件列表展示和人工选择 | `main.py` | 否 | 终端交互 |
| 创建初始 State | `main.py` | 否 | 将选中邮件放入状态 |
| 分类 | `filtering_node` | 是 | LLM 节点 |
| 分类后路由 | `post_filtering` | 是（条件边函数） | spam 结束，其他继续 |
| 摘要 | `summarization_node` | 是 | LLM 节点 |
| 回复生成 | `response_node` | 是 | LLM 节点 |
| 第一次人工审核 | `response_node` 内普通函数 | 形式上在节点执行期间，但不是独立节点 | 阻塞终端输入 |
| 第二次人工审核 | `main.py` | 否 | 与第一次审核重复 |
| 发送/所谓 Gmail 草稿选择 | `main.py` | 否 | 终端输入 |
| SMTP 发送 | `email_sender.py` | 否 | 图结束后执行 |
| 日志输出 | 多处 | 图内外都有 | 包含完整邮箱地址的隐私问题 |

当前图只覆盖“模型处理链”，没有覆盖完整邮件业务生命周期。论文和设计中不能把 IMAP、审核、SMTP 都描述成已经由 LangGraph 管理。

## 8. 外部副作用清单

外部副作用是指会访问外部系统、产生费用、泄露数据或改变外部状态的操作。

| 副作用 | 位置 | 当前行为 | 风险 | 正式系统控制要求 |
|---|---|---|---|---|
| IMAP 网络连接和登录 | `fetch_imap_emails` | 连接邮箱并读取收件箱全部邮件 | 凭据安全、邮箱限流、读取范围过大 | 加密保存授权信息、增量同步、超时重试、账户隔离 |
| 邮件内容读取 | `fetch_imap_emails` | `BODY.PEEK[]` 获取完整原始邮件 | 邮件正文和附件属于敏感数据 | 最小读取、隐私声明、脱敏日志、安全解析 |
| DeepSeek API 调用 | 三个 Agent | 邮件正文被发送给外部模型 | 隐私泄露、Token 成本、模型不可用 | 模型适配层、数据最小化、超时、重试、审计、可替换供应商 |
| 终端人工输入 | `review_email`、`main.py` | 阻塞进程等待输入 | 无法用于 Web 服务、无法恢复 | 持久化审核任务和异步恢复 |
| 日志输出 | Agent、IMAP、SMTP、main | 输出模型结果、完整邮箱、最终 State | 个人信息进入日志和截图 | 邮箱脱敏、正文分级、密钥过滤、日志保留策略 |
| SMTP 登录和发送 | `send_email` | 发送到原邮件 `From` 地址 | 错发、重复发送、格式错误 | 审核批准、地址解析校验、幂等键、发送审计、失败重试策略 |
| “发送草稿到 Gmail” | `send_draft_to_gmail` | 实际发送一封主题带 Draft 的普通邮件 | 用户误以为只是保存草稿 | 删除误导功能或实现真正的草稿持久化 |

当前项目没有数据库写入、日历写入和自动归档副作用，这些是毕业设计正式系统后续新增时需要重点控制的动作。

## 9. 已确认的主要实现缺陷

详细清单见 `known-issues.md`，与工作流关系最密切的问题包括：

1. 分类曾使用宽松字符串包含判断，可能错误路由。
2. Human-in-the-Loop 在节点内和图外重复执行。
3. Agent 已格式化完整邮件，SMTP 层又格式化一次。
4. 地址显示名通过 `split("@")` 解析，产生错误称呼。
5. 所谓 Gmail 草稿其实是一次真实发送。
6. 日志输出完整邮箱地址和完整最终 State。
7. 网易 IMAP ID、SMTP SSL 等供应商差异没有抽象成邮箱适配层。
8. 图每次处理邮件都重新构建和编译。
9. 所有非 spam 邮件都生成回复，缺少 `should_reply` 决策。
10. 没有 checkpoint、持久化、重试、幂等和发送审计。

## 10. 对毕业设计的启示

可借鉴的核心思想是：用共享 State 串联职责单一的处理节点，用条件边控制邮件处理分支，并在高风险动作前加入人工审核。

不能直接照搬的是：自由字典状态、阻塞式人工输入、硬编码模型/邮箱、图外发送、重复格式化以及缺乏持久化和审计的实现。正式系统应把 LangGraph 当作业务工作流的一部分，而不是让模型节点直接承担邮箱协议、状态管理和外部动作的全部责任。

