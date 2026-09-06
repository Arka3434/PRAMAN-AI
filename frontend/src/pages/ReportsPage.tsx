import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, ExternalLink, FileCheck, Search } from 'lucide-react'

import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { PageHeader } from '../components/ui/page-header'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table'
import type { InspectionHistoryRecord } from './InspectionsPage'
import { getStoredToken } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export function ReportsPage() {
  const navigate = useNavigate()
  const [reports, setReports] = useState<InspectionHistoryRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')

  const fetchReports = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      params.append('status', 'completed')
      if (searchTerm.trim()) {
        params.append('search', searchTerm.trim())
      }

      const token = getStoredToken()
      const res = await fetch(`${API_BASE}/api/v1/inspections?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) {
        throw new Error(`Failed to load report history: HTTP ${res.status}`)
      }
      const data = (await res.json()) as InspectionHistoryRecord[]
      setReports(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error fetching reports')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const handler = setTimeout(() => {
      void fetchReports()
    }, 200)
    return () => clearTimeout(handler)
  }, [searchTerm])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        description="Inspection records and evidence-backed decision summaries finalized for regulatory documentation and audit archival."
        action={
          <Button onClick={() => navigate('/inspections')} variant="outline">
            View All Inspections
          </Button>
        }
      />

      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b border-slate-100 pb-4">
          <div>
            <CardTitle>Report history</CardTitle>
            <CardDescription>
              Evidence-backed statutory PDF reports generated for finalized product inspections under Legal Metrology Rules, 2011.
            </CardDescription>
          </div>
          <div className="relative w-64">
            <Input
              placeholder="Search reports..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 text-xs"
              data-testid="reports-search-input"
            />
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {error && (
            <div className="p-4 text-sm text-rose-600 bg-rose-50 border-b border-rose-100">
              {error}
            </div>
          )}

          {loading ? (
            <div className="p-8 text-center text-sm text-slate-500">Loading finalized reports...</div>
          ) : reports.length === 0 ? (
            <div className="p-12 text-center" data-testid="empty-reports-message">
              <FileCheck className="mx-auto h-8 w-8 text-slate-300" />
              <div className="mt-2 text-sm font-semibold text-slate-700">No finalized reports available</div>
              <div className="mt-1 text-xs text-slate-500">
                {searchTerm
                  ? 'No completed reports match your search criteria.'
                  : 'Complete and finalize an inspection to generate its statutory audit report.'}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/inspections')}
                className="mt-4 text-xs"
              >
                Go to Inspections
              </Button>
            </div>
          ) : (
            <Table data-testid="reports-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Inspection Ref</TableHead>
                  <TableHead>Product</TableHead>
                  <TableHead>Finalized Date</TableHead>
                  <TableHead>Compliance Evaluation</TableHead>
                  <TableHead>Findings</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.map((report) => (
                  <TableRow key={report.id} data-testid={`report-row-${report.id}`}>
                    <TableCell>
                      <div className="font-mono font-semibold text-slate-900">{report.inspection_number}</div>
                      <div className="text-[11px] text-slate-500">
                        praman_inspection_report_{report.inspection_number}.pdf
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="font-medium text-slate-900">{report.product_name ?? 'Not specified'}</span>
                    </TableCell>
                    <TableCell className="text-xs text-slate-600">
                      {new Date(report.updated_at || report.created_at).toLocaleDateString(undefined, {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                      })}
                    </TableCell>
                    <TableCell>
                      {report.overall_result === 'COMPLIANT' ? (
                        <Badge variant="pass">COMPLIANT</Badge>
                      ) : (
                        <Badge variant="violation">VIOLATIONS DETECTED</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 font-mono">
                        {report.finding_count} {report.finding_count === 1 ? 'finding' : 'findings'}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate(`/inspections/${report.id}`)}
                          className="h-8 px-2.5 text-xs"
                          data-testid="view-inspection-link"
                        >
                          <ExternalLink className="mr-1 h-3.5 w-3.5" /> View
                        </Button>
                        <a
                          href={`${API_BASE}/api/v1/inspections/${report.id}/report`}
                          download={`praman_inspection_report_${report.inspection_number}.pdf`}
                          className="inline-flex items-center justify-center rounded-md bg-emerald-700 px-3 py-1 text-xs font-semibold text-white shadow-sm hover:bg-emerald-800 transition-colors h-8"
                          data-testid="download-report-button"
                          title="Download formal evidence-backed statutory PDF report"
                        >
                          <Download className="mr-1 h-3.5 w-3.5" /> Download PDF
                        </a>
                        {report.notice_id && (
                          <a
                            href={`${API_BASE}/api/v1/notices/${report.notice_id}/pdf`}
                            download={`statutory_notice_${report.notice_reference || report.notice_id}.pdf`}
                            className="inline-flex items-center justify-center rounded-md bg-indigo-700 px-3 py-1 text-xs font-semibold text-white shadow-sm hover:bg-indigo-800 transition-colors h-8"
                            data-testid="download-notice-button"
                            title="Download official statutory notice / inspection memo PDF"
                          >
                            <FileCheck className="mr-1 h-3.5 w-3.5" /> Notice PDF
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