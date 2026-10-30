import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const ok = (data: unknown) => ({ json: { code: 0, message: "ok", data } })

const provider = (v: string, label: string, keySource: "web" | "env" | "none", available: boolean) => ({
  var: v,
  label,
  hint: "",
  key_source: keySource,
  tail: keySource === "web" ? "abcd" : null,
  saved_by: null,
  saved_at: null,
  broken: false,
  base: "",
  default_base: "https://example.com/v1",
  protocol: "",
  adapter: "",
  available,
  models: [],
})

const CONFIG = {
  gateway_ok: true,
  builtin: [
    provider("HUNYUAN_API_KEY", "腾讯混元", "none", false),
    provider("DEEPSEEK_API_KEY", "DeepSeek", "env", true),
  ],
  custom: [],
  groups: { "chat-agent": ["deepseek-chat"], embed: [], rerank: [] },
  group_defaults: { "chat-agent": ["deepseek-chat"], embed: [], rerank: [] },
  models: [
    {
      alias: "deepseek-chat",
      model: "deepseek-chat",
      link: "openai_compat",
      kind: "chat",
      tools: true,
      dims: null,
      available: true,
      unavailable_reason: null,
      provider: "DeepSeek",
    },
  ],
  embedding_dims: 1024,
  kb_chunks: 0,
  reindex: { status: "idle", target: null, done: 0, total: 0, error: null, by: null, at: null },
  allow_private_base: false,
}

test("模型接入：一家厂商一行，编辑在原地展开，只填 Key 就能保存（模拟接口）", async ({ page }) => {
  await loginAs(page, "admin")
  let saved: unknown = null
  await page.route(/\/api\/integrations\/models$/, (r) => r.fulfill(ok(CONFIG)))
  await page.route(/\/api\/integrations\/models\/builtin$/, async (r) => {
    saved = r.request().postDataJSON()
    await r.fulfill(ok(CONFIG))
  })
  await page.goto("/settings/models")

  await expect(page.getByRole("listitem", { name: "腾讯混元" }).getByRole("img", { name: "不可用" })).toBeVisible()
  await expect(page.getByRole("listitem", { name: "DeepSeek" }).getByRole("img", { name: "可用" })).toBeVisible()
  await expect(page.getByRole("listitem", { name: "默认模型" })).toContainText("对话 DeepSeek")
  // 收起时不显示输入框
  await expect(page.getByPlaceholder("输入 API Key")).toHaveCount(0)

  await page.getByRole("button", { name: "编辑腾讯混元" }).click()
  // 接口地址默认收在「自定义设置」里
  await expect(page.getByPlaceholder("https://example.com/v1")).toBeHidden()
  await page.getByPlaceholder("输入 API Key").fill("sk-test-1234")
  await page.getByRole("button", { name: "保存" }).click()
  await expect
    .poll(() => saved)
    .toEqual({ var: "HUNYUAN_API_KEY", base: "", protocol: "", adapter: "", key: "sk-test-1234" })
})
