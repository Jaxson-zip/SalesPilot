"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"

export type OnboardingStepKey = "model" | "pricing" | "customer" | "followup" | "solution" | "share"

/** GET /api/onboarding（契约 §36） */
export interface OnboardingStep {
  key: OnboardingStepKey
  title: string
  detail: string
  href: string
  done: boolean
}

export interface Onboarding {
  steps: OnboardingStep[]
  done: number
  total: number
}

export function useOnboarding(enabled = true) {
  return useQuery({
    queryKey: ["onboarding"],
    queryFn: ({ signal }) => api.get<Onboarding>("/api/onboarding", undefined, signal),
    staleTime: 60_000,
    enabled,
  })
}
