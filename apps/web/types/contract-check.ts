/**
 * 前后端类型契约检查（只在 tsc 阶段生效，不产生运行时代码）。
 *
 * types/generated/openapi.d.ts 由 `pnpm gen:api` 从 docs/api/openapi.yaml 生成；
 * 业务代码仍用 types/*.ts 里手写的类型（字段注释、更窄的联合类型），这里逐个断言两边一致：
 * - 响应：后端返回的结构必须能赋给前端类型（后端删字段、改类型 → tsc 报错）
 * - 请求：前端发送的结构必须能赋给后端入参（前端漏必填字段、类型不对 → tsc 报错）
 */
import type { components } from "@/types/generated/openapi"
import type * as P from "@/lib/pack-rules"
import type * as C from "@/lib/settings"
import type * as T from "@/types/api"
import type * as M from "@/lib/materials"
import type * as Smp from "@/lib/samples"
import type * as A from "@/hooks/useAuditLogs"
import type * as I from "@/components/customers/CustomerIntel"
import type * as K from "@/hooks/useCompetitors"
import type * as U from "@/app/(main)/settings/ai-usage/page"
import type * as D from "@/hooks/useMeddic"
import type * as R from "@/hooks/useReports"
import type * as W from "@/hooks/useWecom"
import type * as Acc from "@/hooks/useAccounts"
import type * as LV from "@/lib/list-view"

type S = components["schemas"]
/** A 能赋给 B 时为 true；不能时类型为 false，下面的 `= true` 就会报错 */
type Fits<A, B> = [A] extends [B] ? true : false

/* ---------- 响应：后端 → 前端 ---------- */
export const responses = {
  UserBrief: true as Fits<S["UserBrief"], T.UserBrief>,
  CurrentUser: true as Fits<S["UserOut"], T.CurrentUser>,
  MockLoginData: true as Fits<S["LoginResult"], T.MockLoginData>,
  Customer: true as Fits<S["CustomerListItem"], T.Customer>,
  CustomerDetail: true as Fits<S["CustomerDetail"], T.CustomerDetail>,
  SimilarCustomer: true as Fits<S["SimilarCustomer"], T.SimilarCustomer>,
  ContactItem: true as Fits<S["ContactItem"], T.ContactItem>,
  FollowupItem: true as Fits<S["FollowupItem"], T.FollowupItem>,
  ChatModels: true as Fits<S["ChatModels"], T.ChatModels>,
  NextTask: true as Fits<S["NextTask"], T.NextTask>,
  UserItem: true as Fits<S["UserListItem"], T.UserItem>,
  AccountItem: true as Fits<S["AccountItem"], Acc.AccountItem>,
  FacetOption: true as Fits<S["FacetOption"], LV.FilterOption>,
  TempPassword: true as Fits<S["TempPassword"], Acc.TempPassword>,
  TeamItem: true as Fits<S["TeamItem"], Acc.TeamItem>,
  TaskItem: true as Fits<S["TaskItem"], T.TaskItem>,
  NotificationList: true as Fits<S["NotificationList"], T.NotificationList>,
  Templates: true as Fits<S["Templates"], T.Templates>,
  Activity: true as Fits<S["ActivityOut"], T.Activity>,
  AttachmentOut: true as Fits<S["AttachmentOut"], T.AttachmentOut>,
  DashboardData: true as Fits<S["Dashboard"], T.DashboardData>,
  OpportunityItem: true as Fits<S["OpportunityItem"], T.OpportunityItem>,
  OpportunityDetail: true as Fits<S["OpportunityDetail"], T.OpportunityDetail>,
  PipelineSummary: true as Fits<S["PipelineSummary"], T.PipelineSummary>,
  QuoteItem: true as Fits<S["QuoteListItem"], T.QuoteItem>,
  QuoteDetail: true as Fits<S["QuoteDetail"], T.QuoteDetail>,
  ContractList: true as Fits<S["ContractList"], T.ContractList>,
  PaymentPlanView: true as Fits<S["PaymentPlanView"], T.PaymentPlanView>,
  ExpenseItem: true as Fits<S["ExpenseItem"], T.ExpenseItem>,
  ExpenseDetail: true as Fits<S["ExpenseDetail"], T.ExpenseDetail>,
  ExpensePrecheck: true as Fits<S["ExpenseCheck"], T.ExpensePrecheck>,
  ApprovalItem: true as Fits<S["ApprovalItem"], T.ApprovalItem>,
  ProductLineItem: true as Fits<S["ProductLineItem"], T.ProductLineItem>,
  PackOut: true as Fits<S["PackOut"], T.PackOut>,
  SettingsOut: true as Fits<S["SettingsOut"], C.SettingsOut>,
  CatalogRow: true as Fits<S["CatalogRow"], P.PackCatalogItem>,
  KnowledgeDoc: true as Fits<S["KnowledgeDoc"], P.PackKnowledgeDoc>,
  KnowledgeUploadOut: true as Fits<S["KnowledgeUploadOut"], C.KnowledgeUploadOut>,
  MaterialOut: true as Fits<S["MaterialOut"], M.MaterialOut>,
  SampleItem: true as Fits<S["SampleItem"], Smp.SampleItem>,
  AuditItem: true as Fits<S["AuditItem"], A.AuditItem>,
  MeddicOut: true as Fits<S["MeddicOut"], D.MeddicOut>,
  CompetitorOut: true as Fits<S["CompetitorOut"], K.Competitor>,
  DailyReportOut: true as Fits<S["DailyReportOut"], R.DailyReport>,
  TeamDailyOut: true as Fits<S["TeamDailyOut"], R.TeamDaily>,
  WecomConfigOut: true as Fits<S["WecomConfigOut"], W.WecomConfig>,
  CompanyIntel: true as Fits<S["CompanyIntel"], I.CompanyIntel>,
  UsageStats: true as Fits<S["UsageStats"], U.UsageStats>,
  MeddicAssessOut: true as Fits<S["AssessOut"], D.MeddicAssessOut>,
} satisfies Record<string, true>

