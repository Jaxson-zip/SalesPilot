import type { NextConfig } from "next"

/**
 * /api/* 代理到 core（避免跨域，前端只调用 core 的 /api/*）。
 * 注意：rewrites 在 `next build` 时求值并写入 routes-manifest，
 * 所以 Docker 镜像里 CORE_INTERNAL_URL 需要在构建阶段传入（见 Dockerfile 的 ARG）。
 */
const coreUrl = (process.env.CORE_INTERNAL_URL ?? "http://localhost:8000").replace(/\/$/, "")

/**
 * 代理等 core 响应的上限。Next 默认 30 秒，和 core 等模型的 LLM_TIMEOUT_SECONDS（30）一样长：
 * 模型一慢，core 还没来得及回退到模板 / 规则结果，代理就先断开返回 500。
 * 取 60 秒，与 Nginx 默认的 proxy_read_timeout 一致。
 */
export const PROXY_TIMEOUT_MS = 60_000

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: { proxyTimeout: PROXY_TIMEOUT_MS },
  // 关闭 gzip，避免 SSE（/api/agent/chat）被压缩缓冲导致无法逐字输出
  compress: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${coreUrl}/api/:path*` }]
  },
}

export default nextConfig
