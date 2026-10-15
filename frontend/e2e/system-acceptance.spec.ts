import { expect, test } from '@playwright/test'

import { installMockApi } from './mock-api'

async function expectNoPageOverflow(page: import('@playwright/test').Page) {
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    )
    .toBe(true)
}

test('E2E-01 五个核心页面可访问且无页面级横向溢出', async ({ page }) => {
  await installMockApi(page)
  for (const [path, title] of [
    ['/mail', '邮件'],
    ['/applications', '求职进度'],
    ['/calendar', '日程'],
    ['/reviews', '审核'],
    ['/settings/mailboxes', '邮箱设置'],
  ]) {
    await page.goto(path)
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
    await expectNoPageOverflow(page)
  }
})

test('E2E-02 Provider、连接、启用和自动同步配置可操作且不暴露凭据', async ({ page }) => {
  await installMockApi(page)
  await page.goto('/settings/mailboxes')
  await expect(page.getByText('a***@163.com')).toBeVisible()
  await expect(page.getByText('acceptance-test@163.com')).toHaveCount(0)
  await page.getByRole('button', { name: '添加邮箱' }).first().click()
  await page.getByRole('combobox', { name: '邮箱服务商' }).click({ force: true })
  await page.getByRole('option', { name: /QQ/ }).click()
  await page.getByPlaceholder(/qq\.com/).fill('new-test@qq.com')
  await expect(page.getByText('获取 QQ 邮箱授权码')).toBeVisible()
  await page.getByPlaceholder('粘贴刚刚生成的授权码').fill('fixture-authorization-code')
  await page.getByRole('dialog').getByRole('button', { name: '取消' }).click()
  await page.getByRole('button', { name: '更新授权码' }).click()
  await page.getByPlaceholder('粘贴新的邮箱授权码').fill('new-fixture-authorization-code')
  await page.getByRole('button', { name: '保存授权码' }).click()
  await expect(page.getByText('IMAP 接收连接')).toBeVisible()
  await expect(page.getByText('SMTP 发送连接')).toBeVisible()
})

test('E2E-03 收发切换、搜索、详情、附件和安全 HTML 可用', async ({ page }) => {
  await installMockApi(page)
  await page.goto('/mail')
  await expect(page.getByText('星河科技后端开发工程师一面邀请').first()).toBeVisible()
  const search = page.getByRole('textbox', { name: '搜索收件' })
  await search.fill('星河')
  await expect(page.locator('.mail-row')).toHaveCount(1)
  await search.fill('')
  await page.getByRole('button', { name: /已发送/ }).click()
  await expect(page.getByText('已发送：面试时间确认').first()).toBeVisible()
  await page.getByRole('button', { name: /^收件 2$/ }).click()
  await page.getByRole('tab', { name: /附件 2/ }).click()
  await expect(page.getByText('岗位说明.pdf')).toBeVisible()
  await expect(
    page.getByText('附件按不可信输入下载，系统不会自动执行其内容', { exact: true }),
  ).toHaveCount(2)
})

test('E2E-04 手动同步两次只新增一次并给出明确反馈', async ({ page }) => {
  await installMockApi(page)
  await page.goto('/mail')
  const syncButton = page.getByTitle('同步收件箱')
  await syncButton.click()
  await expect(page.getByText('同步和智能处理完成，共处理 1/1 封新邮件')).toBeVisible()
  await syncButton.click()
  await expect(page.getByText('同步完成，没有新邮件')).toBeVisible()
})

test('E2E-04A 后台同步完成后邮件页随轻量轮询刷新', async ({ page }) => {
  const state = await installMockApi(page)
  const delayedEmails = state.emails.splice(0)
  await page.goto('/mail')
  await expect(page.getByText('没有符合条件的收件')).toBeVisible()

  state.emails.push(delayedEmails[0])
  await expect(page.getByText('星河科技后端开发工程师一面邀请').first()).toBeVisible({
    timeout: 8_000,
  })
})

test('E2E-05 面试邀请可从分析进入人工审核', async ({ page }) => {
  await installMockApi(page)
  await page.goto('/mail/1')
  await expect(page.getByText('面试邀请', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '重新智能处理' }).click()
  await expect(page.getByText('智能处理已暂停，等待你的审核')).toBeVisible()
  await expect(page.getByText('星河科技', { exact: true })).toBeVisible()
  await expect(page.getByText('后端开发工程师', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '前往审核' }).click()
  await expect(page).toHaveURL(/\/reviews\/review-create-task$/)
  await expect(page.getByText('创建日程', { exact: true }).first()).toBeVisible()
})

