import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const ok = (data: unknown) => ({ json: { code: 0, message: "ok", data } })

const result = (created: boolean) => ({
  total: 3,
  ok: 2,
  skipped: 1,
  created,
  columns: ["name", "industry"],
  ignored_columns: ["备注"],
  rows: [
    { line: 2, name: "导入测试甲", owner_name: "张晨", status: "ok", message: null, warnings: [] },
    {
      line: 3,
      name: "深圳明理律师事务所",
      owner_name: "张晨",
      status: "duplicate",
      message: "客户已存在：深圳明理律师事务所",
      warnings: [],
    },
    {
      line: 4,
      name: "导入测试乙",
      owner_name: "张晨",
      status: "ok",
      message: null,
      warnings: ["名称相似：乙方科技，确认不是同一家"],
    },
  ],
})

test("销售批量导入客户：下载模板、预览问题行、确认导入（模拟写接口）", async ({ page }) => {
  const calls: string[] = []
  await page.route(/\/api\/customers\/import(\/preview)?$/, (r) => {
    const preview = r.request().url().endsWith("/preview")
    calls.push(preview ? "preview" : "import")
    return r.fulfill(ok(result(!preview)))
  })
  await loginAs(page, "sales")
  await page.goto("/customers")
  await page.getByRole("button", { name: "批量导入" }).click()
  const dialog = page.getByRole("dialog", { name: "批量导入客户" })
  await expect(dialog).not.toContainText("「负责人」列") // 销售没有负责人列

  const download = page.waitForEvent("download")
  await dialog.getByRole("button", { name: "下载模板" }).click()
  expect((await download).suggestedFilename()).toBe("客户导入模板.csv")

  // 不支持的格式在浏览器里就拦下，不上传
  await dialog
    .getByLabel("选择要导入的文件")
    .setInputFiles({ name: "a.xls", mimeType: "application/vnd.ms-excel", buffer: Buffer.from("x") })
  await expect(dialog.getByText("只支持 .csv 和 .xlsx 文件")).toBeVisible()
  expect(calls).toEqual([])

  await dialog.getByLabel("选择要导入的文件").setInputFiles({
    name: "客户.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("客户名称,行业,备注\n导入测试甲,制造业,x\n"),
  })
  const preview = dialog.getByRole("region", { name: "导入预览" })
  await expect(preview).toContainText("共 3 行：可导入 2 行，跳过 1 行（重复 1）")
  await expect(preview).toContainText("没有识别的列（不会导入）：备注")
  await expect(preview).toContainText("客户已存在：深圳明理律师事务所")
  await expect(preview).toContainText("名称相似：乙方科技")
  await expect(preview).not.toContainText("导入测试甲") // 正常行不列出
  await dialog.getByRole("button", { name: "导入 2 个客户" }).click()
  await expect(page.getByText("已导入 2 个客户")).toBeVisible()
  await expect(dialog).toHaveCount(0)
  expect(calls).toEqual(["preview", "import"])
})

test("主管导入说明里有负责人列；管理员没有导入入口", async ({ page }) => {
  await loginAs(page, "manager")
  await page.goto("/customers")
  await page.getByRole("button", { name: "批量导入" }).click()
  await expect(page.getByRole("dialog", { name: "批量导入客户" })).toContainText("填「公海」放入本团队公海")
  await page.getByRole("button", { name: "取消" }).click()
  await loginAs(page, "admin")
  await page.goto("/customers")
  await expect(page.getByRole("note", { name: "只读提示" })).toBeVisible()
  await expect(page.getByRole("button", { name: "批量导入" })).toHaveCount(0)
})
