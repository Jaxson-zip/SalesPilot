import { expect, test, type Page } from "@playwright/test"

import { loginAs } from "./helpers"

interface Task {
  id: string
  title: string
  subject_type: string
  subject_id: string
}

async function openOppTask(page: Page): Promise<Task> {
  // page.request 和页面共用登录 Cookie
  const res = await page.request.get("/api/tasks?view=mine&status=open&subject_type=opportunity&page_size=50")
  const items = ((await res.json()) as { data: { items: Task[] } }).data.items
  const t = items.find((x) => x.subject_type === "opportunity")
  if (!t) throw new Error("演示数据里没有商机上的未完成任务")
  return t
}

test("点任务通知：已经在商机看板也能打开对应商机，并定位、高亮那条任务（通知接口模拟）", async ({ page }) => {
  await loginAs(page, "sales")
  await page.goto("/pipeline")
  const task = await openOppTask(page)
  const link = `/pipeline?opp=${task.subject_id}&task=${task.id}`
  await page.route(/\/api\/notifications(\?.*)?$/, (route) =>
    route.fulfill({
      json: {
        code: 0,
        message: "ok",
        data: {
          items: [
            {
              id: "n-1",
              type: "task_due",
              title: `任务今天到期：${task.title}`,
              body: null,
              link,
              read: false,
              created_at: new Date().toISOString(),
            },
          ],
          total: 1,
          unread: 1,
        },
      },
    }),
  )
  await page.route("**/api/notifications/read", (route) =>
    route.fulfill({ json: { code: 0, message: "ok", data: null } }),
  )
  await page.reload()

  // 已经在看板页时点通知（以前地址参数名不对，只停在看板上）
  await page.getByRole("button", { name: /^通知/ }).click()
  await page.getByText(`任务今天到期：${task.title}`).click()
  const sheet = page.getByRole("dialog")
  await expect(sheet).toBeVisible()
  const row = sheet.locator("[data-focused]")
  await expect(row).toContainText(task.title)
  await expect(row).toBeInViewport()

  // 关掉侧栏后地址清干净，再点同一条通知还能打开
  await page.keyboard.press("Escape")
  await expect(page).toHaveURL(/\/pipeline$/)
  await page.getByRole("button", { name: /^通知/ }).click()
  await page.getByText(`任务今天到期：${task.title}`).click()
  await expect(page.getByRole("dialog").locator("[data-focused]")).toContainText(task.title)
})

test("日报没保存就离开：先确认，离开后回来内容还在（不保存、不写库）", async ({ page }) => {
  await loginAs(page, "sales")
  await page.goto("/reports")
  const editor = page.getByRole("textbox", { name: "日报正文" })
  await expect(editor).toBeEnabled()
  const text = `浏览器测试：今天拜访了两家客户 ${Date.now()}`
  await editor.fill(text)
  await expect(page.getByText("有未保存的修改")).toBeVisible()

  // 点侧栏：拦下来问一句；取消留在原页
  await page.getByRole("link", { name: "工作台", exact: true }).click()
  const confirm = page.getByRole("alertdialog", { name: "日报还没保存" })
  await expect(confirm).toBeVisible()
  await confirm.getByRole("button", { name: "取消" }).click()
  await expect(page).toHaveURL(/\/reports$/)
  await expect(editor).toHaveValue(text)

  // 确认离开，再回来：恢复没保存的内容
  await page.getByRole("link", { name: "工作台", exact: true }).click()
  await page.getByRole("alertdialog", { name: "日报还没保存" }).getByRole("button", { name: "先离开" }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
  await page.getByRole("link", { name: "日报", exact: true }).click()
  await expect(page.getByRole("textbox", { name: "日报正文" })).toHaveValue(text)
  await expect(page.getByText("已恢复上次没保存的内容，记得保存")).toBeVisible()
})
