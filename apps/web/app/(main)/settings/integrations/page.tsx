"use client"

import { BellRing, CircleCheck, CircleX, Loader2, Send } from "lucide-react"
import { useState } from "react"

import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { RoleGate } from "@/components/shell/RoleGate"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { useSaveWecom, useWecomConfig, useWecomTest, type WecomConfig } from "@/hooks/useWecom"

function time(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const SOURCE: Record<WecomConfig["source"], string> = {
  web: "网页配置",
  env: "环境变量 WECOM_WEBHOOK_URL",
  none: "未配置",
}

function WecomForm({ cfg }: { cfg: WecomConfig }) {
  const save = useSaveWecom()
  const test = useWecomTest()
  const [url, setUrl] = useState("")
  const [enabled, setEnabled] = useState(cfg.enabled)
  const [events, setEvents] = useState<string[]>(cfg.events)
  const toggle = (key: string, on: boolean) =>
    setEvents((list) => (on ? [...list, key] : list.filter((k) => k !== key)))

  return (
    <div className="w-full space-y-4 p-4 sm:p-5">
      <section className="space-y-3 rounded-lg border border-zinc-200 p-4 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-medium">企业微信群机器人</h3>
          {cfg.configured ? <Tag color="green">已配置</Tag> : <Tag>未配置</Tag>}
          <span className="text-xs text-zinc-400">
            来源：{SOURCE[cfg.source]}
            {cfg.webhook_masked ? ` · ${cfg.webhook_masked}` : ""}
          </span>
        </div>
        <ol className="list-decimal space-y-0.5 pl-5 text-xs text-zinc-500">
          <li>在企业微信里打开销售团队群 → 右上角「…」→「添加群机器人」→ 新建机器人；</li>
          <li>复制机器人的 Webhook 地址粘贴到下面，保存后点「发送测试消息」确认；</li>
          <li>地址中的 key 等同密码，保存后只显示首尾几位，不会出现在操作日志里。</li>
        </ol>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            type="password"
            autoComplete="off"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={
              cfg.configured
                ? "如需更换，粘贴新的 Webhook 地址"
                : "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=…"
            }
            aria-label="Webhook 地址"
          />
          {cfg.source === "web" ? (
            <Button
              variant="ghost"
              size="sm"
              className="shrink-0"
              disabled={save.isPending}
              onClick={() => save.mutate({ webhook_url: "", enabled, events })}
            >
              清除网页配置
            </Button>
          ) : null}
        </div>
        <label className="flex items-center gap-2">
          <Switch checked={enabled} onCheckedChange={setEnabled} aria-label="开启推送" />
          开启推送
        </label>
        <fieldset className="space-y-1.5">
          <legend className="mb-1 text-xs font-medium text-zinc-500">推送哪些消息</legend>
          {cfg.options.map((o) => (
            <label key={o.key} className="flex items-center gap-2">
              <Checkbox
                checked={events.includes(o.key)}
                onCheckedChange={(v) => toggle(o.key, v === true)}
                aria-label={o.label}
              />
              {o.label}
            </label>
          ))}
        </fieldset>
        <p className="text-xs text-zinc-400">
          消息里的链接指向 {cfg.web_base_url}（部署后在环境变量 WEB_BASE_URL 修改）。
        </p>
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!cfg.configured || test.isPending}
            onClick={() => test.mutate()}
          >
            {test.isPending ? <Loader2 className="animate-spin" /> : <Send />}
            发送测试消息
          </Button>
          <Button
            size="sm"
            disabled={save.isPending}
            onClick={() =>
              save.mutate(
                { webhook_url: url.trim() ? url.trim() : undefined, enabled, events },
                { onSuccess: () => setUrl("") },
              )
            }
          >
            保存
          </Button>
        </div>
      </section>

      <section aria-label="最近推送" className="rounded-lg border border-zinc-200 text-sm">
        <h3 className="border-b border-zinc-100 px-4 py-2.5 font-medium">最近推送</h3>
        {cfg.recent.length === 0 ? (
          <p className="px-4 py-3 text-zinc-400">还没有推送记录。</p>
        ) : (
          <ul>
            {cfg.recent.map((p, i) => (
              <li
                key={`${p.at}-${i}`}
                className="flex items-start gap-2 border-b border-zinc-100 px-4 py-2 last:border-0"
              >
                {p.ok ? (
                  <CircleCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" />
                ) : (
                  <CircleX className="mt-0.5 size-4 shrink-0 text-red-500" />
                )}
                <span className="w-24 shrink-0 text-xs text-zinc-400 tabular-nums">{time(p.at)}</span>
                <span className="min-w-0 flex-1">
                  {p.title}
                  {p.error ? <span className="block text-xs text-red-600">{p.error}</span> : null}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

/** 消息推送：企业微信群机器人（审批提醒、赢单喜报、日报汇总与提醒） */
export default function IntegrationsPage() {
  const { role } = useSession()
  const q = useWecomConfig(role === "admin") // 非管理员只看锁定提示，不请求管理员接口
  return (
    <PageFrame title="消息推送" icon={BellRing} bodyClassName="overflow-y-auto">
      <RoleGate roles={["admin"]} lockedText="消息推送由系统管理员配置">
        {q.isPending ? (
          <div className="p-5">
            <Skeleton className="h-60 w-full" />
          </div>
        ) : q.isError ? (
          <QueryError error={q.error} onRetry={() => void q.refetch()} feature="消息推送" />
        ) : (
          <WecomForm cfg={q.data} />
        )}
      </RoleGate>
    </PageFrame>
  )
}
