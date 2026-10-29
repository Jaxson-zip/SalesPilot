import { expect, test, type Page } from "@playwright/test"

import { loginAs } from "./helpers"

const ok = (data: unknown) => ({ json: { code: 0, message: "ok", data } })

const customer = (i: number) => ({
  id: `00000000-0000-4000-8000-${String(i).padStart(12, "0")}`,
  name: `分页客户 ${String(i).padStart(3, "0")}`,
  industry: i % 2 ? "制造业" : "软件",
  level: "B",
  owner: { id: "u1", name: "张晨" },
  website: null,
  opportunity_amount: i * 100,
  last_followup_at: null,
})

/** 模拟 120 个客户的服务端分页；记下每次列表请求的查询参数 */
async function mockCustomers(page: Page) {
  const all = Array.from({ length: 120 }, (_, i) => customer(i + 1))
  const calls: URLSearchParams[] = []
  await page.route(/\/api\/customers\/facets/, (r) =>
    r.fulfill(
      ok({
        industry: [
          { value: "制造业", label: "制造业" },
          { value: "软件", label: "软件" },
        ],
        owner: [{ value: "u1", label: "张晨" }],
      }),
    ),
  )
  await page.route(/\/api\/customers\?/, (r) => {
    const params = new URL(r.request().url()).searchParams
    calls.push(params)
    const industry = params.getAll("industry")
    const rows = industry.length ? all.filter((c) => industry.includes(c.industry)) : all
    const no = Number(params.get("page") ?? 1)
    const size = Number(params.get("page_size") ?? 20)
    return r.fulfill(ok({ items: rows.slice((no - 1) * size, no * size), total: rows.length }))
  })
  return calls
}

test("客户列表服务端分页：翻页请求下一页，筛选发给接口并回到第 1 页（模拟接口）", async ({ page }) => {
  await loginAs(page, "sales")
  const calls = await mockCustomers(page)
  await page.goto("/customers")
  const grid = page.getByRole("table")
  await expect(grid).toContainText("分页客户 001")
  await expect(page.getByText("第 1 / 3 页")).toBeVisible()
  await expect(page.getByText("共 120 条").first()).toBeVisible()

  await page.getByRole("button", { name: "下一页" }).click()
  await expect(grid).toContainText("分页客户 051")
  await expect(grid).not.toContainText("分页客户 001")
  expect(calls.at(-1)?.get("page")).toBe("2")
  expect(calls.at(-1)?.get("page_size")).toBe("50")

  // 筛选项来自 facets（整个范围），选中后作为参数发给接口
  await page.getByRole("button", { name: "筛选" }).click()
  await page.getByRole("menuitem", { name: "行业" }).click()
  await page.getByRole("menuitemcheckbox", { name: "软件" }).click()
  await page.keyboard.press("Escape")
  await expect(page.getByText("第 1 / 2 页")).toBeVisible()
  const last = calls.at(-1)
  expect(last?.getAll("industry")).toEqual(["软件"])
  expect(last?.get("page")).toBe("1")
  await expect(page.getByText("共 60 条").first()).toBeVisible()
})

test("导出 CSV 按当前筛选取全部页（模拟接口）", async ({ page }) => {
  await loginAs(page, "sales")
  const calls = await mockCustomers(page)
  const exports: unknown[] = []
  await page.route(/\/api\/exports$/, (r) => {
    exports.push(r.request().postDataJSON())
    return r.fulfill(ok({ allowed: true, max_rows: 200 }))
  })
  await page.goto("/customers")
  await expect(page.getByText("第 1 / 3 页")).toBeVisible()
  const before = calls.length
  const download = page.waitForEvent("download")
  await page.getByRole("button", { name: "选项" }).click()
  await page.getByRole("menuitem", { name: "导出 CSV" }).click()
  const file = await download
  const text = await (await file.createReadStream()).toArray()
  const lines = Buffer.concat(text).toString("utf-8").trim().split(/\r\n/)
  expect(lines).toHaveLength(121) // 表头 + 120 行，不只是当前页的 50 行
  expect(exports[0]).toEqual({ entity: "customers", rows: 120 })
  const fetched = calls.slice(before).filter((p) => p.get("page_size") === "100")
  expect(fetched.map((p) => p.get("page"))).toEqual(["1", "2"])
})
