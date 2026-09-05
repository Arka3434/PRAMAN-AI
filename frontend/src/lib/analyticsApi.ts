const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type ComplianceTrendBucket = {
  month: string
  pass: number
  warning: number
  violation: number
}

export type CategoryBreakdownItem = {
  name: string
  rule_id: string
  value: number
  fill: string
}

export type DashboardRecentInspection = {
  id: string
  inspection_number: string
  product_name: string | null
  inspector_name: string | null
  status: string
  score: string
  overall_result: string
  created_at: string
}

export type DashboardAttentionItem = {
  finding_id: string
  inspection_id: string
  inspection_number: string
  product_name: string | null
  title: string
  rule_check_id: string
  severity: string
  rule_status: string | null
  inspector_decision: string | null
  created_at: string
}

export type DashboardOverviewResponse = {
  total_inspections: number
  inspections_this_month: number
  statutory_violations_count: number
  review_queue_count: number
  average_compliance_score: number | null
  compliance_trend: ComplianceTrendBucket[]
  violation_breakdown: CategoryBreakdownItem[]
  recent_inspections: DashboardRecentInspection[]
  attention_items: DashboardAttentionItem[]
}

export type RulePerformanceStat = {
  rule_id: string
  rule_title: string
  total_evaluations: number
  pass_count: number
  violation_count: number
  warning_count: number
  manual_review_count: number
  pass_rate: number | null
}

export type AnalyticsTrendsResponse = {
  total_inspections: number
  total_completed: number
  total_in_review: number
  total_draft: number
  total_findings: number
  reviewed_findings: number
  confirmed_violations: number
  rejected_findings: number
  manual_review_items: number
  adjudication_yield_rate: number
  compliance_trend: ComplianceTrendBucket[]
  rule_performance: RulePerformanceStat[]
}

export type ViolationRegisterItem = {
  finding_id: string
  inspection_id: string
  inspection_number: string
  product_name: string | null
  product_category: string | null
  title: string
  rule_check_id: string
  rule_title: string
  legal_citation: string
  severity: string
  rule_status: string | null
  inspector_decision: string | null
  detected_value: string | null
  created_at: string
}

export type EscalationSummary = {
  critical_violations: number
  major_violations: number
  statutory_warnings: number
  manual_review_required: number
  unreviewed_count: number
  confirmed_count: number
  rejected_count: number
}

export type ViolationsRegisterResponse = {
  items: ViolationRegisterItem[]
  total: number
  limit: number
  offset: number
  summary: EscalationSummary
}

export async function fetchDashboardOverview(): Promise<DashboardOverviewResponse> {
  const res = await fetch(`${API_BASE}/api/v1/analytics/overview`)
  if (!res.ok) {
    throw new Error(`Failed to load dashboard overview: HTTP ${res.status}`)
  }
  return res.json() as Promise<DashboardOverviewResponse>
}

export async function fetchAnalyticsTrends(): Promise<AnalyticsTrendsResponse> {
  const res = await fetch(`${API_BASE}/api/v1/analytics/trends`)
  if (!res.ok) {
    throw new Error(`Failed to load analytics trends: HTTP ${res.status}`)
  }
  return res.json() as Promise<AnalyticsTrendsResponse>
}

export async function fetchViolationsRegister(params?: {
  severity?: string
  rule_status?: string
  review_decision?: string
  rule_id?: string
  search?: string
  limit?: number
  offset?: number
}): Promise<ViolationsRegisterResponse> {
  const q = new URLSearchParams()
  if (params?.severity && params.severity !== 'all') q.append('severity', params.severity)
  if (params?.rule_status && params.rule_status !== 'all') q.append('rule_status', params.rule_status)
  if (params?.review_decision && params.review_decision !== 'all') q.append('review_decision', params.review_decision)
  if (params?.rule_id && params.rule_id !== 'all') q.append('rule_id', params.rule_id)
  if (params?.search?.trim()) q.append('search', params.search.trim())
  if (params?.limit) q.append('limit', params.limit.toString())
  if (params?.offset !== undefined) q.append('offset', params.offset.toString())

  const res = await fetch(`${API_BASE}/api/v1/analytics/violations?${q.toString()}`)
  if (!res.ok) {
    throw new Error(`Failed to load violations register: HTTP ${res.status}`)
  }
  return res.json() as Promise<ViolationsRegisterResponse>
}
