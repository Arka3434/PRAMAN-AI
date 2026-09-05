import { useEffect, useState } from 'react'
import { BarChart3, AlertCircle, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { KPICard } from '../components/ui/kpi-card'
import { PageHeader } from '../components/ui/page-header'
import { StatusBadge, type StatusBadgeVariant } from '../components/ui/status-badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table'
import { fetchDashboardOverview, type DashboardOverviewResponse } from '../lib/analyticsApi'

function mapOverallResultToBadge(result: string): StatusBadgeVariant {
  switch (result) {
    case 'COMPLIANT':
      return 'pass'
    case 'POTENTIAL_VIOLATIONS_DETECTED':
      return 'violation'
    case 'WARNINGS_OR_MANUAL_REVIEW':
      return 'warning'
    case 'PENDING_ANALYSIS':
    default:
      return 'neutral'
  }
}

function mapFindingStatusToBadge(ruleStatus: string | null, severity: string): StatusBadgeVariant {
  if (ruleStatus === 'POTENTIAL_VIOLATION' || severity === 'critical' || severity === 'major') {
    return 'violation'
  }
  if (ruleStatus === 'MANUAL_REVIEW') {
    return 'review'
  }
  if (ruleStatus === 'WARNING' || severity === 'warning') {
    return 'warning'
  }
  return 'neutral'
}

export function OverviewPage() {
  const [data, setData] = useState<DashboardOverviewResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchDashboardOverview()
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  const reviewQueueCount = data?.review_queue_count ?? 0
  const hasTrendData = data?.compliance_trend.some((b) => b.pass > 0 || b.warning > 0 || b.violation > 0) ?? false
  const hasBreakdownData = (data?.violation_breakdown.length ?? 0) > 0

  return (
    <div>
      <PageHeader
        title="Overview"
        description="Inspection performance, exception tracking, and recent decision outcomes across the compliance workflow."
        action={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => void loadData()} disabled={loading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button asChild>
              <Link to="/inspections/new">New Inspection</Link>
            </Button>
          </div>
        }
      />

      {error && (
        <div className="mb-6 flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-800">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-rose-600" />
            <span className="text-sm font-medium">{error}</span>
          </div>
          <Button variant="outline" size="sm" onClick={() => void loadData()}>
            Retry
          </Button>
        </div>
      )}

      {/* Operational Status Banner */}
      <div className="mb-6 rounded-2xl border border-sky-200 bg-gradient-to-r from-sky-50 to-blue-50 p-5 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm font-medium text-sky-700">Good morning, Field Operations</p>
            <h2 className="mt-1 text-2xl font-bold text-slate-900" data-testid="dashboard-headline">
              {loading
                ? 'Loading operational review status...'
                : reviewQueueCount > 0
                ? `Operational review is active with ${reviewQueueCount} item${reviewQueueCount === 1 ? '' : 's'} in review queue.`
                : 'Operational review is stable with 0 items needing attention.'}
            </h2>
          </div>
          <Button asChild data-testid="dashboard-review-queue-btn">
            <Link to="/inspections?status=review_required">Review Queue</Link>
          </Button>
        </div>
      </div>

      {/* 4 KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KPICard
          label="Inspections this month"
          value={loading ? '...' : String(data?.inspections_this_month ?? 0)}
          change={data ? `Total: ${data.total_inspections}` : undefined}
          tone="pass"
          icon={<BarChart3 className="h-5 w-5" />}
        />
        <KPICard
          label="Manual review queue"
          value={loading ? '...' : String(data?.review_queue_count ?? 0)}
          change={data ? (data.review_queue_count > 0 ? 'Action required' : 'Queue clear') : undefined}
          tone="review"
          icon={<BarChart3 className="h-5 w-5" />}
        />
        <KPICard
          label="Statutory violations"
          value={loading ? '...' : String(data?.statutory_violations_count ?? 0)}
          change={data ? (data.statutory_violations_count > 0 ? 'Flagged by engine' : 'Zero detected') : undefined}
          tone="violation"
          icon={<BarChart3 className="h-5 w-5" />}
        />
        <KPICard
          label="Average compliance score"
          value={loading ? '...' : data?.average_compliance_score !== null && data?.average_compliance_score !== undefined ? `${data.average_compliance_score}%` : '—'}
          change={data?.average_compliance_score !== null && data?.average_compliance_score !== undefined ? 'Evaluated checks' : 'No evaluations yet'}
          tone="pass"
          icon={<BarChart3 className="h-5 w-5" />}
        />
      </div>

      {/* Trend & Breakdown Charts */}
      <div className="mt-6 grid gap-6 xl:grid-cols-[1.5fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Compliance trend</CardTitle>
            <CardDescription>Pass rate vs warnings and statutory violations across recent calendar months.</CardDescription>
          </CardHeader>
          <CardContent className="h-[270px] p-4 pt-0" data-testid="compliance-trend-container">
            {hasTrendData && data ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.compliance_trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="month" stroke="#64748b" fontSize={12} />
                  <YAxis stroke="#64748b" fontSize={12} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="pass" fill="#10b981" radius={[6, 6, 0, 0]} name="Passed" />
                  <Bar dataKey="warning" fill="#f59e0b" radius={[6, 6, 0, 0]} name="Warning / Review" />
                  <Bar dataKey="violation" fill="#ef4444" radius={[6, 6, 0, 0]} name="Violation" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-center text-slate-400">
                <BarChart3 className="h-8 w-8 text-slate-300" />
                <p className="mt-2 text-sm font-medium text-slate-600">No inspection trend data recorded yet</p>
                <p className="text-xs text-slate-400">Run inspections to populate monthly statutory compliance history.</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Violation breakdown</CardTitle>
            <CardDescription>Statutory rule checks flagged as potential violations.</CardDescription>
          </CardHeader>
          <CardContent className="h-[270px] p-4 pt-0" data-testid="violation-breakdown-container">
            {hasBreakdownData && data ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data.violation_breakdown}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={48}
                    outerRadius={78}
                    paddingAngle={4}
                    stroke="#fff"
                  >
                    {data.violation_breakdown.map((entry) => (
                      <Cell key={entry.rule_id} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-center text-slate-400">
                <p className="text-sm font-medium text-slate-600">Zero statutory violations detected</p>
                <p className="mt-1 text-xs text-slate-400">All package declarations currently meet legal rules.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Inspections & Attention Required */}
      <div className="mt-6 grid gap-6 xl:grid-cols-[1.7fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Recent inspections</CardTitle>
            <CardDescription>Latest records evaluated in the inspection workflow.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-8 text-center text-sm text-slate-500">Loading recent inspections...</div>
            ) : (data?.recent_inspections.length ?? 0) === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No inspections recorded yet.{' '}
                <Link to="/inspections/new" className="font-semibold text-blue-600 hover:underline">
                  Start a new inspection
                </Link>{' '}
                to begin.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Inspection</TableHead>
                    <TableHead>Product</TableHead>
                    <TableHead>Inspector</TableHead>
                    <TableHead>Result</TableHead>
                    <TableHead>Score</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data?.recent_inspections.map((inspection) => (
                    <TableRow key={inspection.id} className="cursor-pointer hover:bg-slate-50">
                      <TableCell className="font-medium text-slate-900">
                        <Link to={`/inspections/${inspection.id}`} className="hover:text-blue-600 hover:underline">
                          {inspection.inspection_number}
                        </Link>
                      </TableCell>
                      <TableCell>{inspection.product_name ?? '—'}</TableCell>
                      <TableCell>{inspection.inspector_name ?? 'Field Officer'}</TableCell>
                      <TableCell>
                        <StatusBadge status={mapOverallResultToBadge(inspection.overall_result)} />
                      </TableCell>
                      <TableCell className="font-semibold text-slate-900">{inspection.score}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Attention required</CardTitle>
            <CardDescription>Findings requiring inspector verification or escalation.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {loading ? (
              <div className="p-6 text-center text-sm text-slate-500">Loading attention queue...</div>
            ) : (data?.attention_items.length ?? 0) === 0 ? (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-500">
                All operational items clear. No unreviewed statutory violations or manual verification items.
              </div>
            ) : (
              data?.attention_items.map((finding) => (
                <Link
                  key={finding.finding_id}
                  to={`/inspections/${finding.inspection_id}`}
                  className="block rounded-xl border border-slate-200 bg-slate-50 p-4 transition-colors hover:border-slate-300 hover:bg-slate-100"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">{finding.title}</p>
                    <StatusBadge status={mapFindingStatusToBadge(finding.rule_status, finding.severity)} />
                  </div>
                  <p className="mt-2 text-sm text-slate-600">
                    {finding.product_name ?? finding.inspection_number}
                  </p>
                  <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                    <span>{finding.rule_check_id}</span>
                    <span className="font-medium capitalize text-slate-700">{finding.severity}</span>
                  </div>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
