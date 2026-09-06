import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  Bot,
  CheckCircle,
  FileText,
  Info,
  Scale,
  ShieldAlert,
  X,
} from 'lucide-react'
import { Button } from './ui/button'
import { getStoredToken } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

interface FindingOption {
  id: string
  rule_check_id: string
  title: string
}

interface PramanAssistantDrawerProps {
  isOpen: boolean
  onClose: () => void
  inspectionId: string
  findings: FindingOption[]
  initialFindingId?: string | null
  initialTab?: 'summary' | 'explain' | 'trace' | 'manual'
}

interface FindingExplanation {
  finding_id: string
  rule_check_id: string
  title: string
  rule_status: string
  inspector_decision: string | null
  inspector_decision_framing: string
  detected_value: any
  expected_condition: string | null
  evidence_snippet: string | null
  evidence_panel: string | null
  ocr_confidence: number | null
  statutory_reference: string | null
  statutory_mapping_status: string
  statutory_mapping_explanation: string
  requires_human_review: boolean
  human_review_reason: string | null
  applicable_legal_version: string | null
  disclaimer: string
}

interface InspectionSummary {
  inspection_id: string
  inspection_number: string
  product_name: string | null
  applicable_legal_version: string | null
  panel_count: number
  image_quality_assessments: Array<{
    image_id: string
    panel: string
    assessment: string
    sharpness: number | null
    glare_score: number | null
    dimensions: string | null
    resolution_adequate: boolean | null
  }>
  declaration_extraction_summary: {
    total_extracted: number
    extracted_fields: string[]
    has_multipanel_provenance: boolean
  }
  engine_evaluation_summary: Record<string, number>
  inspector_review_summary: Record<string, number>
  unresolved_items: string[]
  statutory_notice_state: {
    id: string
    notice_number: string
    status: string
    is_immutable: boolean
    charges_count: number
    officer_name: string | null
  } | null
  disclaimer: string
}

interface EvidenceTrace {
  finding_id: string
  rule_check_id: string
  source_image_id: string | null
  source_panel: string | null
  ocr_snippet: string | null
  bounding_box: any
  ocr_confidence: number | null
  detected_value: any
  declaration_field: string | null
  declaration_raw_text: string | null
  applicable_legal_version: string | null
  rule_description: string | null
  disclaimer: string
}

interface ManualReviewItem {
  item_type: string
  identifier: string
  title: string
  reason: string
  available_evidence: string[]
  verification_checklist: string[]
  why_assistant_cannot_resolve: string
}

interface ManualReviewGuide {
  inspection_id: string
  manual_review_items: ManualReviewItem[]
  conflict_items: ManualReviewItem[]
  unresolved_discrepancies_count: number
  guidance_notes: string[]
  disclaimer: string
}

