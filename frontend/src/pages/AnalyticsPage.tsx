import { useEffect, useState } from 'react'
import { BarChart3, CheckCircle, Clock, AlertTriangle, RefreshCw, AlertCircle } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { KPICard } from '../components/ui/kpi-card'
import { PageHeader } from '../components/ui/page-header'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table'
import { fetchAnalyticsTrends, type AnalyticsTrendsResponse } from '../lib/analyticsApi'

export function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsTrendsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadTrends = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchAnalyticsTrends()
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics trends')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadTrends()
  }, [])

  const hasTrendData = data?.compliance_trend.some((b) => b.pass > 0 || b.warning > 0 || b.violation > 0) ?? false

  return (
    <div>
      <PageHeader
        title="Analytics"
        description="Operational analytics for statutory compliance performance, review queue health, and rule adjudication efficiency."
        action={
          <Button variant="outline" size="sm" onClick={() => void loadTrends()} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

      {error && (
        <div className="mb-6 flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-800">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-rose-600" />
            <span className="text-sm font-medium">{error}</span>
          </div>
          <Button variant="outline" size="sm" onClick={() => void loadTrends()}>
            Retry
          </Button>
        </div>
      )}

      {/* 4 KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KPICard
          label="Total inspections"
          value={loading ? '...' : String(data?.total_inspections ?? 0)}
          change={data ? `Draft: ${data.total_draft}` : undefined}
          tone="pass"
          icon={<BarChart3 className="h-5 w-5" />}
        />
        <KPICard
          label="Completed inspections"
          value={loading ? '...' : String(data?.total_completed ?? 0)}
          change={data ? `Finalized: ${data.total_completed}` : undefined}
          tone="pass"
          icon={<CheckCircle className="h-5 w-5" />}
        />
        <KPICard
          label="In review queue"
          value={loading ? '...' : String(data?.total_in_review ?? 0)}
          change={data ? (data.total_in_review > 0 ? 'Review pending' : 'Queue clear') : undefined}
          tone="review"
          icon={<Clock className="h-5 w-5" />}
        />
        <KPICard
          label="Adjudication yield rate"
          value={loading ? '...' : `${data?.adjudication_yield_rate ?? 0}%`}
          change={data ? `${data.reviewed_findings} of ${data.total_findings} reviewed` : undefined}
          tone="pass"
          icon={<AlertTriangle className="h-5 w-5" />}
        />
      </div>

      {/* Monthly Trend & Review Efficiency */}
      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Monthly compliance trend</CardTitle>
            <CardDescription>Engine evaluation outcomes (Pass, Warning, Violation) across recent reporting months.</CardDescription>
          </CardHeader>
          <CardContent className="h-[300px] p-4 pt-0" data-testid="analytics-monthly-trend">
            {hasTrendData && data ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.compliance_trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="month" stroke="#64748b" />
                  <YAxis stroke="#64748b" allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="pass" fill="#10b981" radius={[6, 6, 0, 0]} name="Passed Checks" />
                  <Bar dataKey="warning" fill="#f59e0b" radius={[6, 6, 0, 0]} name="Warning / Review" />
                  <Bar dataKey="violation" fill="#ef4444" radius={[6, 6, 0, 0]} name="Potential Violations" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-center text-slate-400">
                <BarChart3 className="h-8 w-8 text-slate-300" />
                <p className="mt-2 text-sm font-medium text-slate-600">No monthly trend data recorded yet</p>
                <p className="text-xs text-slate-400">Monthly breakdown will populate as package inspections are analyzed.</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Inspector review efficiency</CardTitle>
            <CardDescription>Operational adjudication outcomes recorded by field officers.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Total Findings</p>
                <p className="mt-1 text-2xl font-bold text-slate-900">{data?.total_findings ?? 0}</p>
                <p className="mt-1 text-xs text-slate-500">Evaluated by engine</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Adjudicated</p>
                <p className="mt-1 text-2xl font-bold text-slate-900">{data?.reviewed_findings ?? 0}</p>
                <p className="mt-1 text-xs text-slate-500">{data?.adjudication_yield_rate ?? 0}% yield rate</p>
              </div>
            </div>

            <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50/50 p-4 text-sm">
              <div className="flex items-center justify-between py-1">
                <span className="text-slate-600">Confirmed Violations:</span>
                <span className="font-semibold text-rose-600">{data?.confirmed_violations ?? 0}</span>
              </div>
              <div className="flex items-center justify-between border-t border-slate-200 py-1">
                <span className="text-slate-600">Overruled / Rejected in Field:</span>
                <span className="font-semibold text-emerald-600">{data?.rejected_findings ?? 0}</span>
              </div>
              <div className="flex items-center justify-between border-t border-slate-200 py-1">
                <span className="text-slate-600">Manual Review Escalated:</span>
                <span className="font-semibold text-amber-600">{data?.manual_review_items ?? 0}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Rule-by-Rule Performance Table */}
      <div className="mt-6">
        <Card>
          <CardHeader>
            <CardTitle>Statutory rule performance</CardTitle>
            <CardDescription>Evaluation statistics across all legal rule checks in the catalog.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-8 text-center text-sm text-slate-500">Loading rule statistics...</div>
            ) : (data?.rule_performance.length ?? 0) === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No statutory rule evaluations recorded yet.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Rule ID</TableHead>
                    <TableHead>Provision Title</TableHead>
                    <TableHead className="text-right">Total Evaluations</TableHead>
                    <TableHead className="text-right">Pass Count</TableHead>
                    <TableHead className="text-right">Violations</TableHead>
                    <TableHead className="text-right">Pass Rate</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data?.rule_performance.map((rule) => (
                    <TableRow key={rule.rule_id}>
                      <TableCell className="font-mono font-medium text-slate-900">{rule.rule_id}</TableCell>
                      <TableCell>{rule.rule_title}</TableCell>
                      <TableCell className="text-right font-medium">{rule.total_evaluations}</TableCell>
                      <TableCell className="text-right text-emerald-600">{rule.pass_count}</TableCell>
                      <TableCell className="text-right text-rose-600">{rule.violation_count}</TableCell>
                      <TableCell className="text-right font-semibold text-slate-900">
                        {rule.pass_rate !== null ? `${rule.pass_rate}%` : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
