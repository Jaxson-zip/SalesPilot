import { request, type APIRequestContext, type FullConfig } from "@playwright/test"

interface Envelope<T> {
  code: number
  message: string
  data: T
}

type Get = <T>(path: string) => Promise<T>

/**
 * 跑浏览器测试前确认企业微信推送已关闭：用例会真实新建报销、标赢单，
 * 推送打开时这些测试数据会被发到真实的销售群。
 */
async function checkPushOff(get: Get): Promise<void> {
  const cfg = await get<{ configured: boolean; enabled: boolean; source: string }>("/api/integrations/wecom")
  if (!cfg?.configured || !cfg.enabled) return
  throw new Error(
    `企业微信推送处于开启状态（来源：${cfg.source === "env" ? ".env 的 WECOM_WEBHOOK_URL" : "网页上保存的地址"}），` +
      "浏览器测试会把测试数据推送到真实的群。请先关闭再运行：\n" +
      "  sed -i 's/^WECOM_WEBHOOK_URL=/#E2E#WECOM_WEBHOOK_URL=/' .env && docker compose up -d --force-recreate core\n" +
      "跑完恢复：sed -i 's/^#E2E#WECOM_WEBHOOK_URL=/WECOM_WEBHOOK_URL=/' .env && docker compose up -d --force-recreate core",
  )
}

/**
 * 用例按演示数据写（审批要主管批、AI 走大模型部署行业包、明理的商机还没成交）。
 * 手动试用改过这些时，几十个用例会各自报出难懂的失败；这里先检查，一句话说清楚。
 */
async function checkDemoData(get: Get): Promise<void> {
  const problems: string[] = []
  if ((await get<{ solo_mode: boolean }>("/api/me")).solo_mode)
    problems.push("开着个人模式（seed --reset 不会关它，在「设置 → 业务规则 → 工作方式」里关闭）")
  const team = (await get<{ name: string; pack: string | null }[]>("/api/admin/teams")).find(
    (t) => t.name === "华南销售组",
  )
  if (team && team.pack !== "llm_deploy")
    problems.push(`华南销售组的默认行业包是 ${team.pack ?? "未设置"}，应为 llm_deploy`)
  const opps = await get<{ items: { name: string; stage: string }[] }>(
    "/api/opportunities?q=合同审查私有化&page_size=20",
  )
  const demo = opps.items.find((o) => o.name === "合同审查私有化")
  if (demo && ["won", "lost"].includes(demo.stage)) problems.push(`演示商机「合同审查私有化」已是 ${demo.stage}`)
  if (problems.length === 0) return
  throw new Error(
    `演示数据和用例的前提不一致：\n  - ${problems.join("\n  - ")}\n` +
      "请先恢复演示数据：docker compose exec core python -m seed --reset",
  )
}

async function adminGet(ctx: APIRequestContext): Promise<Get | null> {
  const res = await ctx.post("/api/auth/mock-login", {
    data: { role: "admin", access_code: process.env.E2E_ACCESS_CODE },
  })
  const login = (await res.json()) as Envelope<{ token: string }>
  if (login.code !== 0) return null // 登录失败交给各用例报错
  const headers = { Authorization: `Bearer ${login.data.token}` }
  return async <T>(path: string) => ((await (await ctx.get(path, { headers })).json()) as Envelope<T>).data
}

export default async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL = config.projects[0]?.use.baseURL ?? "http://127.0.0.1:3000"
  const ctx = await request.newContext({ baseURL })
  try {
    const get = await adminGet(ctx)
    if (!get) return
    await checkPushOff(get)
    // E2E_SKIP_DATA_CHECK=1：只跑不依赖演示数据的个别用例时跳过
    if (process.env.E2E_SKIP_DATA_CHECK !== "1") await checkDemoData(get)
  } finally {
    await ctx.dispose()
  }
}
