import type { NextConfig } from "next"

/**
 * /api/* 代理到 core（避免跨域，前端只调用 core 的 /api/*）。
 * 注意：rewrites 在 `next build` 时求值并写入 routes-manifest，
 * 所以 Docker 镜像里 CORE_INTERNAL_URL 需要在构建阶段传入（见 Dockerfile 的 ARG）。
 */
const coreUrl = (process.env.CORE_INTERNAL_URL ?? "http://localhost:8000").replace(/\/$/, "")

const nextConfig: NextConfig = {
  output: "standalone",
  // 关闭 gzip，避免 SSE（/api/agent/chat）被压缩缓冲导致无法逐字输出
  compress: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${coreUrl}/api/:path*` }]
  },
}

export default nextConfig
