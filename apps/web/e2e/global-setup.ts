import { request, type FullConfig } from "@playwright/test"

interface Envelope<T> {
  code: number
  message: string
  data: T
}

/**
 * 跑浏览器测试前确认企业微信推送已关闭：用例会真实新建报销、标赢单，
 * 推送打开时这些测试数据会被发到真实的销售群。
 */
export default async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL = config.projects[0]?.use.baseURL ?? "http://127.0.0.1:3000"
  const ctx = await request.newContext({ baseURL })
  try {
    const login = (await (
      await ctx.post("/api/auth/mock-login", { data: { role: "admin", access_code: process.env.E2E_ACCESS_CODE } })
    ).json()) as Envelope<{ token: string }>
    if (login.code !== 0) return // 登录失败交给各用例报错
    const res = await ctx.get("/api/integrations/wecom", { headers: { Authorization: `Bearer ${login.data.token}` } })
    const cfg = ((await res.json()) as Envelope<{ configured: boolean; enabled: boolean; source: string }>).data
    if (cfg?.configured && cfg.enabled) {
      throw new Error(
        `企业微信推送处于开启状态（来源：${cfg.source === "env" ? ".env 的 WECOM_WEBHOOK_URL" : "网页上保存的地址"}），` +
          "浏览器测试会把测试数据推送到真实的群。请先关闭再运行：\n" +
          "  sed -i 's/^WECOM_WEBHOOK_URL=/#E2E#WECOM_WEBHOOK_URL=/' .env && docker compose up -d --force-recreate core\n" +
          "跑完恢复：sed -i 's/^#E2E#WECOM_WEBHOOK_URL=/WECOM_WEBHOOK_URL=/' .env && docker compose up -d --force-recreate core",
      )
    }
  } finally {
    await ctx.dispose()
  }
}
