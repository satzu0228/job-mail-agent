# Email-AI-Agent 实验区

此目录用于保存不侵入参考仓库的运行入口、适配器、调试脚本和实验说明。

计划内容：

- 使用本项目脱敏样例执行参考工作流的模拟入口；
- DeepSeek/Qwen 模型接入验证；
- LangChain/LangGraph 版本兼容实验；
- IMAP 只读获取测试；
- SMTP 向测试邮箱发送测试；
- 节点输入、输出和状态变化记录。

约束：

- 不存放真实密钥和邮箱授权码；
- 不存放未经脱敏的真实邮件；
- SMTP 测试默认只向自己控制的测试邮箱发送；
- 实验代码不等同于最终系统代码，复用前需要重新审查和整理。

## 模拟流程启动

先在 `references/Email-AI-Agent/.env` 中配置：

```dotenv
DEEPSEEK_API_KEY=你的测试密钥
```

然后从项目根目录运行：

```powershell
conda activate email-ai-agent-ref
python experiments/email-ai-agent/run_mock.py --your-name "你的名字" --recipient-name "招聘负责人"
```

该入口只读取参考项目的 `sample_emails.json`，不会连接 IMAP，也不会通过 SMTP 发送邮件。

## IMAP 只读验证

在测试邮箱中准备好指定主题的邮件，并完成 `.env` 配置后，从项目根目录运行：

```powershell
conda activate email-ai-agent-ref
python experiments/email-ai-agent/test_imap.py --subject-contains "[JobMailAgent IMAP Test]" --timeout 15
```

该脚本登录后发送 RFC 2971 IMAP ID，以兼容网易邮箱的客户端身份检查。随后优先以 `EXAMINE` 只读方式打开收件箱；若服务器不支持则回退到 `SELECT INBOX`。邮件内容始终通过 `BODY.PEEK` 检查最近 10 封，不会调用模型或 SMTP，也不会主动改变邮件的已读状态。

## SMTP 自发自收验证

先预览配置和目标，不发送邮件：

```powershell
python experiments/email-ai-agent/test_smtp.py
```

确认服务器是 `smtp.163.com:465` 且发送方式为自发自收后，明确执行：

```powershell
python experiments/email-ai-agent/test_smtp.py --confirm
```

脚本只会向 `EMAIL_USERNAME` 自身发送一封固定主题的测试邮件，不调用大模型，也不向其他地址发送。