/* ---------- 请求：前端 → 后端 ---------- */
export const requests = {
  MockLogin: true as Fits<T.MockLoginRequest, S["MockLoginIn"]>,
  AgentChat: true as Fits<T.AgentChatRequest, S["ChatIn"]>,
  AgentResume: true as Fits<T.AgentResumeRequest, S["ResumeIn"]>,
  FollowupCreate: true as Fits<T.FollowupCreate, S["FollowupIn"]>,
  CustomerCreate: true as Fits<T.CustomerCreate, S["CustomerCreate"]>,
  CustomerTransfer: true as Fits<T.CustomerTransferIn, S["CustomerTransfer"]>,
  HandoverIn: true as Fits<T.HandoverIn, S["HandoverIn"]>,
  AccountCreate: true as Fits<Acc.AccountCreate, S["AccountCreate"]>,
  AccountUpdate: true as Fits<Acc.AccountUpdate, S["AccountUpdate"]>,
  TeamIn: true as Fits<Acc.TeamIn, S["TeamIn"]>,
  QuoteItemsPatch: true as Fits<T.QuoteItemsPatch, S["QuoteItemsUpdate"]>,
  TaskCreate: true as Fits<T.TaskCreate, S["TaskCreate"]>,
  TaskUpdate: true as Fits<T.TaskUpdate, S["TaskUpdate"]>,
  OpportunityCreate: true as Fits<T.OpportunityCreate, S["OpportunityCreate"]>,
  OpportunityUpdate: true as Fits<T.OpportunityUpdate, S["OpportunityUpdate"]>,
  CustomerUpdate: true as Fits<T.CustomerUpdate, S["CustomerUpdate"]>,
  PoolRelease: true as Fits<T.PoolRelease, S["PoolRelease"]>,
  StageChange: true as Fits<T.StageChange, S["StageChange"]>,
  PaymentIn: true as Fits<T.PaymentIn, S["PaymentIn"]>,
  ExpenseCreate: true as Fits<T.ExpenseCreate, S["ExpenseCreate"]>,
  ApprovalDecide: true as Fits<T.ApprovalDecideIn, S["ApprovalDecision"]>,
  ContactIn: true as Fits<T.ContactIn, S["ContactIn"]>,
  ContactUpdate: true as Fits<T.ContactUpdate, S["ContactUpdate"]>,
  PaymentPlanUpdate: true as Fits<T.PaymentPlanUpdate, S["PaymentPlanUpdate"]>,
  InvoiceIn: true as Fits<T.InvoiceIn, S["InvoiceIn"]>,
  ProductLineUpdate: true as Fits<T.ProductLineUpdate, S["ProductLineUpdate"]>,
  SettingsUpdate: true as Fits<C.SettingsUpdate, S["SettingsUpdate"]>,
  CatalogEdit: true as Fits<C.CatalogEdit, S["CatalogEdit"]>,
  MaterialIn: true as Fits<M.MaterialIn, S["MaterialIn"]>,
  SamplesIn: true as Fits<Smp.SamplesIn, S["SamplesIn"]>,
} satisfies Record<string, true>