export function PramanAssistantDrawer({
  isOpen,
  onClose,
  inspectionId,
  findings,
  initialFindingId,
  initialTab = 'summary',
}: PramanAssistantDrawerProps) {
  const [activeTab, setActiveTab] = useState<'summary' | 'explain' | 'trace' | 'manual'>(initialTab)
  const [selectedFindingId, setSelectedFindingId] = useState<string>(initialFindingId || (findings[0]?.id ?? ''))

  const [summaryData, setSummaryData] = useState<InspectionSummary | null>(null)
  const [explainData, setExplainData] = useState<FindingExplanation | null>(null)
  const [traceData, setTraceData] = useState<EvidenceTrace | null>(null)
  const [manualData, setManualData] = useState<ManualReviewGuide | null>(null)

  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (initialTab) setActiveTab(initialTab)
  }, [initialTab])

  useEffect(() => {
    if (initialFindingId) {
      setSelectedFindingId(initialFindingId)
    } else if (findings.length > 0 && !selectedFindingId) {
      setSelectedFindingId(findings[0].id)
    }
  }, [initialFindingId, findings, selectedFindingId])

  // Fetch tab data
  useEffect(() => {
    if (!isOpen || !inspectionId) return

    let isMounted = true
    setLoading(true)
    setError(null)

    const fetchData = async () => {
      try {
        const token = getStoredToken()
        const authHeaders = token ? { Authorization: `Bearer ${token}` } : {}

        if (activeTab === 'summary') {
          const res = await fetch(`${API_BASE}/api/v1/inspections/${inspectionId}/assistant/summarize`, {
            headers: authHeaders,
          })
          if (!res.ok) throw new Error(`Failed to fetch summary: ${res.statusText}`)
          const data = await res.json()
          if (isMounted) setSummaryData(data)
        } else if (activeTab === 'explain') {
          if (!selectedFindingId) return
          const res = await fetch(
            `${API_BASE}/api/v1/inspections/${inspectionId}/assistant/explain-finding?finding_id=${selectedFindingId}`,
            { headers: authHeaders }
          )
          if (!res.ok) throw new Error(`Failed to explain finding: ${res.statusText}`)
          const data = await res.json()
          if (isMounted) setExplainData(data)
        } else if (activeTab === 'trace') {
          if (!selectedFindingId) return
          const res = await fetch(
            `${API_BASE}/api/v1/inspections/${inspectionId}/assistant/evidence-trace?finding_id=${selectedFindingId}`,
            { headers: authHeaders }
          )
          if (!res.ok) throw new Error(`Failed to trace evidence: ${res.statusText}`)
          const data = await res.json()
          if (isMounted) setTraceData(data)
        } else if (activeTab === 'manual') {
          const res = await fetch(`${API_BASE}/api/v1/inspections/${inspectionId}/assistant/manual-review-guide`, {
            headers: authHeaders,
          })
          if (!res.ok) throw new Error(`Failed to load manual review guide: ${res.statusText}`)
          const data = await res.json()
          if (isMounted) setManualData(data)
        }
      } catch (err: any) {
        if (isMounted) setError(err.message || 'An error occurred while communicating with the assistant.')
      } finally {
        if (isMounted) setLoading(false)
      }
    }

    fetchData()

    return () => {
      isMounted = false
    }
  }, [isOpen, inspectionId, activeTab, selectedFindingId])

  if (!isOpen) return null

  return (
    <div
      id="praman-assistant-drawer"
      data-testid="praman-assistant-drawer"
      className="fixed inset-0 z-50 flex justify-end bg-slate-900/60 backdrop-blur-sm transition-opacity"
      aria-modal="true"
      role="dialog"
    >
      <div className="flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800">
        {/* Drawer Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-md shadow-indigo-600/20">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-slate-900 dark:text-white">PRAMAN Assistant</h2>
                <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-[10px] font-semibold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
                  Evidence-Grounded
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Evidence-grounded informational assistance for packaging inspection
              </p>
            </div>
          </div>
          <Button
            id="close-assistant-drawer-btn"
            data-testid="close-assistant-drawer-btn"
            variant="outline"
            size="sm"
            onClick={onClose}
            className="h-8 w-8 p-0 text-slate-500 hover:text-slate-900 dark:hover:text-white"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Global Mandatory Statutory Disclaimer */}
        <div className="border-b border-amber-200 bg-amber-50/90 px-6 py-2.5 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300 flex items-start gap-2">
          <Info className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
          <div>
            <span className="font-semibold">Informational Assistance Only:</span> Explains existing stored records and
            evidence. Does not determine legal liability, issue statutory notices, or replace authorized officer discretion.
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-200 bg-slate-50/80 px-6 dark:border-slate-800 dark:bg-slate-900/50">
          <button
            id="tab-summary"
            data-testid="tab-summary"
            onClick={() => setActiveTab('summary')}
            className={`border-b-2 py-3 px-3 text-xs font-medium transition-colors ${
              activeTab === 'summary'
                ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                : 'border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            Inspection Summary
          </button>
          <button
            id="tab-explain"
            data-testid="tab-explain"
            onClick={() => setActiveTab('explain')}
            className={`border-b-2 py-3 px-3 text-xs font-medium transition-colors ${
              activeTab === 'explain'
                ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                : 'border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            Explain Finding
          </button>
          <button
            id="tab-trace"
            data-testid="tab-trace"
            onClick={() => setActiveTab('trace')}
            className={`border-b-2 py-3 px-3 text-xs font-medium transition-colors ${
              activeTab === 'trace'
                ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                : 'border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            Evidence Trace
          </button>
          <button
            id="tab-manual"
            data-testid="tab-manual"
            onClick={() => setActiveTab('manual')}
            className={`border-b-2 py-3 px-3 text-xs font-medium transition-colors ${
              activeTab === 'manual'
                ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                : 'border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            Manual Review Guide
          </button>
        </div>

        {/* Drawer Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading && (
            <div className="flex h-48 flex-col items-center justify-center gap-3 text-slate-500">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
              <span className="text-xs">Loading assistant explanation...</span>
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-300">
              <div className="flex items-center gap-2 font-semibold">
                <AlertTriangle className="h-4 w-4" />
                <span>Error</span>
              </div>
              <p className="mt-1">{error}</p>
            </div>
          )}

          {!loading && !error && (
            <>
              {/* Finding Selector for Explain and Trace tabs */}
              {(activeTab === 'explain' || activeTab === 'trace') && findings.length > 0 && (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800/40">
                  <label htmlFor="assistant-finding-select" className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Select Finding to Inspect:
                  </label>
                  <select
                    id="assistant-finding-select"
                    data-testid="assistant-finding-select"
                    value={selectedFindingId}
                    onChange={(e) => setSelectedFindingId(e.target.value)}
                    className="w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                  >
                    {findings.map((f) => (
                      <option key={f.id} value={f.id}>
                        [{f.rule_check_id}] {f.title}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* TAB 1: SUMMARY */}
              {activeTab === 'summary' && summaryData && (
                <div className="space-y-5">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                      <div className="text-[11px] font-medium text-slate-500">Panels Analyzed</div>
                      <div className="mt-1 text-lg font-bold text-slate-900 dark:text-white">
                        {summaryData.panel_count}
                      </div>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                      <div className="text-[11px] font-medium text-slate-500">Declarations Extracted</div>
                      <div className="mt-1 text-lg font-bold text-slate-900 dark:text-white">
                        {summaryData.declaration_extraction_summary?.total_extracted ?? 0}
                      </div>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                      <div className="text-[11px] font-medium text-slate-500">Engine Violations</div>
                      <div className="mt-1 text-lg font-bold text-rose-600">
                        {summaryData.engine_evaluation_summary?.FAIL ?? 0}
                      </div>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                      <div className="text-[11px] font-medium text-slate-500">Inspector Confirmed</div>
                      <div className="mt-1 text-lg font-bold text-indigo-600">
                        {summaryData.inspector_review_summary?.CONFIRMED ?? 0}
                      </div>
                    </div>
                  </div>

                  {/* Panel Image Quality Diagnostics */}
                  <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3">
                      Panel Image Quality Diagnostics (Raw Metrics)
                    </h3>
                    <div className="divide-y divide-slate-100 dark:divide-slate-800">
                      {summaryData.image_quality_assessments.map((qa) => (
                        <div key={qa.image_id} className="py-2.5 flex items-center justify-between text-xs">
                          <div>
                            <span className="font-semibold text-slate-800 dark:text-slate-200 uppercase mr-2">
                              {qa.panel} Panel
                            </span>
                            <span
                              className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                                qa.assessment === 'ACCEPTABLE'
                                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                                  : 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
                              }`}
                            >
                              {qa.assessment}
                            </span>
                          </div>
                          <div className="text-slate-500 space-x-3 text-[11px]">
                            <span>Sharpness: {qa.sharpness != null ? qa.sharpness : 'N/A'}</span>
                            <span>Glare: {qa.glare_score != null ? `${qa.glare_score}%` : 'N/A'}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Unresolved / Manual Verification Items */}
                  {summaryData.unresolved_items.length > 0 && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-4 dark:border-amber-900/40 dark:bg-amber-950/20">
                      <div className="flex items-center gap-2 font-semibold text-xs text-amber-900 dark:text-amber-300 mb-2">
                        <AlertTriangle className="h-4 w-4 text-amber-600" />
                        <span>Unresolved / Action Required Items ({summaryData.unresolved_items.length})</span>
                      </div>
                      <ul className="list-disc pl-5 text-xs text-amber-800 dark:text-amber-300 space-y-1">
                        {summaryData.unresolved_items.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Statutory Notice State */}
                  {summaryData.statutory_notice_state && (
                    <div className="rounded-lg border border-indigo-200 bg-indigo-50/60 p-4 dark:border-indigo-900/40 dark:bg-indigo-950/20">
                      <div className="flex items-center gap-2 font-semibold text-xs text-indigo-900 dark:text-indigo-300 mb-1">
                        <FileText className="h-4 w-4 text-indigo-600" />
                        <span>Statutory Notice Drafted: {summaryData.statutory_notice_state.notice_number}</span>
                      </div>
                      <p className="text-xs text-indigo-800 dark:text-indigo-300">
                        Status: <strong className="font-semibold">{summaryData.statutory_notice_state.status}</strong> | Charges recorded: {summaryData.statutory_notice_state.charges_count}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: EXPLAIN FINDING */}
              {activeTab === 'explain' && explainData && (
                <div className="space-y-4">
                  {/* Finding Title Header */}
                  <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                        {explainData.rule_check_id}
                      </span>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                          explainData.rule_status === 'FAIL'
                            ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300'
                            : explainData.rule_status === 'PASS'
                            ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                            : 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300'
                        }`}
                      >
                        Engine: {explainData.rule_status}
                      </span>
                    </div>
                    <h3 className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">{explainData.title}</h3>
                  </div>

                  {/* Inspector Decision Framing */}
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-800/50 dark:text-slate-300">
                    <span className="font-semibold text-slate-900 dark:text-white">Review Status: </span>
                    {explainData.inspector_decision_framing}
                  </div>

                  {/* Expected Condition vs Detected Value */}
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
                      <div className="text-[11px] font-medium text-slate-500">Expected Statutory Condition</div>
                      <div className="mt-1 text-xs text-slate-800 dark:text-slate-200 font-medium">
                        {explainData.expected_condition || 'Standard Packaged Commodities Rule declaration required.'}
                      </div>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
                      <div className="text-[11px] font-medium text-slate-500">Detected Value on Packaging</div>
                      <div className="mt-1 font-mono text-xs text-slate-800 dark:text-slate-200">
                        {typeof explainData.detected_value === 'object'
                          ? JSON.stringify(explainData.detected_value)
                          : explainData.detected_value || 'None detected'}
                      </div>
                    </div>
                  </div>

                  {/* Optical Evidence Snippet */}
                  <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
                    <div className="text-[11px] font-medium text-slate-500 mb-1">OCR Optical Evidence Snippet</div>
                    <div className="rounded bg-slate-50 p-2 font-mono text-xs text-slate-800 dark:bg-slate-800/80 dark:text-slate-200">
                      "{explainData.evidence_snippet || 'No text snippet associated'}"
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                      <span>Panel: <strong>{explainData.evidence_panel || 'Unknown'}</strong></span>
                      {explainData.ocr_confidence != null && (
                        <span>OCR Confidence: {(explainData.ocr_confidence * 100).toFixed(1)}%</span>
                      )}
                    </div>
                  </div>

                  {/* Statutory Mapping Card */}
                  <div
                    className={`rounded-lg border p-4 text-xs ${
                      explainData.statutory_mapping_status === 'RECORDED_IN_NOTICE'
                        ? 'border-indigo-200 bg-indigo-50/50 dark:border-indigo-900/50 dark:bg-indigo-950/30'
                        : 'border-amber-200 bg-amber-50/50 dark:border-amber-900/50 dark:bg-amber-950/30'
                    }`}
                  >
                    <div className="flex items-center gap-2 font-semibold">
                      {explainData.statutory_mapping_status === 'RECORDED_IN_NOTICE' ? (
                        <CheckCircle className="h-4 w-4 text-indigo-600" />
                      ) : (
                        <ShieldAlert className="h-4 w-4 text-amber-600" />
                      )}
                      <span>
                        Statutory Mapping Status: {explainData.statutory_mapping_status}
                      </span>
                    </div>
                    {explainData.statutory_reference && (
                      <div className="mt-1 font-mono font-semibold text-slate-900 dark:text-white">
                        {explainData.statutory_reference}
                      </div>
                    )}
                    <p className="mt-1 text-slate-700 dark:text-slate-300">
                      {explainData.statutory_mapping_explanation}
                    </p>
                  </div>

                  {/* Human Review Requirement */}
                  {explainData.requires_human_review && (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-800 dark:bg-slate-800/40">
                      <span className="font-semibold text-slate-900 dark:text-white">Human Review Required: </span>
                      <span className="text-slate-600 dark:text-slate-400">{explainData.human_review_reason}</span>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: EVIDENCE TRACE */}
              {activeTab === 'trace' && traceData && (
                <div className="space-y-4">
                  <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                      Optical Provenance & Traceability
                    </h3>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                        <span className="text-slate-500">Rule Check ID</span>
                        <span className="font-mono font-semibold text-indigo-600">{traceData.rule_check_id}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                        <span className="text-slate-500">Source Panel</span>
                        <span className="font-semibold text-slate-800 dark:text-slate-200">{traceData.source_panel || 'N/A'}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                        <span className="text-slate-500">Image ID</span>
                        <span className="font-mono text-slate-600 dark:text-slate-400">{traceData.source_image_id || 'N/A'}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                        <span className="text-slate-500">OCR Confidence</span>
                        <span className="font-semibold text-slate-800 dark:text-slate-200">
                          {traceData.ocr_confidence != null ? `${(traceData.ocr_confidence * 100).toFixed(1)}%` : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                        <span className="text-slate-500">Applicable Version</span>
                        <span className="font-semibold text-slate-800 dark:text-slate-200">{traceData.applicable_legal_version}</span>
                      </div>
                    </div>
                  </div>

                  {/* OCR Snippet */}
                  <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                    <div className="text-[11px] font-semibold text-slate-500 mb-1">OCR Raw Text Snippet</div>
                    <pre className="rounded bg-slate-50 p-3 font-mono text-xs text-slate-800 dark:bg-slate-800 dark:text-slate-200 overflow-x-auto">
                      {traceData.ocr_snippet || 'None recorded'}
                    </pre>
                  </div>

                  {/* Bounding Box Coordinates */}
                  {traceData.bounding_box && (
                    <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                      <div className="text-[11px] font-semibold text-slate-500 mb-1">Bounding Box Coordinates (x, y)</div>
                      <pre className="rounded bg-slate-50 p-3 font-mono text-xs text-slate-800 dark:bg-slate-800 dark:text-slate-200 overflow-x-auto">
                        {JSON.stringify(traceData.bounding_box, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 4: MANUAL REVIEW GUIDE */}
              {activeTab === 'manual' && manualData && (
                <div className="space-y-4">
                  {/* Guidance Notes */}
                  <div className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-4 dark:border-indigo-900/50 dark:bg-indigo-950/30 text-xs space-y-1 text-indigo-950 dark:text-indigo-200">
                    <div className="flex items-center gap-2 font-semibold">
                      <Scale className="h-4 w-4 text-indigo-600" />
                      <span>Procedural Verification Protocol</span>
                    </div>
                    <ul className="list-disc pl-5 space-y-1 mt-1">
                      {manualData.guidance_notes.map((n, idx) => (
                        <li key={idx}>{n}</li>
                      ))}
                    </ul>
                  </div>

                  {/* Items Requiring Physical / Manual Verification */}
                  {manualData.manual_review_items.map((item, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-semibold text-amber-600 dark:text-amber-400">
                          {item.identifier}
                        </span>
                        <span className="rounded bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700 dark:bg-amber-950/50 dark:text-amber-300">
                          Physical Review Required
                        </span>
                      </div>
                      <h4 className="text-xs font-bold text-slate-900 dark:text-white">{item.title}</h4>
                      <p className="text-xs text-slate-600 dark:text-slate-400">{item.reason}</p>

                      {/* Verification Steps Checklist */}
                      <div className="rounded-md bg-slate-50 p-3 dark:bg-slate-800/60">
                        <div className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                          Verification Checklist for Inspecting Officer:
                        </div>
                        <ul className="list-disc pl-5 text-xs text-slate-600 dark:text-slate-400 space-y-1">
                          {item.verification_checklist.map((step, sIdx) => (
                            <li key={sIdx}>{step}</li>
                          ))}
                        </ul>
                      </div>

                      {/* Why Assistant Cannot Resolve */}
                      <div className="text-xs text-slate-500 italic">
                        <span className="font-medium">Why Assistant Cannot Resolve Automatically: </span>
                        {item.why_assistant_cannot_resolve}
                      </div>
                    </div>
                  ))}

                  {/* Image Degradation Items */}
                  {manualData.conflict_items.map((item, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-rose-200 bg-rose-50/40 p-4 dark:border-rose-900/40 dark:bg-rose-950/20 space-y-2"
                    >
                      <div className="flex items-center gap-2 text-xs font-semibold text-rose-900 dark:text-rose-300">
                        <AlertTriangle className="h-4 w-4 text-rose-600" />
                        <span>{item.title}</span>
                      </div>
                      <p className="text-xs text-rose-800 dark:text-rose-300">{item.reason}</p>
                      <div className="text-xs text-slate-600 dark:text-slate-400">
                        <strong>Recommended action:</strong> {item.verification_checklist.join(' ')}
                      </div>
                    </div>
                  ))}

                  {manualData.manual_review_items.length === 0 && manualData.conflict_items.length === 0 && (
                    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300 flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-emerald-600" />
                      <span>No outstanding manual review or physical verification conflicts detected.</span>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
