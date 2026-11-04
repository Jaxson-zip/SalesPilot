import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { describe, expect, it } from "vitest"

import nextConfig, { PROXY_TIMEOUT_MS } from "../../next.config"

/** .env.example 里 core 等模型的超时（秒） */
function llmTimeoutMs(): number {
  const env = readFileSync(resolve(__dirname, "../../../../.env.example"), "utf8")
  const m = env.match(/^LLM_TIMEOUT_SECONDS=(\d+)/m)
  if (!m) throw new Error(".env.example 缺少 LLM_TIMEOUT_SECONDS")
  return Number(m[1]) * 1000
}

// 回归：代理超时和 core 的模型超时一样长时，模型一慢，日报草稿、AI 评估就返回 500
describe("代理超时", () => {
  it("比 core 等模型的时间长，core 来得及回退", () => {
    expect(nextConfig.experimental?.proxyTimeout).toBe(PROXY_TIMEOUT_MS)
    expect(PROXY_TIMEOUT_MS).toBeGreaterThan(llmTimeoutMs() + 10_000)
  })
})
