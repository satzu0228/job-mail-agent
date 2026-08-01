# Job Mail Agent 前端

第九阶段 Vue 3 前端，面向求职邮件处理、求职进度管理、日程和人工审核场景。

## 技术栈

- Vue 3 + TypeScript
- Vite
- Vue Router
- Element Plus
- Axios
- Vitest

## 本地运行

先启动 FastAPI：

```powershell
conda activate job-mail-agent
cd backend
uvicorn app.main:app --reload
```

再启动前端：

```powershell
cd frontend
npm install
npm run dev
```

开发地址为 `http://127.0.0.1:5173`。Vite 会把 `/api` 代理到
`http://127.0.0.1:8000`。

如果 API 部署在其他地址，可配置：

```text
VITE_API_BASE_URL=http://example.com/api/v1
```

## 页面

| 路由 | 页面 | 主要能力 |
|---|---|---|
| `/mail` | 邮件 | 同步、邮件列表与详情、AI 分析、归档/恢复审核入口 |
| `/applications` | 求职进度 | 飞书表格式进度表、筛选、新建与基本信息编辑 |
| `/calendar` | 日程 | 近期任务、月历、确认与完成状态 |
| `/reviews` | 审核 | 建议检查、批准/拒绝、SMTP 发送及 IMAP 移动确认 |
| `/settings/mailboxes` | 邮箱设置 | 添加账户、连接测试、手动同步 |

关键申请阶段不能在求职进度表中直接修改。创建申请、关联申请、修改阶段、
创建任务、发送回复和归档等动作继续遵循后端审核与幂等边界。

## 验证

```powershell
npm run type-check
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

生产构建输出到 `frontend/dist/`，该目录不进入版本控制。
Playwright 第一版以 Chromium 为强制基线，失败时的 trace、截图和报告输出到仓库根目录
`.artifacts/`。
