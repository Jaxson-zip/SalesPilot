# apps/web · SalesPilot 前端

Next.js 15 · React 19 · TypeScript（strict）· Tailwind 4 · shadcn/ui。界面以仓库根目录 `prototype/index.html` 为准，规范见 `AGENTS.md` 和 `docs/开发规范.md` §10.3–10.4。

```bash
pnpm install
pnpm dev          # http://localhost:3000，/api/* 代理到 CORE_INTERNAL_URL（默认 http://localhost:8000）
pnpm lint && pnpm typecheck && pnpm build
```

目录：`app/(main)/*` 页面 · `components/shell` 应用外壳 · `components/biz` 业务组件 · `components/agent` AI 会话组件 · `lib` 数据层（api / sse / session / artifacts）· `hooks` · `types`。