test('E2E-06 批准、修改、拒绝与重复点击保护可理解', async ({ page }) => {
  const state = await installMockApi(page)
  await page.goto('/reviews/review-create-task')
  await expect(page.getByText('系统内部标识和协议字段保持只读')).toBeVisible()
  await page.getByRole('button', { name: '批准', exact: true }).dblclick()
  await expect(page.getByText('审核已批准')).toBeVisible()
  expect(state.decisions).toBe(1)
  await expect(page).toHaveURL(/\/reviews\/review-send-reply$/)
  await expect(page.getByText('发送回复', { exact: true }).first()).toBeVisible()

  state.reviews[0].decision_status = 'PENDING'
  state.reviews[0].execution_status = null
  state.reviews[0].display_status = 'PENDING'
  state.decisions = 0
  await page.goto('/reviews/review-create-task')
  await page.getByPlaceholder('拒绝时请填写原因；批准时可选').fill('时间需要进一步确认')
  await page.getByRole('button', { name: '拒绝', exact: true }).click()
  await expect(page.getByText('审核已拒绝')).toBeVisible()
})

test('E2E-07 求职进度显示一面、准确时间和申请时间线', async ({ page }) => {
  await installMockApi(page)
  await page.goto('/applications')
  await page.getByRole('button', { name: '已结束' }).click()
  await expect(page.getByText('暂无已结束的申请')).toBeVisible()
  await expect(page.getByRole('button', { name: '新建第一项申请' })).toHaveCount(0)
  await page.getByRole('button', { name: '全部' }).click()
  await expect(page.getByText('一面', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('2099/08/05 14:00')).toBeVisible()
  await page.getByText('2099/08/05 14:00').click()
  await page.getByRole('tab', { name: /时间线/ }).click()
  await expect(page.getByText('已投递 → 面试')).toBeVisible()
})

test('E2E-07A 无邮件通知时可由用户手动记录面试结果', async ({ page }) => {
  await installMockApi(page)
  await page.goto('/applications')
  const row = page.getByRole('row', { name: /星河科技 后端开发工程师/ })
  await expect(row.getByRole('button', { name: '待确认' })).toBeVisible()
  await row.getByRole('button', { name: '待确认' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('记录面试结果')).toBeVisible()
  await dialog.getByRole('radio', { name: /已通过/ }).click()
  await dialog.getByPlaceholder(/招聘网站显示/).fill('招聘网站显示一面通过')
  await dialog.getByRole('button', { name: '保存面试结果' }).click()

  await expect(page.getByText('面试结果已更新为“已通过”')).toBeVisible()
  await expect(row.getByRole('button', { name: '已通过' })).toBeVisible()
  await expect(page.getByText('一面已通过，下一阶段待确认')).toBeVisible()
  await page.goto('/calendar')
  await page.getByText('星河科技一面', { exact: true }).click()
  await expect(
    page.getByRole('dialog', { name: '星河科技一面' }).getByText('已完成', { exact: true }),
  ).toBeVisible()
})

test('E2E-07B 每轮面试通过后可递增登记下一轮，未登记时保持待确认', async ({ page }) => {
  const state = await installMockApi(page)
  state.applications[0].interview_result = 'PASSED'
  state.tasks[0].status = 'COMPLETED'
  await page.goto('/applications')

  await expect(page.getByText('下一阶段：待确认')).toBeVisible()
  const row = page.getByRole('row', { name: /星河科技 后端开发工程师/ })
  await row.getByRole('cell').first().click()
  await page.getByRole('button', { name: '登记下一轮面试' }).click()
  const dialog = page.getByRole('dialog', { name: '登记二面' })
  const startAt = dialog.getByRole('combobox', { name: /开始时间/ })
  await startAt.fill('2099-08-12 15:00:00')
  await startAt.press('Tab')
  await dialog.getByPlaceholder(/招聘人员电话通知/).fill('招聘人员电话通知二面')
  await dialog.getByRole('button', { name: '保存下一轮日程' }).click()

  await expect(page.getByText('二面已登记')).toBeVisible()
  await expect(page.getByText('二面', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: '待确认' }).first()).toBeVisible()
  expect(state.tasks.at(-1)?.interview_round).toBe(2)
})

test('E2E-08 模糊时间与多岗位冲突保持待确认', async ({ page }) => {
  await installMockApi(page, { ambiguous: true })
  await page.goto('/mail/2')
  await page.getByRole('tab', { name: '智能分析' }).click()
  await expect(page.getByText('待确认信息')).toBeVisible()
  await expect(page.getByText('岗位', { exact: true }).last()).toBeVisible()
  await expect(page.getByText('事件时间', { exact: true }).last()).toBeVisible()
  await page.goto('/applications')
  await expect(page.getByText('星河科技', { exact: true })).toHaveCount(2)
})

test('E2E-09 待审核工作流刷新后仍可恢复且不重复执行', async ({ page }) => {
  const state = await installMockApi(page)
  await page.goto('/reviews/review-create-task')
  await expect(page.getByText('创建日程', { exact: true }).first()).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: '批准', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '批准', exact: true }).click()
  expect(state.decisions).toBe(1)
})

