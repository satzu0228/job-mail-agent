# 项目文档导航

`docs/` 按文档用途分类，不按编写时间平铺。第一次阅读建议依次查看需求基线、架构
决策、数据库设计和实施计划；第一阶段材料主要用于追溯参考项目验证过程。

## 1. 需求与验收

- [MVP 范围与验收场景](requirements/mvp-scope-and-acceptance.md)：回答“首版做什么、
  不做什么，以及怎样算完成”。

## 2. 系统架构

- [架构决策记录](architecture/architecture-decisions.md)：记录技术选型、目录边界、
  checkpoint、HITL 和四 Agent 等已冻结决策。
- [多智能体系统设计](architecture/multi-agent-system-design.md)：说明四 Agent 的职责、
  State、节点、路由和人工审核流程。

## 3. 数据库

- [数据库 ER 设计](database/database-er-design.md)：定义 12 张业务表、关系、约束、
  数据流和迁移顺序。

## 4. 开发计划

- [开发实施计划](plans/implementation-plan.md)：记录阶段任务、交付物、测试和风险控制。

## 5. 阶段进展记录

- [第一阶段索引](phase-1/README.md)：参考项目运行、IMAP/SMTP 验证、源码分析、
  已知问题和复用结论。
- [第二阶段完成记录](phase-2/foundation-progress.md)：MVP、架构边界和正式后端骨架，
  并保留紧随其后的首批实现证据。
- [第三阶段进展](phase-3/database-and-api-progress.md)：数据库与基础接口的完成度、
  开发问题、验证结果和下一步。
- [第四阶段完成记录](phase-4/email-access-and-parsing-progress.md)：邮箱账户、连接测试、
  IMAP 增量同步、MIME/HTML 安全解析、幂等入库与真实 163 邮箱验收。
- [第五阶段完成记录](phase-5/single-email-analysis-progress.md)：单封邮件分类、抽取、
  统一分析 API、版本化持久化与真实模型联调。
- [第六阶段完成记录](phase-6/application-management-progress.md)：确定性候选查询、
  Application Agent、申请状态机、审核与幂等执行边界。
- [第七阶段完成记录](phase-7/langgraph-workflow-progress.md)：强类型 LangGraph
  工作流、加密 checkpoint、两段中断恢复、运行轨迹与真实 MySQL 验收。
- [第八阶段完成记录](phase-8/reply-and-smtp-progress.md)：Reply Agent、草稿审核、
  确定性格式化、三段工作流中断与 SMTP 幂等发送边界。
- [第九阶段前端进展](phase-9/vue-frontend-progress.md)：Vue 3 核心页面、飞书表格式
  求职进度、邮件/审核/日程/设置交互及真实数据浏览器验收。

## 文档职责规则

- 需求变化先更新 `requirements/`，再检查架构、数据库和验收是否受影响。
- 技术选型和重要取舍记录在 `architecture/architecture-decisions.md`，不要散落在计划中。
- 表、字段、约束和迁移顺序以 `database/database-er-design.md` 为准。
- 实际完成情况更新到 `plans/implementation-plan.md` 和根目录 `README.md`。
- 每个阶段只维护一份进展记录，并持续补充问题、原因、处理方式和遗留风险。
- 实验记录不得写成正式系统已经实现的能力。
