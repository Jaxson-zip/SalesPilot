# SalesPilot web：Next.js standalone 多阶段构建
# 构建：docker build -t salespilot-web --build-arg CORE_INTERNAL_URL=http://core:8000 apps/web
FROM node:20-alpine AS base
# pnpm 11 需要 Node ≥ 22.13，Node 20 镜像固定使用 pnpm 10（lockfile v9 兼容）
RUN npm install -g pnpm@10.34.8 && apk add --no-cache libc6-compat
WORKDIR /app

# ---------- 依赖 ----------
FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

# ---------- 构建 ----------
FROM base AS builder
# rewrites 在构建时求值：/api/* → ${CORE_INTERNAL_URL}/api/*
ARG CORE_INTERNAL_URL=http://core:8000
ENV CORE_INTERNAL_URL=${CORE_INTERNAL_URL} \
    NEXT_TELEMETRY_DISABLED=1 \
    NODE_OPTIONS="--max-old-space-size=1024"
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

# ---------- 运行 ----------
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -S -g 1001 nodejs && adduser -S -u 1001 -G nodejs nextjs
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
USER nextjs
EXPOSE 3000
# 运行时仍读取 CORE_INTERNAL_URL（docker-compose 注入）；代理目标以构建时的值为准，两者保持一致
CMD ["node", "server.js"]
