/**
 * 语音输入（浏览器自带的 Web Speech API）的纯函数和最小类型声明。
 * Chrome / Edge / Safari 有 SpeechRecognition（多数带 webkit 前缀），Firefox 没有：没有就不显示话筒按钮。
 * Chrome 的识别要连 Google 服务，国内网络下会报 network 错误；Edge 走微软服务，一般可用。
 */

export interface SpeechAlternativeLike {
  transcript: string
}

export interface SpeechResultLike {
  readonly isFinal: boolean
  readonly length: number
  [index: number]: SpeechAlternativeLike
}

export interface SpeechResultEventLike {
  readonly results: { readonly length: number; [index: number]: SpeechResultLike }
}

export interface RecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((e: SpeechResultEventLike) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}

export type RecognitionCtor = new () => RecognitionLike

/** 当前浏览器的 SpeechRecognition 构造函数；不支持返回 null */
export function recognitionCtor(w: object | undefined): RecognitionCtor | null {
  if (!w) return null
  const g = w as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return g.SpeechRecognition ?? g.webkitSpeechRecognition ?? null
}

/** 把一次识别的所有片段（含还没说完的临时结果）拼成一段文字 */
export function transcriptOf(e: SpeechResultEventLike): string {
  let text = ""
  for (let i = 0; i < e.results.length; i++) text += e.results[i][0]?.transcript ?? ""
  return text.trim()
}

/** 说的话接在已输入的内容后面：前面没有结尾标点就补一个逗号 */
export function joinSpeech(base: string, said: string): string {
  const head = base.replace(/\s+$/, "")
  if (!said) return base
  if (!head) return said
  if (/\n$/.test(base) || /[，。！？、；：,.!?;:]$/.test(head)) return `${base.endsWith("\n") ? base : head}${said}`
  return `${head}，${said}`
}

/** 识别出错时给用户看的话；用户自己停下（aborted）不提示 */
export function speechErrorText(error: string): string | null {
  switch (error) {
    case "aborted":
      return null
    case "no-speech":
      return "没有听到声音，再说一次试试"
    case "audio-capture":
      return "没有找到麦克风"
    case "not-allowed":
    case "service-not-allowed":
      return "麦克风权限被拒绝：点浏览器地址栏左侧的图标允许使用麦克风"
    case "network":
      return "语音识别连不上浏览器的识别服务（国内 Chrome 常见），可以换 Edge，或用输入法自带的语音输入"
    default:
      return `语音识别出错（${error}）`
  }
}
