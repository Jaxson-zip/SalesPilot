import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const ok = (data: unknown) => ({ json: { code: 0, message: "ok", data } })

const row = (id: string, name: string, target: number | null, achieved: number) => ({
  user: { id, name },
  role: "sales",
  team_name: "华南销售组",
  active: true,
  target,
  achieved,
  contracts: achieved ? 1 : 0,
  forecast: 5_000_000,
  rate: target ? achieved / target : null,
})

const board = (month: string, zhang: number | null, wang: number | null) => {
  const rows = [row("u-zc", "张晨", zhang, 30_000_000), row("u-wl", "王磊", wang, 10_000_000)]
  const set = rows.filter((r) => r.target !== null)
  const target = set.length ? set.reduce((s, r) => s + (r.target ?? 0), 0) : null
  return {
    month,
    editable: true,
    time_progress: 0.6,
    total: { target, achieved: 40_000_000, forecast: 10_000_000, rate: target ? 40_000_000 / target : null },
    rows,
  }
}

test("主管设置业绩目标：按万元填写、只提交改过的人、复制上月（模拟接口）", async ({ page }) => {
  const puts: unknown[] = []
  let current = board("2026-10", null, null)
  await page.route(/\/api\/targets(\?.*)?$/, (r) => {
    const month = new URL(r.request().url()).searchParams.get("month") ?? "2026-10"
    // 上个月：张晨 60 万、王磊 40 万
    if (month < current.month) return r.fulfill(ok(board(month, 60_000_000, 40_000_000)))
    return r.fulfill(ok({ ...current, month }))
  })
  await page.route(/\/api\/targets\/\d{4}-\d{2}$/, (r) => {
    const body = r.request().postDataJSON()
    puts.push(body)
    current = board(current.month, 80_000_000, null)
    return r.fulfill(ok(current))
  })
  await loginAs(page, "manager")
  await page.clock.setFixedTime(new Date("2026-10-20T10:00:00+08:00"))
  await page.goto("/targets")

  const summary = page.getByRole("region", { name: "目标汇总" })
  await expect(summary).toContainText("还没有设目标")
  await page.getByRole("button", { name: "设置目标" }).click()
  const zhang = page.getByLabel("张晨的目标（万元）")
  await zhang.fill("abc")
  await expect(page.getByText("目标填数字（万元）")).toBeVisible()
  await expect(page.getByRole("button", { name: /^保存/ })).toBeDisabled()
  await zhang.fill("80")
  await page.getByRole("button", { name: "保存（1 人）" }).click()
  await expect.poll(() => puts).toEqual([{ items: [{ user_id: "u-zc", amount: 80_000_000 }] }])
  await expect(summary).toContainText("¥800,000")
  await expect(summary).toContainText("50%") // 40 万 / 80 万
  await expect(summary).toContainText("落后于时间进度") // 时间进度 60%

  await page.getByRole("button", { name: "复制上月目标" }).click()
  await expect(page.getByLabel("张晨的目标（万元）")).toHaveValue("60")
  await expect(page.getByLabel("王磊的目标（万元）")).toHaveValue("40")
  await page.getByRole("button", { name: "取消" }).click()
  expect(puts).toHaveLength(1)
})

test("销售只看自己的目标，不能设置", async ({ page }) => {
  await loginAs(page, "sales")
  await page.goto("/targets")
  await expect(page.getByRole("region", { name: "目标汇总" })).toBeVisible()
  await expect(page.getByRole("button", { name: "设置目标" })).toHaveCount(0)
  const names = await page.locator("tbody tr td:first-child").allInnerTexts()
  expect(names).toEqual(["张晨"])
  await page.getByRole("button", { name: "下个月" }).click()
  await expect(page.getByRole("region", { name: "目标汇总" })).toContainText("还没有设目标")
})
