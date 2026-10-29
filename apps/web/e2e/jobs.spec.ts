import { expect, test, type Page } from "@playwright/test"

import { loginAs } from "./helpers"

const ok = (data: unknown) => ({ json: { code: 0, message: "ok", data } })

const job = (extra: Record<string, unknown>) => ({
  name: "task_due",
  title: "任务到期提醒",
  description: "给负责人发今天到期的任务。",
  enabled: true,
  run_at: "08:30",
  weekdays_only: false,
  options: [],
  last_run: null,
  ...extra,
})

/** 模拟定时任务接口（不改真实配置、不真的跑任务），记下写请求 */
async function mockJobs(page: Page) {
  const calls: { method: string; url: string; body: unknown }[] = []
  let jobs = [
    job({}),
    job({
      name: "pool_recycle",
      title: "公海自动回收",
      description: "长期没有跟进的客户自动退回公海。",
      enabled: false,
      run_at: "02:00",
      options: [{ key: "days", value: 90 }],
    }),
  ]
  const run = {
    id: "r-1",
    job: "task_due",
    trigger: "manual",
    triggered_by: "周敏",
    status: "ok",
    summary: "今天到期 2 个、逾期 0 个任务，新发提醒 2 条",
    started_at: new Date().toISOString(),
    finished_at: new Date().toISOString(),
  }
  let runs: unknown[] = []
  await page.route(/\/api\/admin\/jobs(\/[^/]+)?(\/run)?$/, async (r) => {
    const method = r.request().method()
    if (method === "GET") return r.fulfill(ok(jobs))
    const url = r.request().url()
    const body = method === "PATCH" ? r.request().postDataJSON() : null
    calls.push({ method, url, body })
    if (url.endsWith("/run")) {
      runs = [run]
      jobs = jobs.map((j) => (j.name === "task_due" ? { ...j, last_run: run } : j))
      return r.fulfill(ok(run))
    }
    const name = url.split("/").pop()
    jobs = jobs.map((j) =>
      j.name === name
        ? {
            ...j,
            ...body,
            options: body.options ? [{ key: "days", value: body.options.days }] : j.options,
          }
        : j,
    )
    return r.fulfill(ok(jobs.find((j) => j.name === name)))
  })
  // 后注册的优先匹配
  await page.route(/\/api\/admin\/jobs\/runs/, (r) => r.fulfill(ok(runs)))
  return calls
}

test("管理员配置定时任务：改时间、改天数、开启回收要确认、立即运行（模拟接口）", async ({ page }) => {
  const calls = await mockJobs(page)
  await loginAs(page, "admin")
  await page.goto("/settings/jobs")

  const due = page.getByRole("listitem", { name: "任务到期提醒" })
  await expect(due.getByText("还没有运行过")).toBeVisible()
  const time = page.getByLabel("任务到期提醒运行时间")
  await time.fill("09:15")
  await time.press("Enter")
  await expect.poll(() => calls.at(-1)?.body).toEqual({ run_at: "09:15" })

  const days = page.getByLabel(/公海自动回收：超过多少天没有跟进/)
  await days.fill("0")
  await expect(page.getByText("填 1～3650 之间的整数")).toBeVisible()
  await days.fill("120")
  await page.getByRole("listitem", { name: "公海自动回收" }).getByRole("button", { name: "保存" }).click()
  await expect.poll(() => calls.at(-1)?.body).toEqual({ options: { days: 120 } })

  // 会改数据的任务：开启前确认，取消就不发请求
  const count = calls.length
  await page.getByRole("switch", { name: "开启公海自动回收" }).click()
  await expect(page.getByRole("alertdialog")).toContainText("客户负责人会被清空")
  await page.getByRole("button", { name: "取消" }).click()
  expect(calls.length).toBe(count)
  await page.getByRole("switch", { name: "开启公海自动回收" }).click()
  await page.getByRole("button", { name: "确认开启" }).click()
  await expect.poll(() => calls.at(-1)?.body).toEqual({ enabled: true })
  await expect(page.getByRole("switch", { name: "关闭公海自动回收" })).toBeChecked()

  await due.getByRole("button", { name: "立即运行" }).click()
  await expect(page.getByText("已运行")).toBeVisible()
  await expect(due.getByText("手动 · 周敏")).toBeVisible()
  await expect(page.getByRole("region", { name: "运行记录" })).toContainText("任务到期提醒")
  expect(calls.at(-1)?.url).toMatch(/\/api\/admin\/jobs\/task_due\/run$/)
})

test("主管看不到定时任务", async ({ page }) => {
  await loginAs(page, "manager")
  await page.goto("/settings/jobs")
  await expect(page.getByText("定时任务由系统管理员配置")).toBeVisible()
  await expect(page.getByRole("link", { name: "定时任务" })).toHaveCount(0)
})
