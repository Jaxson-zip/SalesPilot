/** 工具 / 节点 / 写操作的中文名（时间线标题用）；未登记的直接显示英文名 */
export const TOOL_TITLES: Record<string, string> = {
  start_solution: "转入出方案",
  parse_requirement: "理解需求",
  configure_solution: "配置方案",
  query_catalog: "查询产品目录",
  check_margin: "毛利校验",
  generate_quote: "生成报价单",
  search_customer: "匹配客户",
  search_policy: "查制度与知识库",
  get_business_overview: "查公司业务概览",
  submit_expense: "创建报销单",
  add_followup: "记录跟进",
  update_opportunity_stage: "推进商机",
  pipeline_summary: "漏斗统计",
  calc_commission: "计算提成",
  get_customer_context: "查询客户的商机和联系人",
  get_meddic: "查看赢单要素",
  get_battlecard: "查竞品战卡",
  get_company_intel: "查外部情报",
  create_task: "安排下一步",
  decide_approval: "处理审批",
  digest_material: "整理材料并写入",
}

export const ACTION_TITLES: Record<string, string> = {
  generate_quote: "生成报价单",
  submit_expense: "提交报销单",
  add_followup: "记录跟进",
  update_opportunity_stage: "更新商机阶段",
  create_task: "安排下一步",
  decide_approval: "处理审批",
  digest_material: "整理材料：记跟进、补联系人、安排下一步",
}

export function toolTitle(name: string): string {
  return TOOL_TITLES[name] ?? name
}

export function actionTitle(action: string): string {
  return ACTION_TITLES[action] ?? action
}

/** 模型选择（pill Select）。value 对应网关 models.yaml 的别名 / 分组名 */
export const MODEL_OPTIONS: { value: string; label: string }[] = [
  { value: "chat-agent", label: "自动" },
  { value: "hunyuan-turbo", label: "混元" },
  { value: "deepseek-chat", label: "DeepSeek" },
  { value: "deepseek-native", label: "DeepSeek（原生链路）" },
  { value: "qwen-plus", label: "Qwen" },
]
export const DEFAULT_MODEL = MODEL_OPTIONS[0].value

/** 行业包只读标签的占位值：正式数据来自商机产品线 → 行业包映射 */
export const DEFAULT_PACK_LABEL = "大模型部署"
