/** 客户时间线：合并跟进记录与动态，按时间倒序；去掉与跟进重复的 followup.* 动态 */
import { activityActionLabel, FOLLOWUP_TYPE_LABEL } from "@/lib/labels"
import type { Activity, FollowupItem } from "@/types/api"

export interface TimelineEntry {
  key: string
  kind: "followup" | "activity"
  /** 显示名；AI 产生的记录为 "AI" */
  actor: string
  action: string
  content: string | null
  at: string
  icon: "phone" | "visit" | "wechat" | "email" | "ai" | "stage" | "activity"
}

/** 跟进的动作文案：注明联系的是谁、关于哪一单，如「记录了电话 · 王律师 · 私有化部署」 */
export function followupAction(f: FollowupItem): string {
  const isAi = f.source === "agent" || f.type === "ai"
  const base = isAi ? "根据聊天摘要自动记录" : `记录了${FOLLOWUP_TYPE_LABEL[f.type] ?? "跟进"}`
  return [base, f.contact_name, f.opportunity_name].filter(Boolean).join(" · ")
}

function followupEntry(f: FollowupItem, fallbackActor: string): TimelineEntry {
  const isAi = f.source === "agent" || f.type === "ai"
  return {
    key: `f-${f.id}`,
    kind: "followup",
    actor: isAi ? "AI" : (f.owner?.name ?? fallbackActor),
    action: followupAction(f),
    content: f.content,
    at: f.occurred_at ?? f.created_at,
    icon: isAi ? "ai" : f.type,
  }
}

/** 动态是谁做的：AI、系统（定时任务）还是某个人。老数据没有 source=system，没有操作人的都算 AI */
export function activityActor(a: Pick<Activity, "source" | "actor">): "ai" | "system" | "user" {
  if (a.source === "system") return "system"
  return a.source === "agent" || a.actor === null ? "ai" : "user"
}

function activityEntry(a: Activity): TimelineEntry {
  const by = activityActor(a)
  const isAi = by === "ai"
  return {
    key: `a-${a.id}`,
    kind: "activity",
    actor: by === "system" ? "系统" : isAi ? "AI" : (a.actor?.name ?? "—"),
    // 客户时间线里带上的商机 / 报价 / 合同动态：注明是哪一个（如「发送了报价单 · Q-2026-013」）
    action:
      a.subject_type !== "customer" && a.subject_name
        ? `${activityActionLabel(a.action, a.subject_type)} · ${a.subject_name}`
        : activityActionLabel(a.action, a.subject_type),
    content: a.content,
    at: a.created_at,
    icon: isAi ? "ai" : a.action === "stage_changed" ? "stage" : "activity",
  }
}

/** fallbackActor：跟进记录没有返回 owner 时显示的人（一般是客户负责人） */
export function buildTimeline(followups: FollowupItem[], activities: Activity[], fallbackActor = "—"): TimelineEntry[] {
  const entries = [
    ...followups.map((f) => followupEntry(f, fallbackActor)),
    ...activities.filter((a) => !a.action.startsWith("followup.")).map(activityEntry),
  ]
  return entries.sort((x, y) => new Date(y.at).getTime() - new Date(x.at).getTime())
}
