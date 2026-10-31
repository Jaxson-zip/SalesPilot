"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"
import type { AgentMode } from "@/lib/agent-mode"

export type Rating = "up" | "down"

export interface MyRating {
  message_index: number
  rating: Rating
  comment: string | null
}

export interface FeedbackItem {
  id: string
  user_name: string
  rating: Rating
  mode: string
  question: string
  answer: string
  comment: string | null
  created_at: string
}

export interface RateInput {
  message_index: number
  rating: Rating | null
  question: string
  answer: string
  comment?: string | null
}

export const feedbackKeys = {
  thread: (id: string) => ["ai-feedback", "thread", id] as const,
  review: ["ai-feedback", "review"] as const,
}

/** GET /api/ai-feedback/thread/{id}：本人在这个会话里的点赞 / 点踩（message_index → 评价） */
export function useMyRatings(threadId: string | null) {
  return useQuery({
    queryKey: feedbackKeys.thread(threadId ?? ""),
    queryFn: async ({ signal }) => {
      const rows = await api.get<MyRating[]>(
        `/api/ai-feedback/thread/${encodeURIComponent(threadId ?? "")}`,
        undefined,
        signal,
      )
      return Object.fromEntries(rows.map((r) => [r.message_index, r])) as Record<number, MyRating>
    },
    enabled: Boolean(threadId),
  })
}

/** POST /api/ai-feedback：点赞 / 点踩（rating 为 null 取消），先改界面再提交 */
export function useRate(threadId: string | null, mode: AgentMode) {
  const qc = useQueryClient()
  const key = feedbackKeys.thread(threadId ?? "")
  return useMutation({
    mutationFn: (body: RateInput) =>
      api.post<MyRating | null>("/api/ai-feedback", { ...body, thread_id: threadId, mode }),
    onMutate: async (body) => {
      await qc.cancelQueries({ queryKey: key })
      const prev = qc.getQueryData<Record<number, MyRating>>(key)
      const next = { ...prev }
      if (body.rating)
        next[body.message_index] = {
          message_index: body.message_index,
          rating: body.rating,
          comment: body.comment ?? null,
        }
      else delete next[body.message_index]
      qc.setQueryData(key, next)
      return { prev }
    },
    onError: (err, _b, ctx) => {
      qc.setQueryData(key, ctx?.prev)
      notifyError(err)
    },
    onSettled: () => void qc.invalidateQueries({ queryKey: feedbackKeys.review }),
  })
}

/** GET /api/ai-feedback?rating=down：主管看本团队、管理员看全部「没帮助」的回复 */
export function useFeedbackReview(enabled = true) {
  return useQuery({
    queryKey: feedbackKeys.review,
    queryFn: ({ signal }) => api.get<FeedbackItem[]>("/api/ai-feedback", { rating: "down", limit: 50 }, signal),
    enabled,
  })
}
