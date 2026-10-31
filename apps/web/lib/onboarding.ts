/** 新手引导（契约 §36）的纯函数：上手清单什么时候显示、页面提示记在哪个本地键 */

export const ONBOARDING_DISMISSED_KEY = "sp.onboarding.dismissed"

/** 页面首次提示：每个页面一条，关掉后这台电脑上不再显示 */
export function tipKey(id: string): string {
  return `sp.tip.${id}`
}

/** 「重新显示新手引导」要清掉的本地键 */
export function guideKeys(): string[] {
  return [ONBOARDING_DISMISSED_KEY, ...Object.keys(PAGE_TIPS).map(tipKey)]
}

/** 全部做完、没有步骤（如未加载）或用户收起了，就不显示清单 */
export function showOnboarding(p: { done: number; total: number } | undefined, dismissed: boolean): boolean {
  if (!p || dismissed || p.total === 0) return false
  return p.done < p.total
}

/** 进度条宽度（0–100） */
export function progressPercent(done: number, total: number): number {
  if (total <= 0) return 0
  return Math.round((Math.min(done, total) / total) * 100)
}

/** 关键页面的首次提示文案（一句话说清楚这页最常用的操作） */
export const PAGE_TIPS = {
  ai: "直接说客户要做什么（如「给明理科技做一个质检小程序，预算 10 万」），AI 会拆需求、出三档方案和报价；也可以把聊天记录、会议纪要贴进来让它记跟进。改数据前都会先弹确认卡。",
  pipeline:
    "拖动卡片切换阶段（可以撤销），赢单要确认。点开一张卡片，「需要注意」里是按这单状态算出的下一步建议，一键交给 AI。",
  quotes:
    "报价审批通过后，打开报价点「分享给客户」，生成一条客户手机上就能看的链接（不含成本和毛利），客户打开时会提醒你。",
} as const
