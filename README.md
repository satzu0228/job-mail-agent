# Job Mail Agent

毕业设计：**基于大语言模型与多智能体协作的求职邮件智能管理系统设计与实现**。

第一阶段的参考项目运行与分析已经完成，当前进入正式系统架构评审和技术验证准备阶段。项目背景和长期协作约定见 [AGENTS.md](AGENTS.md)。

正式系统的当前架构评审稿见 [多智能体求职邮件系统设计稿](docs/design/multi-agent-system-design.md)。该设计基于第一阶段结论提出，尚未冻结。

## 当前目录

```text
job-mail-agent/
├── AGENTS.md                       # 项目长期背景与协作规则
├── README.md                       # 项目入口
├── .env.example                    # 环境变量示例，不包含真实凭据
├── references/                     # 第三方参考项目，不纳入本项目版本历史
├── experiments/email-ai-agent/     # 针对参考项目的独立实验与测试数据
├── docs/phase-1/                   # 第一阶段过程记录和验收材料
├── src/                            # 自主实现代码，第一阶段结束后再确定结构
└── tests/fixtures/emails/          # 脱敏邮件测试样例
```

## 第一阶段开始方式

在项目根目录执行：

```powershell
git clone https://github.com/parthshr370/Email-AI-Agent.git references/Email-AI-Agent
```

克隆完成后，先在 [参考项目登记表](references/README.md) 中记录 Commit ID 和许可证，再按 [第一阶段清单](docs/phase-1/README.md) 推进。

不要把 API Key、邮箱密码、授权码或包含个人信息的真实邮件提交到仓库。
