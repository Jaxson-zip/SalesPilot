/** 对话区滚动跟随：停在底部附近时跟随新内容，用户往上翻看时不打扰 */

export interface ScrollState {
  /** 上一次 scroll 事件时的 scrollTop */
  lastTop: number
  top: number
  scrollHeight: number
  clientHeight: number
}

/**
 * scroll 事件后是否继续跟随。只有往上翻才停止：程序刚滚到底，内容又一下子变高（整段报价一起到），
 * 随后的 scroll 事件按新高度算会「离底部很远」，不能据此当成用户在翻看。
 */
export function nextStick(stick: boolean, s: ScrollState): boolean {
  if (s.scrollHeight - s.top - s.clientHeight < 80) return true
  return s.top < s.lastTop - 4 ? false : stick
}
