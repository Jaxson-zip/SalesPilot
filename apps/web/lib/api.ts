import { getToken } from "@/lib/storage"
import { ErrorCode, type ApiEnvelope } from "@/types/api"

/** code ≠ 0 时抛出的错误，带后端错误码（§8.2） */
export class ApiError extends Error {
  readonly code: number
  readonly status: number
  readonly requestId: string | null
  readonly data: unknown

  constructor(opts: { code: number; message: string; status: number; requestId?: string | null; data?: unknown }) {
    super(opts.message)
    this.name = "ApiError"
    this.code = opts.code
    this.status = opts.status
    this.requestId = opts.requestId ?? null
    this.data = opts.data
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError
}

export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError"
}

export function newRequestId(): string {
  const rand =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID().replace(/-/g, "")
      : Math.random().toString(16).slice(2) + Date.now().toString(16)
  return `req_${rand.slice(0, 20)}`
}

/** 公共请求头：Bearer token + X-Request-ID（§8.1、规则 9） */
export function buildHeaders(extra?: HeadersInit, requestId: string = newRequestId()): Headers {
  const headers = new Headers(extra)
  headers.set("X-Request-ID", requestId)
  const token = getToken()
  if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`)
  return headers
}

function isEnvelope(value: unknown): value is ApiEnvelope<unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    "code" in value &&
    typeof (value as { code: unknown }).code === "number"
  )
}

/** 解析统一响应；非统一格式（例如 core 未启动时代理返回的 500）转成 NETWORK 错误 */
export async function parseEnvelope<T>(res: Response, requestId: string): Promise<T> {
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    body = null
  }
  if (!isEnvelope(body)) {
    throw new ApiError({
      code: res.ok ? ErrorCode.INTERNAL : ErrorCode.NETWORK,
      message: res.ok ? "响应格式不正确" : `服务不可用（HTTP ${res.status}），请确认 core 已启动`,
      status: res.status,
      requestId: res.headers.get("X-Request-ID") ?? requestId,
    })
  }
  if (body.code !== ErrorCode.OK) {
    throw new ApiError({
      code: body.code,
      message: body.message,
      status: res.status,
      requestId: body.request_id,
      data: body.data,
    })
  }
  return body.data as T
}

type Query = Record<string, string | number | boolean | undefined>

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  query?: Query
  body?: unknown
  signal?: AbortSignal
  headers?: HeadersInit
}

function withQuery(path: string, query?: Query): string {
  if (!query) return path
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) if (v !== undefined) qs.set(k, String(v))
  const s = qs.toString()
  return s ? `${path}?${s}` : path
}

/** 401 时的处理钩子（由 session 注册：重新 mock 登录），避免 api ↔ session 循环依赖 */
let unauthorizedHandler: (() => Promise<boolean>) | null = null
export function setUnauthorizedHandler(fn: (() => Promise<boolean>) | null): void {
  unauthorizedHandler = fn
}

async function send<T>(path: string, opts: RequestOptions): Promise<T> {
  const requestId = newRequestId()
  const headers = buildHeaders(opts.headers, requestId)
  // FormData（multipart 上传）由浏览器自动带 boundary，不能手动设置 Content-Type
  const isForm = typeof FormData !== "undefined" && opts.body instanceof FormData
  if (opts.body !== undefined && !isForm) headers.set("Content-Type", "application/json")
  let res: Response
  try {
    res = await fetch(withQuery(path, opts.query), {
      method: opts.method ?? "GET",
      headers,
      body: opts.body === undefined ? undefined : isForm ? (opts.body as FormData) : JSON.stringify(opts.body),
      signal: opts.signal,
    })
  } catch (err) {
    if (isAbortError(err)) throw err
    throw new ApiError({ code: ErrorCode.NETWORK, message: "网络连接失败，请确认 core 已启动", status: 0, requestId })
  }
  return parseEnvelope<T>(res, requestId)
}

/** 通用请求：自动带 token 与 X-Request-ID；401 时尝试重新登录一次 */
export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  try {
    return await send<T>(path, opts)
  } catch (err) {
    if (isApiError(err) && err.code === ErrorCode.UNAUTHORIZED && unauthorizedHandler) {
      const ok = await unauthorizedHandler()
      if (ok) return send<T>(path, opts)
    }
    throw err
  }
}

export const api = {
  get: <T>(path: string, query?: Query, signal?: AbortSignal): Promise<T> => apiFetch<T>(path, { query, signal }),
  post: <T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> =>
    apiFetch<T>(path, { method: "POST", body, signal }),
  put: <T>(path: string, body?: unknown): Promise<T> => apiFetch<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body?: unknown): Promise<T> => apiFetch<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string): Promise<T> => apiFetch<T>(path, { method: "DELETE" }),
  /** multipart/form-data 上传（票据等） */
  upload: <T>(path: string, form: FormData): Promise<T> => apiFetch<T>(path, { method: "POST", body: form }),
}

/**
 * 带鉴权地下载文件并返回 object URL（附件预览）。
 * 附件接口需要 Bearer token，不能直接用 <a href>，也不能把 token 放进 URL。
 */
export async function fetchBlobUrl(path: string): Promise<string> {
  const requestId = newRequestId()
  const res = await fetch(path, { headers: buildHeaders(undefined, requestId) })
  const type = res.headers.get("Content-Type") ?? ""
  if (!res.ok || type.includes("application/json")) return parseEnvelope<never>(res, requestId)
  return URL.createObjectURL(await res.blob())
}
