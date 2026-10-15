import path from 'node:path'

import { expect, test } from '@playwright/test'

import { installMockApi } from './mock-api'

const captureBaseline = process.env.CAPTURE_R0_BASELINE === '1'

test.describe('R0 页面基线截图', () => {
  test.skip(!captureBaseline, '仅在显式设置 CAPTURE_R0_BASELINE=1 时生成基线')

  test('记录五个关键页面', async ({ page }) => {
    await installMockApi(page)
    await page.setViewportSize({ width: 1440, height: 960 })

    const pages = [
      ['/mail', 'mail'],
      ['/applications', 'applications'],
      ['/calendar', 'calendar'],
      ['/reviews', 'reviews'],
      ['/settings/mailboxes', 'mailbox-settings'],
    ] as const

    for (const [route, filename] of pages) {
      await page.goto(route)
      await expect(page.locator('main')).toBeVisible()
      await page.evaluate(() => window.scrollTo(0, 0))
      await page.screenshot({
        path: path.resolve(
          '..',
          '.artifacts',
          'r0-baseline',
          `${filename}.png`,
        ),
        fullPage: true,
      })
    }
  })
})
