import { describe, expect, it } from "vitest"

import { buildTimeline } from "@/lib/timeline"
import type { Activity, FollowupItem } from "@/types/api"

const followup: FollowupItem = {
  id: "f1",
  type: "phone",
  content: "确认 50 人并发",
  source: "manual",
  occurred_at: "2026-10-24T02:12:00Z",
  created_at: "2026-10-24T03:00:00Z",
  owner: { id: "u1", name: "张晨" },
}

function act(
  id: string,
  action: string,
  at: string,
  actor: Activity["actor"] = { id: "u1", name: "张晨" },
  subject_type = "customer",
): Activity {
  return {
    id,
    subject_type,
    subject_id: "c1",
    actor,
    source: actor ? "manual" : "agent",
    action,
    content: null,
    created_at: at,
  }
}

describe("buildTimeline", () => {
  it("合并、倒序，并去掉与跟进重复的 followup.* 动态", () => {
    const list = buildTimeline(
      [followup],
      [
        act("a1", "followup.phone", "2026-10-24T02:12:00Z"),
        act("a2", "stage_changed", "2026-10-21T00:00:00Z"),
        act("a3", "create", "2026-10-25T00:00:00Z", null, "quote"),
      ],
    )
    expect(list.map((e) => e.key)).toEqual(["a-a3", "f-f1", "a-a2"])
    expect(list[0]).toMatchObject({ actor: "AI", icon: "ai", action: "生成了报价单" })
    expect(list[1]).toMatchObject({ actor: "张晨", action: "记录了电话", icon: "phone" })
    expect(list[2].icon).toBe("stage")
  })

  it("没有 occurred_at 时用 created_at；agent 记录显示为 AI", () => {
    const [e] = buildTimeline([{ ...followup, occurred_at: null, source: "agent" }], [])
    expect(e.at).toBe(followup.created_at)
    expect(e.actor).toBe("AI")
  })

  it("跟进没有 owner 时用 fallbackActor", () => {
    const [e] = buildTimeline([{ ...followup, owner: undefined }], [], "李薇")
    expect(e.actor).toBe("李薇")
  })
})
