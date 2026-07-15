# 参考项目登记

此目录存放只用于学习、运行和对比的第三方项目。第三方仓库由根目录 `.gitignore` 排除，不直接合并进本项目源码。

## Email-AI-Agent

- 仓库：https://github.com/parthshr370/Email-AI-Agent
- 本地目录：`references/Email-AI-Agent`
- 用途：验证 IMAP、SMTP、模拟邮件、LangGraph 状态流、分类、摘要、回复生成和人工审核。
- 许可证：MIT（克隆后再次以仓库内许可证文件为准）
- 克隆日期：2026-07-15
- 分支：`main`
- Commit ID：`f54ad9d37e2dbe5a6510095acbcf8b6fbf6a79ba`
- 本地修改：包含 LangChain 1.x 最小兼容修复，详见 `docs/phase-1/setup-notes.md`。

克隆命令：

```powershell
git clone https://github.com/parthshr370/Email-AI-Agent.git references/Email-AI-Agent
```

克隆完成后可使用以下命令记录版本：

```powershell
git -C references/Email-AI-Agent rev-parse HEAD
git -C references/Email-AI-Agent branch --show-current
```

不要将毕业设计的新功能长期堆叠在该目录中。必要的适配代码优先放入 `experiments/email-ai-agent/`，最终可复用能力再迁移到本项目自己的源码中。
