import { createParser, type EventSourceMessage } from "eventsource-parser"

import { ApiError, buildHeaders, isAbortError, newRequestId, parseEnvelope } from "@/lib/api"
import { ErrorCode, type AgentEvent, type AgentEventName } from "@/types/api"

/** §8.3 的事件名白名单；未知事件直接忽略，保证向前兼容 */
const EVENT_NAMES: ReadonlySet<string> = new Set<AgentEventName>([
  "node.start",
  "tool.start",
  "tool.end",
  "tool.error",
  "node.retry",
  "interrupt",
  "artifact",
  "message.delta",
  "done",
  "error",
])

function isEventName(name: string): name is AgentEventName {
  return EVENT_NAMES.has(name)
}

/** 把一条 SSE 消息转成强类型事件；data 不是合法 JSON 时返回 null */
export function toAgentEvent(msg: EventSourceMessage): AgentEvent | null {
  const name = msg.event ?? "message"
  if (!isEventName(name)) return null
  try {
    const data: unknown = JSON.parse(msg.data)
    if (typeof data !== "object" || data === null) return null
    // 事件 data 的结构由后端契约保证（§8.3），这里只做事件名校验
    return { event: name, data } as AgentEvent
  } catch {
    return null
  }
}

export interface StreamOptions {
  signal?: AbortSignal
  onEvent: (event: AgentEvent) => void
}

/**
 * POST 一个 SSE 接口并逐条回调事件。
 * 不能用原生 EventSource（只支持 GET），所以用 fetch + eventsource-parser。
 * 如果后端返回的是 JSON（例如参数错误），按统一响应解析并抛出 ApiError。
 */
export async function postSSE(path: string, body: unknown, opts: StreamOptions): Promise<void> {
  const requestId = newRequestId()
  const headers = buildHeaders({ Accept: "text/event-stream", "Content-Type": "application/json" }, requestId)
  let res: Response
  try {
    res = await fetch(path, { method: "POST", headers, body: JSON.stringify(body), signal: opts.signal })
  } catch (err) {
    if (isAbortError(err)) throw err
    throw new ApiError({ code: ErrorCode.NETWORK, message: "网络连接失败，请确认 core 已启动", status: 0, requestId })
  }

  const contentType = res.headers.get("Content-Type") ?? ""
  if (!res.ok || !contentType.includes("text/event-stream")) {
    await parseEnvelope<unknown>(res, requestId)
    return
  }
  if (!res.body)
    throw new ApiError({ code: ErrorCode.INTERNAL, message: "响应没有内容", status: res.status, requestId })

  const parser = createParser({
    onEvent: (msg) => {
      const ev = toAgentEvent(msg)
      if (ev) opts.onEvent(ev)
    },
  })
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      parser.feed(value)
    }
  } finally {
    reader.releaseLock()
  }
}
