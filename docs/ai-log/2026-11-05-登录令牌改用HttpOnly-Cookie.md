# 登录令牌从 localStorage 改为 HttpOnly Cookie

- 日期：2026-11-05 · 开发者：Claude Code · 模块：core（auth、审计中间件、用量归属）、web（session、api、SSE、e2e）、infra/nginx
- 上一份：`2026-11-05-试用反馈-数据重置与上线加固.md`（当时把这一项列为后续任务，先用 CSP 降低风险）
- 起因：外部试用报告指出登录令牌存在 localStorage，页面一旦出现 XSS，脚本就能把令牌读走、在别处冒用。

## 任务卡
| 项 | 内容 |
|---|---|
| 目标 | JS 读不到登录令牌；网页登录、演示账户一键进入、切换账户、退出、AI 对话流式输出、附件预览照常可用 |
| 不变 | 改密码 / 重置密码 `token_version + 1` 作废旧登录；脚本和测试仍可用 `Authorization: Bearer` |
| 范围 | `app/common/auth.py`、`app/common/session_cookie.py`（新）、`app/crm/routers/auth.py`、`auth_service.check_access`、审计中间件、用量归属；web `lib/session.ts`、`lib/api.ts`、`lib/storage.ts`、`SessionProvider` |

## 设计
| 点 | 做法 |
|---|---|
| Cookie | `sp_session`，`HttpOnly; SameSite=Lax; Path=/`，有效期同 JWT。`Secure` 默认按请求判断：HTTPS 或 nginx 传来 `X-Forwarded-Proto: https`（`proxy.conf` 新增这个头）；`COOKIE_SECURE` 可强制。本地 HTTP 不加，否则浏览器不回传 |
| 鉴权顺序 | Bearer 头优先，其次 Cookie（`request_token`）。审计日志、AI 用量归属同样认 Cookie，不然网页操作全记成匿名 |
| CSRF | Cookie 鉴权的非 GET 请求必须带 `X-Requested-With`，否则 `40301 {"rule": "csrf"}`。跨站页面带不了自定义头（要 CORS 预检，core 不放行），再加 `SameSite=Lax` 两层。Bearer 请求不受影响（跨站页面拿不到 token） |
| 响应体里的 token | 浏览器发起的登录（带 `Origin` 头——浏览器对 POST 总会带，JS 改不了）响应体 `token: null`；脚本 / 测试不带 Origin，照旧拿到 token。否则 XSS 调一次 mock-login 就能拿到令牌带走，等于没改 |
| 退出 | 新增 `POST /api/auth/logout` 清 Cookie（HttpOnly Cookie 只能由服务端删）。不加 `token_version`，免得把同一账号的其他设备一起踢下线 |
| 前端登录态 | 不再看 localStorage：非公开页面一律用 `/api/me` 核实，401 由已有的 401 处理跳登录页；打开页面时顺手删掉旧版本留下的 `sp.token` |
| 切换演示账户 | 原来靠请求带当前 token 免访问口令，现在 Cookie 自动带上，`check_access` 改为接收 Bearer 或 Cookie 里的 token |

## AI 写错、人工修正
| 问题 | 原因 | 修正 |
|---|---|---|
| ruff 报 4 处行太长 | 中文注释按字符数估长度，没想到全角字符算两倍宽 | 拆行后 `ruff check` 通过 |
| 实测时用 curl 看 `Set-Cookie`，把一个本地演示账户的完整 token 打进了会话输出 | 只想看 Cookie 属性，没先把值遮掉 | 本地演示 token，24 小时过期；以后看 Cookie 属性用 `sed 's/=[^;]*/=…/'` 遮掉值 |
| 设计时考虑过的坑（写代码前排查到，不是写错后才发现） | 审计中间件和 `usage.bind` 各自解析 `Authorization`，只改 `get_current_user` 会让网页操作全记成匿名；响应体照旧返回 token 的话 XSS 调一次登录接口就能把令牌带走 | 统一走 `request_token`；浏览器请求（带 Origin）不返回 token，有回归测试 |

## 验证
- core：新增 `tests/api/test_session_cookie.py`（9 个：脚本登录返回 token + Cookie 属性、浏览器登录不返回 token 且 Cookie 可鉴权、缺 CSRF 头 40301、Bearer 不需要 CSRF 头、退出清 Cookie、未登录退出、HTTPS 代理下 Secure、配置强制 Secure、无效 Cookie 401）；全量 pytest 通过；OpenAPI 已导出、`pnpm gen:api` 已更新。
- web：新增 `lib/__tests__/auth-headers.test.ts`；lint / typecheck / Vitest 通过。e2e 辅助函数改为依赖浏览器上下文里的 Cookie（`page.request` 与页面共用 Cookie）。
- 浏览器实测：见下方「本地实测」。

## 本地实测
在本分支重建的 Docker 环境里，经 nginx（http://127.0.0.1:8080）和 Next.js 代理（http://127.0.0.1:3000）各走一遍：

| 场景 | 结果 |
|---|---|
| 演示账户一键进入（张晨、刘洋） | 进入工作台；`localStorage` 只有 `sp.role` / `sp.profile` 等偏好，没有 token；`document.cookie` 为空（HttpOnly） |
| 浏览器里调登录接口 | 响应体 `token: null`；`Set-Cookie: sp_session=…; HttpOnly; Max-Age=86400; Path=/; SameSite=lax`（本地 HTTP 无 Secure） |
| 页面脚本发不带 `X-Requested-With` 的写请求 | 403，`40301 {"rule":"csrf"}` |
| 左下角切换账户（张晨 → 陈静 → 张晨） | 问候语和 `/api/me` 都换成新账户 |
| 账号密码登录（`?next=/pipeline`） | 登录后回到 `/pipeline` |
| AI 对话 | 工具调用事件和回答逐步流出，正常结束 |
| 报销附件预览 | `GET /api/attachments/{id}/file` 200 |
| 报价分享 | Cookie 鉴权创建分享链接；退出登录后打开 `/share/q/…` 正常显示；测完已撤销 |
| 退出登录 | 回登录页，`/api/me` 401；直接打开 `/pipeline` 跳到 `/login?next=%2Fpipeline` |

残留风险：token 本身仍是 24 小时有效的 JWT，退出只删 Cookie，不作废已签发的 token（改密码才全部作废）；CSP 里的 `'unsafe-inline'` 仍在。