test('E2E-10 链接安全、远程图片拦截、确认加载和 CID 图片显示', async ({ page }) => {
  await installMockApi(page)
  let trackerRequests = 0
  page.on('request', (request) => {
    if (request.url().includes('/e2e-tracker.png')) trackerRequests += 1
  })
  await page.goto('/mail/1')
  await expect(page.getByText(/该邮件包含 1 张外部图片/)).toBeVisible()
  expect(trackerRequests).toBe(0)
  const frame = page.frameLocator('iframe[title="邮件正文"]')
  await expect(frame.getByText('面试邀请')).toBeVisible()
  await expect(frame.getByRole('link', { name: '进入会议' })).toHaveAttribute(
    'rel',
    /noopener/,
  )
  expect(await page.evaluate(() => Boolean((window as Window & { __xssExecuted?: boolean }).__xssExecuted))).toBe(false)
  await page.getByRole('button', { name: '显示外部图片' }).click()
  await expect.poll(() => trackerRequests).toBe(1)
  await expect(frame.getByAltText('内嵌日程图')).toHaveAttribute('src', /^blob:/)
})

test('E2E-11 日历、提醒已读和日程状态更新可用', async ({ page }) => {
  await installMockApi(page)
  await page.goto('/calendar')
  await expect(page.getByText('星河科技一面即将开始')).toBeVisible()
  await page.getByRole('button', { name: '知道了' }).click()
  await expect(page.getByText('星河科技一面即将开始')).toHaveCount(0)
  await page.getByRole('button', { name: '月历' }).click()
  await expect(page.locator('.month-calendar')).toBeVisible()
})

test('E2E-11A 从面试日程放弃申请会同步取消日程并撤回申请', async ({ page }) => {
  await installMockApi(page)
  await page.goto('/calendar')
  await page.getByText('星河科技一面', { exact: true }).click()
  await page.getByRole('button', { name: '放弃申请' }).click()
  const dialog = page.getByRole('dialog', { name: '放弃这项申请' })
  await dialog.getByPlaceholder(/已接受其他 Offer/).fill('已接受其他公司的 Offer')
  await dialog.getByRole('button', { name: '确认放弃申请' }).click()
  await expect(page.getByText('申请已撤回，相关面试日程已取消')).toBeVisible()
  await expect(
    page.getByRole('dialog', { name: '星河科技一面' }).getByText('已取消', { exact: true }),
  ).toBeVisible()
  await page.goto('/applications')
  await page.getByRole('button', { name: '已结束' }).click()
  await expect(page.getByText('星河科技', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('已撤回', { exact: true }).first()).toBeVisible()
})

test('E2E-12 空列表、接口失败和窄屏布局状态可理解', async ({ page }) => {
  await installMockApi(page, { empty: true, failPath: '/review-tasks/query' })
  await page.setViewportSize({ width: 640, height: 720 })
  await page.goto('/reviews')
  await expect(page.getByText('验收故障注入：后端服务暂时不可用')).toBeVisible()
  await page.goto('/applications')
  await expect(page.getByText('还没有求职申请')).toBeVisible()
  await page.goto('/calendar')
  await expect(page.getByText('近期没有日程任务')).toBeVisible()
  await expectNoPageOverflow(page)
})

test('AC-10 归档与恢复必须经过人工审核且状态可回显', async ({ page }) => {
  const state = await installMockApi(page)
  await page.goto('/mail/1')

  await page.getByRole('button', { name: '归档邮件' }).click()
  await expect(page).toHaveURL(/\/reviews\/review-archive-1$/)
  await page.getByRole('button', { name: '批准', exact: true }).click()
  await expect(page.getByText('确认归档邮件')).toBeVisible()
  await page.getByRole('button', { name: '确认并归档' }).click()
  await expect(page.getByText('邮件已归档')).toBeVisible()

  state.decisions = 0
  await page.goto('/mail/1')
  await page.getByRole('button', { name: '恢复邮件' }).click()
  await expect(page).toHaveURL(/\/reviews\/review-restore-1$/)
  await page.getByRole('button', { name: '批准', exact: true }).click()
  await expect(page.getByText('确认恢复邮件')).toBeVisible()
  await page.getByRole('button', { name: '确认并恢复' }).click()
  await expect(page.getByText('邮件已恢复')).toBeVisible()
  await page.goto('about:blank')
})

test('发送审核可直接编辑正文且只提交正文变更', async ({ page }) => {
  const state = await installMockApi(page)
  await page.goto('/reviews/review-send-reply')

  const body = page.getByRole('textbox', { name: '回复正文' })
  await expect(body).toBeVisible()
  const bodyBox = await body.boundingBox()
  expect(bodyBox?.width).toBeGreaterThan(300)
  expect(bodyBox?.height).toBeGreaterThan(180)
  await body.fill('感谢邀请，我确认准时参加面试。')
  await page.getByRole('button', { name: '确认并发送' }).click()
  await expect(page.getByText('确认发送回复')).toBeVisible()
  await page.getByRole('button', { name: '确认并发送' }).last().click()
  await expect(page.getByText('回复已确认发送')).toBeVisible()

  expect(state.lastDecisionPayload?.reviewed_payload).toEqual({
    body: '感谢邀请，我确认准时参加面试。',
  })
})
