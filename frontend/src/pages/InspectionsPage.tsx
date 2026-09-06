import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, ExternalLink, FileText, Plus, Search } from 'lucide-react'

import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { PageHeader } from '../components/ui/page-header'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table'
import { getStoredToken } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type InspectionHistoryRecord = {
  id: string
  inspection_number: string
  status: string
  title: string | null
  notes: string | null
  barcode_or_qr: string | null
  product_id: string | null
  inspector_id: string | null
  created_at: string
  updated_at: string
  product_name: string | null
  inspector_name: string | null
  finding_count: number
  overall_result: string | null
  review_status: string | null
  report_available: boolean
  notice_status?: string | null
  notice_id?: string | null
  notice_reference?: string | null
}


export function InspectionsPage() {
  const navigate = useNavigate()
  const [inspections, setInspections] = useState<InspectionHistoryRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  const fetchInspections = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (statusFilter !== 'all') {
        params.append('status', statusFilter)
      }
      if (searchTerm.trim()) {
        params.append('search', searchTerm.trim())
      }

      const token = getStoredToken()
      const res = await fetch(`${API_BASE}/api/v1/inspections?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) {
        throw new Error(`Failed to load inspections: HTTP ${res.status}`)
      }
      const data = (await res.json()) as InspectionHistoryRecord[]
      setInspections(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error fetching inspections')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const handler = setTimeout(() => {
      void fetchInspections()
    }, 200)
    return () => clearTimeout(handler)
  }, [searchTerm, statusFilter])

  const renderStatusBadge = (status: string) => {
    const s = status.toUpperCase()
    if (s === 'COMPLETED') {
      return <Badge variant="pass">COMPLETED</Badge>
    }
    if (s === 'REVIEW_REQUIRED') {
      return <Badge variant="warning">REVIEW REQUIRED</Badge>
    }
    return <Badge variant="neutral">DRAFT</Badge>
  }

  const renderResultBadge = (result: string | null) => {
    if (!result) return <Badge variant="default">UNKNOWN</Badge>
    switch (result) {
      case 'COMPLIANT':
        return <Badge variant="pass">COMPLIANT</Badge>
      case 'POTENTIAL_VIOLATIONS_DETECTED':
        return <Badge variant="violation">VIOLATIONS</Badge>
      case 'WARNINGS_OR_MANUAL_REVIEW':
        return <Badge variant="warning">WARNINGS / REVIEW</Badge>
      case 'PENDING_ANALYSIS':
        return <Badge variant="neutral">PENDING</Badge>
      default:
        return <Badge variant="default">{result}</Badge>
    }
  }

  const renderReviewBadge = (review: string | null) => {
    if (!review) return null
    switch (review) {
      case 'COMPLETE':
        return <span className="inline-flex items-center text-xs font-semibold text-emerald-700">✓ Complete</span>
      case 'IN_PROGRESS':
        return <span className="inline-flex items-center text-xs font-semibold text-indigo-700">In Progress</span>
      case 'PENDING':
        return <span className="inline-flex items-center text-xs font-semibold text-amber-700">Pending</span>
      default:
        return <span className="inline-flex items-center text-xs text-slate-500">{review}</span>
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inspections"
        description="Review active, draft, and completed inspection records across packaged commodities."
        action={
          <Button onClick={() => navigate('/inspections/new')} data-testid="new-inspection-button">
            <Plus className="mr-1.5 h-4 w-4" /> New Inspection
          </Button>
        }
      />

      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b border-slate-100 pb-4">
          <div>
            <CardTitle>Inspection register</CardTitle>
            <CardDescription>Search and filter inspection history, audit results, and formal reports.</CardDescription>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Status Filter Tabs */}
            <div className="flex rounded-lg bg-slate-100 p-1 text-xs">
              {(['all', 'completed', 'review_required', 'draft'] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setStatusFilter(tab)}
                  className={`rounded-md px-3 py-1.5 font-medium transition-all ${
                    statusFilter === tab
                      ? 'bg-white text-slate-900 shadow-sm font-semibold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                  data-testid={`filter-tab-${tab}`}
                >
                  {tab === 'all'
                    ? 'All'
                    : tab === 'completed'
                    ? 'Completed'
                    : tab === 'review_required'
                    ? 'Review Required'
                    : 'Draft'}
                </button>
              ))}
            </div>

            {/* Search Input */}
            <div className="relative w-64">
              <Input
                placeholder="Search by ID or product..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 text-xs"
                data-testid="inspection-search-input"
              />
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {error && (
            <div className="p-4 text-sm text-rose-600 bg-rose-50 border-b border-rose-100">
              {error}
            </div>
          )}

          {loading ? (
            <div className="p-8 text-center text-sm text-slate-500">Loading inspection history...</div>
          ) : inspections.length === 0 ? (
            <div className="p-12 text-center" data-testid="empty-history-message">
              <FileText className="mx-auto h-8 w-8 text-slate-300" />
              <div className="mt-2 text-sm font-semibold text-slate-700">No inspections found</div>
              <div className="mt-1 text-xs text-slate-500">
                {searchTerm || statusFilter !== 'all'
                  ? 'Try adjusting your search criteria or filter tabs.'
                  : 'Start by creating your first package inspection.'}
              </div>
            </div>
          ) : (
            <Table data-testid="inspections-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Inspection Ref</TableHead>
                  <TableHead>Product / Commodity</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Workflow Status</TableHead>
                  <TableHead>Compliance Evaluation</TableHead>
                  <TableHead>Findings</TableHead>
                  <TableHead>Inspector Review</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {inspections.map((inspection) => (
                  <TableRow key={inspection.id} data-testid={`inspection-row-${inspection.id}`}>
                    <TableCell>
                      <button
                        type="button"
                        onClick={() => navigate(`/inspections/${inspection.id}`)}
                        className="text-left font-mono font-semibold text-indigo-700 hover:text-indigo-900 hover:underline"
                        data-testid="inspection-link"
                      >
                        {inspection.inspection_number}
                      </button>
                      {inspection.title && (
                        <div className="text-[11px] text-slate-500 truncate max-w-[200px]">{inspection.title}</div>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="font-medium text-slate-900">{inspection.product_name ?? 'Not specified'}</span>
                    </TableCell>
                    <TableCell className="text-xs text-slate-600">
                      {new Date(inspection.created_at).toLocaleDateString(undefined, {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                      })}
                    </TableCell>
                    <TableCell>{renderStatusBadge(inspection.status)}</TableCell>
                    <TableCell>{renderResultBadge(inspection.overall_result)}</TableCell>
                    <TableCell>
                      <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 font-mono">
                        {inspection.finding_count} {inspection.finding_count === 1 ? 'finding' : 'findings'}
                      </span>
                    </TableCell>
                    <TableCell>{renderReviewBadge(inspection.review_status)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate(`/inspections/${inspection.id}`)}
                          className="h-8 px-2.5 text-xs"
                          data-testid="open-inspection-button"
                        >
                          <ExternalLink className="mr-1 h-3.5 w-3.5" /> Open
                        </Button>

                        {inspection.report_available && (
                          <a
                            href={`${API_BASE}/api/v1/inspections/${inspection.id}/report`}
                            download={`praman_inspection_report_${inspection.inspection_number}.pdf`}
                            className="inline-flex items-center justify-center rounded-md border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 shadow-sm hover:bg-emerald-100 transition-colors h-8"
                            data-testid="download-report-button"
                            title="Download evidence-backed statutory PDF report"
                          >
                            <Download className="mr-1 h-3.5 w-3.5" /> Report
                          </a>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
