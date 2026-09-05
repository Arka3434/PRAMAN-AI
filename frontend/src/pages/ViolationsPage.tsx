import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, AlertCircle, Search, ExternalLink, RefreshCw, CheckCircle, ShieldAlert } from 'lucide-react'

import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { PageHeader } from '../components/ui/page-header'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table'
import { fetchViolationsRegister, type ViolationsRegisterResponse } from '../lib/analyticsApi'

export function ViolationsPage() {
  const [data, setData] = useState<ViolationsRegisterResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters
  const [severityFilter, setSeverityFilter] = useState('all')
  const [ruleStatusFilter, setRuleStatusFilter] = useState('all')
  const [reviewDecisionFilter, setReviewDecisionFilter] = useState('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 15

  const loadViolations = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchViolationsRegister({
        severity: severityFilter,
        rule_status: ruleStatusFilter,
        review_decision: reviewDecisionFilter,
        search: searchTerm,
        limit: pageSize,
        offset: page * pageSize,
      })
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load violations')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const handler = setTimeout(() => {
      void loadViolations()
    }, 200)
    return () => clearTimeout(handler)
  }, [severityFilter, ruleStatusFilter, reviewDecisionFilter, searchTerm, page])

  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / pageSize)
  const summary = data?.summary

  return (
    <div>
      <PageHeader
        title="Violations"
        description="Current exceptions, escalations, and statutory findings requiring review and regulatory action."
        action={
          <Button variant="outline" size="sm" onClick={() => void loadViolations()} disabled={loading}>
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
          <Button variant="outline" size="sm" onClick={() => void loadViolations()}>
            Retry
          </Button>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        {/* Left Column: Finding Register */}
        <Card>
          <CardHeader>
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <CardTitle>Finding register</CardTitle>
                <CardDescription>
                  Deterministic statutory outcomes mapped to inspection evidence and inspector decisions.
                </CardDescription>
              </div>
              <div className="text-xs text-slate-500">
                Showing {total > 0 ? page * pageSize + 1 : 0}–{Math.min((page + 1) * pageSize, total)} of {total} findings
              </div>
            </div>

            {/* Filter Controls */}
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Search finding or product..."
                  className="pl-9 text-sm"
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value)
                    setPage(0)
                  }}
                  data-testid="violations-search-input"
                />
              </div>

              <select
                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 shadow-sm focus:border-blue-500 focus:outline-none"
                value={severityFilter}
                onChange={(e) => {
                  setSeverityFilter(e.target.value)
                  setPage(0)
                }}
                data-testid="violations-severity-filter"
              >
                <option value="all">All Severities</option>
                <option value="critical">Critical</option>
                <option value="major">Major</option>
                <option value="warning">Warning</option>
              </select>

              <select
                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 shadow-sm focus:border-blue-500 focus:outline-none"
                value={ruleStatusFilter}
                onChange={(e) => {
                  setRuleStatusFilter(e.target.value)
                  setPage(0)
                }}
                data-testid="violations-rulestatus-filter"
              >
                <option value="all">All Engine Results</option>
                <option value="POTENTIAL_VIOLATION">Potential Violations</option>
                <option value="WARNING">Statutory Warnings</option>
                <option value="MANUAL_REVIEW">Manual Verification</option>
                <option value="PASS">Passes</option>
              </select>

              <select
                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 shadow-sm focus:border-blue-500 focus:outline-none"
                value={reviewDecisionFilter}
                onChange={(e) => {
                  setReviewDecisionFilter(e.target.value)
                  setPage(0)
                }}
                data-testid="violations-reviewdecision-filter"
              >
                <option value="all">All Review States</option>
                <option value="unreviewed">Unreviewed Queue</option>
                <option value="confirm">Confirmed Violations</option>
                <option value="reject">Overruled / Rejected</option>
                <option value="manual_review">Manual Review</option>
              </select>
            </div>
          </CardHeader>

          <CardContent className="p-0">
            {loading ? (
              <div className="p-12 text-center text-sm text-slate-500">Loading statutory findings...</div>
            ) : (data?.items.length ?? 0) === 0 ? (
              <div className="p-12 text-center text-sm text-slate-500">
                No statutory findings match the selected filters.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Rule / Finding</TableHead>
                    <TableHead>Product / Inspection</TableHead>
                    <TableHead>Engine Result</TableHead>
                    <TableHead>Inspector Action</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data?.items.map((item) => (
                    <TableRow key={item.finding_id} className="hover:bg-slate-50">
                      <TableCell className="max-w-[240px]">
                        <p className="font-mono text-xs font-semibold text-slate-900">{item.rule_check_id}</p>
                        <p className="truncate text-sm font-medium text-slate-800" title={item.title}>
                          {item.title}
                        </p>
                        <p className="truncate text-xs text-slate-500" title={item.legal_citation}>
                          {item.legal_citation}
                        </p>
                      </TableCell>

                      <TableCell className="max-w-[180px]">
                        <p className="truncate font-medium text-slate-900">{item.product_name ?? '—'}</p>
                        <Link
                          to={`/inspections/${item.inspection_id}`}
                          className="font-mono text-xs text-blue-600 hover:underline"
                        >
                          {item.inspection_number}
                        </Link>
                      </TableCell>

                      <TableCell>
                        {item.rule_status === 'POTENTIAL_VIOLATION' ? (
                          <Badge variant="violation" className="text-[11px]">
                            POTENTIAL VIOLATION
                          </Badge>
                        ) : item.rule_status === 'WARNING' ? (
                          <Badge variant="warning" className="text-[11px]">
                            WARNING
                          </Badge>
                        ) : item.rule_status === 'MANUAL_REVIEW' ? (
                          <Badge variant="review" className="text-[11px]">
                            MANUAL REVIEW
                          </Badge>
                        ) : (
                          <Badge variant="pass" className="text-[11px]">
                            PASS
                          </Badge>
                        )}
                        <p className="mt-1 text-[11px] capitalize text-slate-500">Severity: {item.severity}</p>
                      </TableCell>

                      <TableCell>
                        {item.inspector_decision === 'confirm' ? (
                          <span className="inline-flex items-center gap-1 rounded-md bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-700 ring-1 ring-inset ring-rose-200">
                            <CheckCircle className="h-3 w-3" /> Confirmed
                          </span>
                        ) : item.inspector_decision === 'reject' ? (
                          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200">
                            <ShieldAlert className="h-3 w-3" /> Overruled
                          </span>
                        ) : item.inspector_decision === 'manual_review' ? (
                          <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700 ring-1 ring-inset ring-amber-200">
                            Escalated
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                            Unreviewed
                          </span>
                        )}
                      </TableCell>

                      <TableCell className="text-right">
                        <Button asChild size="sm" variant="outline" className="h-8">
                          <Link to={`/inspections/${item.inspection_id}`}>
                            View Evidence
                            <ExternalLink className="ml-1 h-3 w-3" />
                          </Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            {/* Pagination footer */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 sm:px-6">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  Previous
                </Button>
                <span className="text-xs text-slate-500">
                  Page {page + 1} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                >
                  Next
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right Column: Escalation Summary */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Statutory escalation summary</CardTitle>
              <CardDescription>Engine findings breakdown by legal severity.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-rose-800">
                    <AlertTriangle className="h-5 w-5 text-rose-600" />
                    <span className="font-semibold">Critical Violations</span>
                  </div>
                  <span className="text-xl font-bold text-rose-700">{summary?.critical_violations ?? 0}</span>
                </div>
                <p className="mt-2 text-xs text-rose-600">Mandatory statutory omissions under Legal Metrology Rules.</p>
              </div>

              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-amber-800">
                    <AlertCircle className="h-5 w-5 text-amber-600" />
                    <span className="font-semibold">Major Violations</span>
                  </div>
                  <span className="text-xl font-bold text-amber-700">{summary?.major_violations ?? 0}</span>
                </div>
                <p className="mt-2 text-xs text-amber-600">Substantive declaration non-conformances detected.</p>
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-700">Warnings & Manual Reviews</span>
                  <span className="text-xl font-bold text-slate-700">
                    {(summary?.statutory_warnings ?? 0) + (summary?.manual_review_required ?? 0)}
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-500">Advisory formatting issues and non-automated verifications.</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Field adjudication status</CardTitle>
              <CardDescription>Inspector decision progress on open items.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                <span className="text-slate-600">Unreviewed Queue:</span>
                <span className="font-bold text-slate-900">{summary?.unreviewed_count ?? 0}</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50/50 p-3 text-sm">
                <span className="text-emerald-800">Confirmed by Inspector:</span>
                <span className="font-bold text-emerald-700">{summary?.confirmed_count ?? 0}</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                <span className="text-slate-600">Overruled / Dismissed:</span>
                <span className="font-bold text-slate-700">{summary?.rejected_count ?? 0}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
