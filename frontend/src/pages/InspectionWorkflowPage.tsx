import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  AlertTriangle,
  Bot,
  ChevronDown,
  ChevronUp,
  Download,
  FileText,
  Lock,
} from 'lucide-react'

import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { PageHeader } from '../components/ui/page-header'
import { PramanAssistantDrawer } from '../components/PramanAssistantDrawer'
import { useAuth } from '../context/AuthContext'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

type InspectionRecord = {
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
}

type InspectorCorrection = {
  field_name: string
  original_value: unknown
  corrected_value: unknown
  timestamp: string
  notes?: string | null
  status: string
}

type ExtractionMetadata = {
  raw_ocr_declarations?: Record<string, unknown>
  inspector_corrections?: InspectorCorrection[]
  [key: string]: unknown
}

type AnalysisRecord = {
  id: string
  inspection_id: string
  status: string
  confidence: number
  structured_declarations: Record<string, unknown>
  extraction_metadata?: ExtractionMetadata | null
  ocr_text?: string | null
  created_at: string
}

type FindingRecord = {
  id: string
  inspection_id: string
  severity: string
  status: string
  title: string
  description: string
  detected_value: string | null
  rule_check_id: string
  evidence_reference: string | null
  created_at: string
  what?: string | null
  why?: string | null
  legal_citation?: string | null
  expected_condition?: string | null
  source_image?: string | null
  evidence_snippet?: string | null
  evidence_location?: unknown[] | null
  ocr_confidence?: number | null
  image_id?: string | null
  storage_path?: string | null
  panel_type?: string | null
  has_conflict?: boolean | null
  rule_status?: string | null
  inspector_decision?: string | null
  reviewer_name?: string | null
  reviewed_at?: string | null
  inspector_notes?: string | null
}

type ImageQualityAssessment = {
  sharpness_score: number
  glare_percentage: number
  width: number
  height: number
  resolution_adequate: boolean
  quality_verdict: 'ACCEPTABLE' | 'WARNING_DEGRADED' | 'UNREADABLE'
  issues: string[]
  recommendations: string[]
}

type ImageRecord = {
  id: string
  inspection_id: string
  image_type: string
  file_name: string
  storage_path: string | null
  mime_type: string | null
  width: number | null
  height: number | null
  created_at: string
  quality_assessment?: ImageQualityAssessment | null
  rotation_metadata?: {
    rotation_angle?: number
    original_preserved?: boolean
    is_derivative?: boolean
    updated_at?: string
    [key: string]: unknown
  } | null
}

type ComplianceSummary = {
  inspection_id: string
  inspection_status: string
  inspection_date?: string | null
  catalog_version?: string | null
  catalog_hash?: string | null
  engine_summary: {
    overall_result: string
    total_checks: number
    passed: number
    potential_violations: number
    warnings: number
    manual_review: number
    not_applicable: number
    severity_distribution: {
      critical: number
      major: number
      warning: number
      pass_count: number
    }
  }
  inspector_summary: {
    total_findings: number
    reviewed_count: number
    pending_count: number
    confirmed_count: number
    rejected_count: number
    manual_review_count: number
    review_status: string
  }
  final_result: {
    can_finalize: boolean
    inspection_status: string
    blocking_reasons: string[]
  }
}

type StatutoryCharge = {
  rule_check_id: string
  legal_basis: string
  factual_basis: string
  applicable_section: string
  statutory_citation: string
  evidence_summary: string
  requires_manual_review: boolean
  manual_review_reason?: string | null
}

type StatutoryNotice = {
  id: string
  notice_number: string
  notice_reference: string
  inspection_id: string
  recipient_role: string
  recipient_name: string
  recipient_address?: string | null
  recipient_email?: string | null
  status: 'DRAFT' | 'REVIEWED' | 'ISSUED_BY_OFFICER'
  response_period_days: number
  compounding_available: boolean
  statutory_charges: StatutoryCharge[]
  officer_review_notes?: string | null
  issuing_officer_name?: string | null
  issuing_officer_designation?: string | null
  issuing_officer_jurisdiction?: string | null
  is_immutable: boolean
  created_at: string
  updated_at: string
  issued_at?: string | null
}

const steps = ['Upload', 'Analysis', 'Findings', 'Review', 'Complete']

function getStepIndex(status: string) {
  switch (status) {
    case 'DRAFT':
      return 0
    case 'ANALYZING':
      return 1
    case 'REVIEW_REQUIRED':
      return 3
    case 'COMPLETED':
      return 4
    default:
      return 1
  }
}

function getStatusClass(status: string) {
  switch (status) {
    case 'DRAFT':
      return 'bg-slate-100 text-slate-700'
    case 'ANALYZING':
      return 'bg-violet-100 text-violet-700'
    case 'REVIEW_REQUIRED':
      return 'bg-amber-100 text-amber-700'
    case 'COMPLETED':
      return 'bg-emerald-100 text-emerald-700'
    default:
      return 'bg-slate-100 text-slate-700'
  }
}

function getLabelForImageType(type: string) {
  switch (type) {
    case 'front':
      return 'Front'
    case 'back':
      return 'Back'
    case 'left_side':
      return 'Left Side'
    case 'right_side':
      return 'Right Side'
    case 'other':
      return 'Other'
    default:
      return 'Front'
  }
}

const DECLARATION_FIELD_LABELS: Record<string, string> = {
  commodity_name: 'Commodity Name',
  manufacturer_name: 'Manufacturer / Packer / Importer',
  manufacturer_address: 'Manufacturer Address',
  net_quantity: 'Net Quantity',
  quantity_unit: 'Quantity Unit',
  retail_sale_price: 'Retail Sale Price (MRP)',
  month_year: 'Month & Year of Manufacture',
  consumer_contact: 'Consumer Care Contact',
  country_of_origin: 'Country of Origin',
}

function formatInspectorDecision(decision: string) {
  switch (decision.toLowerCase()) {
    case 'confirm':
      return 'CONFIRMED'
    case 'reject':
      return 'REJECTED'
    case 'manual_review':
      return 'MANUAL REVIEW'
    default:
      return decision.toUpperCase()
  }
}

function VisualEvidenceViewer({
  finding,
  imageUrl,
}: {
  finding: FindingRecord
  imageUrl: string | null
}) {
  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number } | null>(null)
  const [isExpanded, setIsExpanded] = useState(false)

  const parsedBox = useMemo(() => {
    if (!finding.evidence_location || !Array.isArray(finding.evidence_location) || finding.evidence_location.length === 0) {
      return null
    }
    const loc = finding.evidence_location
    if (loc.length >= 4 && Array.isArray(loc[0])) {
      const points = (loc as number[][]).map(([x, y]) => `${x},${y}`).join(' ')
      return { points }
    }
    if (loc.length === 4 && typeof loc[0] === 'number') {
      const [x1, y1, x2, y2] = loc as number[]
      const points = `${x1},${y1} ${x2},${y1} ${x2},${y2} ${x1},${y2}`
      return { points }
    }
    return null
  }, [finding.evidence_location])

  const strokeColor = useMemo(() => {
    switch (finding.severity?.toLowerCase()) {
      case 'critical':
      case 'major':
        return { stroke: '#ef4444', fill: 'rgba(239, 68, 68, 0.22)' }
      case 'warning':
        return { stroke: '#f59e0b', fill: 'rgba(245, 158, 11, 0.22)' }
      case 'pass':
      default:
        return { stroke: '#10b981', fill: 'rgba(16, 185, 129, 0.22)' }
    }
  }, [finding.severity])

  if (!imageUrl || !parsedBox) {
    return (
      <div className="rounded-lg border border-slate-200/80 bg-slate-100/60 p-2.5 text-xs" data-testid="finding-textual-evidence">
        <span className="font-semibold block text-[11px] uppercase tracking-wider text-slate-500">Evidence & Localization</span>
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-slate-600">
          {finding.panel_type && (
            <div data-testid="evidence-panel-provenance"><span className="font-medium text-slate-700">Panel:</span> <span className="capitalize font-semibold text-slate-800">{finding.panel_type}</span></div>
          )}
          {finding.source_image && (
            <div><span className="font-medium text-slate-700">Source:</span> {finding.source_image}</div>
          )}
          {finding.evidence_snippet && (
            <div data-testid="evidence-snippet"><span className="font-medium text-slate-700">OCR Snippet:</span> &ldquo;{finding.evidence_snippet}&rdquo;</div>
          )}
          {finding.ocr_confidence != null && (
            <div data-testid="evidence-confidence"><span className="font-medium text-slate-700">Confidence:</span> {(finding.ocr_confidence * 100).toFixed(1)}%</div>
          )}
          <div className="text-slate-400 italic">
            Spatial bounding box unavailable (declaration not detected in image text)
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-slate-200/80 bg-slate-100/60 p-2.5 text-xs space-y-2" data-testid="finding-visual-evidence">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-[11px] uppercase tracking-wider text-slate-500">Visual Evidence & Localization</span>
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-[11px] font-medium text-indigo-600 hover:text-indigo-800 hover:underline"
        >
          {isExpanded ? 'Fit preview' : 'Expand full image'}
        </button>
      </div>

      <div className={`relative overflow-hidden rounded-md border border-slate-300 bg-slate-900/5 ${isExpanded ? 'max-h-none' : 'max-h-60'}`}>
        <img
          src={imageUrl}
          alt={finding.source_image || 'Package source evidence'}
          className="block w-full h-auto object-contain select-none"
          onLoad={(e) => {
            setImageDimensions({
              width: e.currentTarget.naturalWidth,
              height: e.currentTarget.naturalHeight,
            })
          }}
        />
        {imageDimensions && (
          <svg
            data-testid="evidence-bbox-overlay"
            viewBox={`0 0 ${imageDimensions.width} ${imageDimensions.height}`}
            className="absolute inset-0 h-full w-full pointer-events-none"
            preserveAspectRatio="none"
          >
            <polygon
              points={parsedBox.points}
              stroke={strokeColor.stroke}
              strokeWidth="3.5"
              fill={strokeColor.fill}
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-slate-600 pt-0.5">
        {finding.panel_type && (
          <div data-testid="evidence-panel-provenance"><span className="font-medium text-slate-700">Panel:</span> <span className="capitalize font-semibold text-slate-800">{finding.panel_type}</span></div>
        )}
        {finding.source_image && (
          <div><span className="font-medium text-slate-700">Source:</span> {finding.source_image}</div>
        )}
        {finding.evidence_snippet && (
          <div data-testid="evidence-snippet"><span className="font-medium text-slate-700">OCR Snippet:</span> &ldquo;{finding.evidence_snippet}&rdquo;</div>
        )}
        {finding.ocr_confidence != null && (
          <div data-testid="evidence-confidence"><span className="font-medium text-slate-700">Confidence:</span> {(finding.ocr_confidence * 100).toFixed(1)}%</div>
        )}
        {finding.evidence_location && (
          <div className="text-slate-400 font-mono text-[10px]">
            Box: {JSON.stringify(finding.evidence_location)}
          </div>
        )}
      </div>
    </div>
  )
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
    },
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || 'Request failed')
  }

  return response.json() as Promise<T>
}

export function InspectionWorkflowPage() {
  const { user } = useAuth()
  const { inspectionId } = useParams()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [inspection, setInspection] = useState<InspectionRecord | null>(null)
  const [uploadedImages, setUploadedImages] = useState<ImageRecord[]>([])
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [captureSide, setCaptureSide] = useState<'front' | 'back' | 'left_side' | 'right_side' | 'other'>('front')
  const [analysis, setAnalysis] = useState<AnalysisRecord | null>(null)
  const [findings, setFindings] = useState<FindingRecord[]>([])
  const [errorMessage, setErrorMessage] = useState('')
  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [reviewing, setReviewing] = useState(false)
  const [finalizing, setFinalizing] = useState(false)
  const [summary, setSummary] = useState<ComplianceSummary | null>(null)
  const [findingFilter, setFindingFilter] = useState<'all' | 'violations' | 'needs_review' | 'passed' | 'pending_review'>('all')
  const [loadFailed, setLoadFailed] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | undefined>(undefined)
  const [rotatingImageId, setRotatingImageId] = useState<string | null>(null)

  const [isEditingDeclarations, setIsEditingDeclarations] = useState(false)
  const [editedDeclarations, setEditedDeclarations] = useState<Record<string, string>>({})
  const [declarationNotes, setDeclarationNotes] = useState('')
  const [savingDeclarations, setSavingDeclarations] = useState(false)
  const [showRawOcrText, setShowRawOcrText] = useState(false)

  const [notice, setNotice] = useState<StatutoryNotice | null>(null)
  const [noticeActionLoading, setNoticeActionLoading] = useState(false)
  const [noticeExpanded, setNoticeExpanded] = useState(false)
  const [recipientRole, setRecipientRole] = useState('MANUFACTURER')
  const [recipientName, setRecipientName] = useState('')
  const [recipientAddress, setRecipientAddress] = useState('')
  const [recipientEmail, setRecipientEmail] = useState('')
  const [responsePeriodDays, setResponsePeriodDays] = useState(15)
  const [compoundingAvailable, setCompoundingAvailable] = useState(false)
  const [officerReviewNotes, setOfficerReviewNotes] = useState('')
  const [confirmIssuance, setConfirmIssuance] = useState(false)
  const [noticeMessage, setNoticeMessage] = useState('')

  const [isAssistantOpen, setIsAssistantOpen] = useState(false)
  const [assistantInitialFindingId, setAssistantInitialFindingId] = useState<string | null>(null)
  const [assistantInitialTab, setAssistantInitialTab] = useState<'summary' | 'explain' | 'trace' | 'manual'>('summary')

  const fetchNotice = useCallback(async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/inspections/${id}/notice`)
      if (res.ok) {
        const data = (await res.json()) as StatutoryNotice
        setNotice(data)
        setRecipientRole(data.recipient_role || 'MANUFACTURER')
        setRecipientName(data.recipient_name || '')
        setRecipientAddress(data.recipient_address || '')
        setRecipientEmail(data.recipient_email || '')
        setResponsePeriodDays(data.response_period_days || 15)
        setCompoundingAvailable(Boolean(data.compounding_available))
        setOfficerReviewNotes(data.officer_review_notes || '')
      } else {
        setNotice(null)
      }
    } catch {
      setNotice(null)
    }
  }, [])

  const handleDraftNotice = async () => {
    if (!inspectionId) return
    try {
      setNoticeActionLoading(true)
      setNoticeMessage('')
      setErrorMessage('')
      const res = await fetch(`${API_BASE}/api/v1/inspections/${inspectionId}/notice/draft`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipient_role: recipientRole,
          recipient_name: recipientName || undefined,
          recipient_address: recipientAddress || undefined,
          recipient_email: recipientEmail || undefined,
        }),
      })
      if (!res.ok) {
        const err = await res.text()
        throw new Error(err || 'Failed to draft notice')
      }
      const created = (await res.json()) as StatutoryNotice
      setNotice(created)
      setNoticeExpanded(true)
      setNoticeMessage('Draft statutory notice created successfully. Complete review before issuance.')
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to draft notice.')
    } finally {
      setNoticeActionLoading(false)
    }
  }

  const handleSaveNotice = async () => {
    if (!notice) return
    try {
      setNoticeActionLoading(true)
      setNoticeMessage('')
      setErrorMessage('')
      const res = await fetch(`${API_BASE}/api/v1/notices/${notice.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipient_role: recipientRole,
          recipient_name: recipientName,
          recipient_address: recipientAddress,
          recipient_email: recipientEmail,
          response_period_days: Number(responsePeriodDays),
          compounding_available: compoundingAvailable,
          officer_review_notes: officerReviewNotes,
        }),
      })
      if (!res.ok) {
        const err = await res.text()
        throw new Error(err || 'Failed to update notice')
      }
      const updated = (await res.json()) as StatutoryNotice
      setNotice(updated)
      setNoticeMessage('Notice draft updated successfully.')
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to update notice.')
    } finally {
      setNoticeActionLoading(false)
    }
  }

  const handleReviewNotice = async () => {
    if (!notice) return
    try {
      setNoticeActionLoading(true)
      setNoticeMessage('')
      setErrorMessage('')
      const res = await fetch(`${API_BASE}/api/v1/notices/${notice.id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          officer_notes: officerReviewNotes || 'Statutory findings and legal basis reviewed by authorized officer.',
          officer_review_notes: officerReviewNotes,
          reviewer_name: 'demo-inspector',
        }),
      })
      if (!res.ok) {
        const err = await res.text()
        throw new Error(err || 'Failed to mark notice as reviewed')
      }
      const reviewed = (await res.json()) as StatutoryNotice
      setNotice(reviewed)
      setNoticeMessage('Notice marked as REVIEWED. Officer may now formally issue.')
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to review notice.')
    } finally {
      setNoticeActionLoading(false)
    }
  }

  const handleIssueNotice = async () => {
    if (!notice) return
    if (!confirmIssuance) {
      setErrorMessage('Please confirm verification before issuing the notice.')
      return
    }
    try {
      setNoticeActionLoading(true)
      setNoticeMessage('')
      setErrorMessage('')
      const res = await fetch(`${API_BASE}/api/v1/notices/${notice.id}/issue`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          officer_review_notes: officerReviewNotes || undefined,
        }),
      })
      if (!res.ok) {
        const err = await res.text()
        throw new Error(err || 'Failed to issue notice')
      }
      const issued = (await res.json()) as StatutoryNotice
      setNotice(issued)
      setNoticeMessage('Notice successfully ISSUED and permanently locked.')
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to issue notice.')
    } finally {
      setNoticeActionLoading(false)
    }
  }

  const refreshSummary = useCallback(async (id: string) => {
    try {
      const summaryData = await fetchJson<ComplianceSummary>(`/api/v1/inspections/${id}/summary`)
      setSummary(summaryData)
    } catch {
      // non-blocking fallback
    }
  }, [])

  const loadFindings = useCallback(async (id: string) => {
    try {
      const inspectionFindings = await fetchJson<FindingRecord[]>(`/api/v1/inspections/${id}/findings`)
      setFindings(inspectionFindings)
    } catch {
      // non-blocking fallback
    }
  }, [])

  const startEditingDeclarations = () => {
    if (!analysis) return
    const initial: Record<string, string> = {}
    const standardFields = [
      'commodity_name',
      'manufacturer_name',
      'manufacturer_address',
      'net_quantity',
      'quantity_unit',
      'retail_sale_price',
      'month_year',
      'consumer_contact',
      'country_of_origin',
    ]
    for (const f of standardFields) {
      const val = analysis.structured_declarations?.[f]
      initial[f] = val != null ? (typeof val === 'object' ? JSON.stringify(val) : String(val)) : ''
    }
    for (const [k, v] of Object.entries(analysis.structured_declarations ?? {})) {
      if (!(k in initial)) {
        initial[k] = v != null ? (typeof v === 'object' ? JSON.stringify(v) : String(v)) : ''
      }
    }
    setEditedDeclarations(initial)
    setDeclarationNotes('')
    setIsEditingDeclarations(true)
  }

  const handleSaveDeclarations = async () => {
    if (!inspectionId) return
    try {
      setSavingDeclarations(true)
      setErrorMessage('')
      const resp = await fetchJson<{
        inspection_id: string
        structured_declarations: Record<string, unknown>
        raw_ocr_declarations: Record<string, unknown>
        inspector_corrections: InspectorCorrection[]
        compliance_summary: ComplianceSummary
        analysis: AnalysisRecord
      }>(`/api/v1/inspections/${inspectionId}/declarations`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          declarations: editedDeclarations,
          notes: declarationNotes.trim() || undefined,
        }),
      })
      setAnalysis(resp.analysis)
      setIsEditingDeclarations(false)
      await Promise.all([
        loadFindings(inspectionId),
        refreshSummary(inspectionId),
      ])
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to save declaration corrections.')
    } finally {
      setSavingDeclarations(false)
    }
  }

  const stepIndex = inspection ? getStepIndex(inspection.status) : 0
  const hasSelectedFiles = selectedFiles.length > 0 || (fileInputRef.current?.files?.length ?? 0) > 0

  // Manage preview URL with cleanup to avoid memory leaks
  useEffect(() => {
    const file = selectedFiles[0]
    if (!file) {
      setPreviewUrl(undefined)
      return
    }
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    return () => {
      URL.revokeObjectURL(url)
    }
  }, [selectedFiles])
  const groupedImages = useMemo(() => {
    const groups = { front: [] as ImageRecord[], back: [] as ImageRecord[], left_side: [] as ImageRecord[], right_side: [] as ImageRecord[], other: [] as ImageRecord[] }
    for (const image of uploadedImages) {
      const type = (image.image_type || 'front').toLowerCase().replace(/\s+/g, '_')
      if (type in groups) {
        groups[type as keyof typeof groups].push(image)
      } else {
        groups.front.push(image)
      }
    }
    return groups
  }, [uploadedImages])

  const resolveFindingImageUrl = (finding: FindingRecord): string | null => {
    if (finding.image_id && finding.inspection_id) {
      return `${API_BASE}/api/v1/inspections/${finding.inspection_id}/images/${finding.image_id}/file`
    }
    if (finding.storage_path) {
      return `${API_BASE}/${finding.storage_path}`
    }
    if (finding.source_image) {
      const matching = uploadedImages.find((img) => img.file_name === finding.source_image)
      if (matching?.storage_path) {
        return `${API_BASE}/${matching.storage_path}`
      }
      if (matching?.id && finding.inspection_id) {
        return `${API_BASE}/api/v1/inspections/${finding.inspection_id}/images/${matching.id}/file`
      }
    }
    if (uploadedImages.length > 0 && uploadedImages[0].storage_path) {
      return `${API_BASE}/${uploadedImages[0].storage_path}`
    }
    return null
  }

  useEffect(() => {
    if (!inspectionId) {
      return
    }

    const loadInspection = async () => {
      try {
        const current = await fetchJson<InspectionRecord>(`/api/v1/inspections/${inspectionId}`)
        setInspection(current)

        const images = await fetchJson<ImageRecord[]>(`/api/v1/inspections/${inspectionId}/images`)
        setUploadedImages(images)

        const inspectionAnalysis = await fetchJson<AnalysisRecord | null>(`/api/v1/inspections/${inspectionId}/analysis`)
        if (inspectionAnalysis) {
          setAnalysis(inspectionAnalysis)
        }

        const inspectionFindings = await fetchJson<FindingRecord[]>(`/api/v1/inspections/${inspectionId}/findings`)
        setFindings(inspectionFindings)
        void refreshSummary(inspectionId)
        void fetchNotice(inspectionId)
      } catch (loadError) {
        setLoadFailed(true)
        setErrorMessage(loadError instanceof Error ? loadError.message : 'Unable to load inspection.')
      }
    }

    void loadInspection()
  }, [inspectionId, refreshSummary, fetchNotice])

  const uploadImages = async () => {
    if (!inspectionId || selectedFiles.length === 0) {
      setErrorMessage('Please choose one or more images before uploading.')
      return
    }

    const formData = new FormData()
    formData.append('image_type', captureSide)
    selectedFiles.forEach((file) => formData.append('files', file))

    try {
      setUploading(true)
      setErrorMessage('')
      const response = await fetch(`${API_BASE}/api/v1/inspections/${inspectionId}/upload-images`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(errorText || 'Image upload failed')
      }

      const images = (await response.json()) as ImageRecord[]
      setUploadedImages((current) => [...images, ...current])
      setSelectedFiles([])
      // Also reset the native file input so hasSelectedFiles reflects the cleared state
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      setInspection((current) => (current ? { ...current, status: 'DRAFT' } : current))
    } catch (uploadError) {
      setErrorMessage(uploadError instanceof Error ? uploadError.message : 'Image upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const rotateImage = async (imageId: string) => {
    if (!inspectionId) return
    const img = uploadedImages.find((i) => i.id === imageId)
    const currentAngle = img?.rotation_metadata?.rotation_angle ?? 0
    const nextAngle = (currentAngle + 90) % 360

    try {
      setRotatingImageId(imageId)
      setErrorMessage('')
      const updated = await fetchJson<ImageRecord>(
        `/api/v1/inspections/${inspectionId}/images/${imageId}/rotate`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ angle: nextAngle }),
        }
      )
      setUploadedImages((current) =>
        current.map((item) => (item.id === imageId ? { ...item, ...updated } : item))
      )
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to rotate image.')
    } finally {
      setRotatingImageId(null)
    }
  }

  const runAnalysis = async () => {
    if (!inspectionId) {
      return
    }

    try {
      setAnalyzing(true)
      setErrorMessage('')
      const result = await fetchJson<AnalysisRecord>(`/api/v1/inspections/${inspectionId}/analyze`, {
        method: 'POST',
      })
      setAnalysis(result)
      setInspection((current) => (current ? { ...current, status: 'REVIEW_REQUIRED' } : current))

      const nextFindings = await fetchJson<FindingRecord[]>(`/api/v1/inspections/${inspectionId}/findings`)
      setFindings(nextFindings)
      void refreshSummary(inspectionId)
    } catch (analysisError) {
      setErrorMessage(analysisError instanceof Error ? analysisError.message : 'Analysis could not be completed.')
    } finally {
      setAnalyzing(false)
    }
  }

  const submitFindingDecision = async (findingId: string, decision: 'confirm' | 'reject' | 'manual_review') => {
    if (!inspectionId) {
      return
    }

    try {
      setReviewing(true)
      setErrorMessage('')
      await fetchJson<{ id: string }>(`/api/v1/inspections/${inspectionId}/findings/${findingId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          inspection_id: inspectionId,
          decision,
          reviewer_name: 'demo-inspector',
          notes: `Inspector marked finding as ${decision}.`,
        }),
      })
      setFindings((current) =>
        current.map((f) =>
          f.id === findingId
            ? {
              ...f,
              inspector_decision: decision,
              reviewer_name: 'demo-inspector',
              reviewed_at: new Date().toISOString(),
            }
            : f,
        ),
      )
      void refreshSummary(inspectionId)
    } catch (reviewError) {
      setErrorMessage(reviewError instanceof Error ? reviewError.message : 'Finding decision could not be recorded.')
    } finally {
      setReviewing(false)
    }
  }

  const submitDecision = async (decision: 'confirm' | 'reject' | 'manual_review') => {
    if (!inspectionId) {
      return
    }

    try {
      setReviewing(true)
      setErrorMessage('')
      await fetchJson<{ id: string }>(`/api/v1/inspections/${inspectionId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          inspection_id: inspectionId,
          decision,
          reviewer_name: 'demo-inspector',
          notes: `DEMO workflow review selected ${decision}.`,
        }),
      })
      void refreshSummary(inspectionId)
      // Do NOT optimistically set status to COMPLETED here.
      // Only the /finalize response should advance the inspection to COMPLETED.
      setFindings((current) =>
        current.map((f) => ({
          ...f,
          inspector_decision: decision,
          reviewer_name: 'demo-inspector',
          reviewed_at: new Date().toISOString(),
        })),
      )
    } catch (reviewError) {
      setErrorMessage(reviewError instanceof Error ? reviewError.message : 'Review decision could not be recorded.')
    } finally {
      setReviewing(false)
    }
  }

  const finalizeInspection = async () => {
    if (!inspectionId) {
      return
    }

    try {
      setFinalizing(true)
      setErrorMessage('')
      const result = await fetchJson<InspectionRecord>(`/api/v1/inspections/${inspectionId}/finalize`, {
        method: 'POST',
      })
      setInspection(result)
      void refreshSummary(inspectionId)
      void fetchNotice(inspectionId)
    } catch (finalizeError) {
      setErrorMessage(finalizeError instanceof Error ? finalizeError.message : 'Inspection could not be finalized.')
    } finally {
      setFinalizing(false)
    }
  }

  const declarationEntries = analysis ? Object.entries(analysis.structured_declarations ?? {}) : []
  const rawOcrDeclarations = (analysis?.extraction_metadata?.raw_ocr_declarations ?? {}) as Record<string, unknown>
  const inspectorCorrections = (analysis?.extraction_metadata?.inspector_corrections ?? []) as InspectorCorrection[]

  const isFieldVerified = (fieldName: string) => {
    return inspectorCorrections.some((c) => c.field_name === fieldName)
  }

  const getOriginalOcrValue = (fieldName: string) => {
    if (rawOcrDeclarations && fieldName in rawOcrDeclarations) {
      const raw = rawOcrDeclarations[fieldName]
      return raw != null ? (typeof raw === 'object' ? JSON.stringify(raw) : String(raw)) : 'Not detected'
    }
    const matchingCorrection = inspectorCorrections.find((c) => c.field_name === fieldName)
    if (matchingCorrection && matchingCorrection.original_value != null) {
      return typeof matchingCorrection.original_value === 'object'
        ? JSON.stringify(matchingCorrection.original_value)
        : String(matchingCorrection.original_value)
    }
    return null
  }

  const reviewedCount = findings.filter((f) => f.inspector_decision != null).length
  const allReviewed = findings.length === 0 || reviewedCount === findings.length
  const hasManualReview = findings.some((f) => f.inspector_decision === 'manual_review')

  const filteredFindings = useMemo(() => {
    return findings.filter((finding) => {
      if (findingFilter === 'violations') {
        return (
          finding.status !== 'resolved' &&
          (finding.severity === 'critical' ||
            finding.severity === 'major' ||
            finding.rule_status === 'POTENTIAL_VIOLATION')
        )
      }
      if (findingFilter === 'needs_review') {
        return (
          finding.status !== 'resolved' &&
          (finding.rule_status === 'MANUAL_REVIEW' ||
            finding.rule_check_id === 'PCR-006' ||
            finding.rule_check_id === 'PCR-008' ||
            finding.severity === 'warning')
        )
      }
      if (findingFilter === 'passed') {
        return finding.status === 'resolved' || finding.severity === 'pass' || finding.rule_status === 'PASS'
      }
      if (findingFilter === 'pending_review') {
        return finding.inspector_decision == null
      }
      return true
    })
  }, [findings, findingFilter])

  // Render a clean empty state when the inspection could not be loaded (e.g. invalid UUID / 404)
  if (loadFailed) {
    return (
      <div>
        <PageHeader title="Inspection not found" description="The requested inspection could not be loaded." />
        <div
          data-testid="inspection-not-found"
          className="mt-10 rounded-2xl border border-red-200 bg-red-50 p-10 text-center"
        >
          <p className="text-lg font-semibold text-red-700">Inspection not found</p>
          <p className="mt-2 text-sm text-red-600">{errorMessage || 'This inspection does not exist or could not be retrieved.'}</p>
          <a
            href="/inspections"
            className="mt-6 inline-block rounded-lg bg-red-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-red-700"
          >
            ← Back to inspection list
          </a>
        </div>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title={inspection?.title ?? 'Inspection workflow'}
        description={inspection ? `Inspection ${inspection.inspection_number}` : 'Loading inspection details...'}
        action={
          <div className="flex items-center gap-3">
            <Button
              id="open-assistant-btn"
              data-testid="open-assistant-btn"
              variant="outline"
              size="sm"
              onClick={() => {
                setAssistantInitialFindingId(null)
                setAssistantInitialTab('summary')
                setIsAssistantOpen(true)
              }}
              className="flex items-center gap-2 border-indigo-300 bg-indigo-50/70 text-indigo-700 hover:bg-indigo-100 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-300"
            >
              <Bot className="h-4 w-4" />
              <span>PRAMAN Assistant</span>
            </Button>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${getStatusClass(inspection?.status ?? 'DRAFT')}`}>
              {inspection?.status ?? 'DRAFT'}
            </span>
          </div>
        }
      />

      {errorMessage ? <p className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{errorMessage}</p> : null}

      <div className="mb-6 grid gap-3 md:grid-cols-5">
        {steps.map((step, index) => (
          <div key={step} className={`rounded-xl border p-3 text-sm font-medium ${index <= stepIndex ? 'border-sky-200 bg-sky-50 text-sky-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>
            {index + 1}. {step}
          </div>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Capture & upload evidence</CardTitle>
              <CardDescription>Attach package images from the device or local files before running OCR analysis.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
                <div>
                  <label htmlFor="inspection-image-upload" className="mb-2 block text-sm font-medium text-slate-700">
                    Select package image(s)
                  </label>
                  <input
                    ref={fileInputRef}
                    id="inspection-image-upload"
                    name="inspection-image-upload"
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    aria-label="Upload package images"
                    data-testid="inspection-image-upload"
                    multiple
                    onChange={(event) => setSelectedFiles(Array.from(event.target.files ?? []))}
                    className="block w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                  />
                </div>

                <div>
                  <label htmlFor="capture-side" className="mb-2 block text-sm font-medium text-slate-700">Image side</label>
                  <select
                    id="capture-side"
                    value={captureSide}
                    onChange={(event) => setCaptureSide(event.target.value as 'front' | 'back' | 'left_side' | 'right_side' | 'other')}
                    className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                  >
                    <option value="front">Front</option>
                    <option value="back">Back</option>
                    <option value="left_side">Left Side</option>
                    <option value="right_side">Right Side</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>

              {previewUrl ? (
                <img src={previewUrl} alt="Selected package evidence" className="h-56 w-full rounded-xl object-cover border border-slate-200 bg-slate-50" />
              ) : null}

              <div className="flex flex-wrap gap-3">
                <Button onClick={() => void uploadImages()} disabled={uploading || !hasSelectedFiles}>
                  {uploading ? 'Uploading...' : 'Upload image'}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Evidence gallery</CardTitle>
              <CardDescription>Images captured and stored for the current inspection.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {uploadedImages.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">No package images uploaded yet.</div>
              ) : (
                Object.entries(groupedImages).map(([key, images]) => (
                  <div key={key} className="space-y-2">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{getLabelForImageType(key)}</div>
                    {images.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">No images in this side group.</div>
                    ) : (
                      <div className="grid gap-3 md:grid-cols-2">
                        {images.map((image) => {
                          const qa = image.quality_assessment
                          const rot = image.rotation_metadata
                          const isRotating = rotatingImageId === image.id
                          return (
                            <div key={image.id} className="overflow-hidden rounded-xl border border-slate-200 bg-slate-50 flex flex-col justify-between" data-testid="image-card">
                              <div className="relative">
                                <img
                                  src={`${API_BASE}/api/v1/inspections/${inspectionId}/images/${image.id}/file?t=${rot?.updated_at ?? image.created_at}`}
                                  alt={image.file_name}
                                  className="h-44 w-full object-cover"
                                />
                                <div className="absolute top-2 right-2 flex flex-col items-end gap-1">
                                  {qa && (
                                    <span
                                      data-testid="image-quality-badge"
                                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold tracking-wide shadow-sm ${qa.quality_verdict === 'ACCEPTABLE'
                                          ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                          : qa.quality_verdict === 'WARNING_DEGRADED'
                                            ? 'bg-amber-100 text-amber-800 border border-amber-300'
                                            : 'bg-rose-100 text-rose-800 border border-rose-300'
                                        }`}
                                    >
                                      {qa.quality_verdict === 'ACCEPTABLE' && '✓ Optimal Quality'}
                                      {qa.quality_verdict === 'WARNING_DEGRADED' && '⚠ Degraded Quality'}
                                      {qa.quality_verdict === 'UNREADABLE' && '✖ Unreadable Quality'}
                                    </span>
                                  )}
                                  {rot && rot.rotation_angle ? (
                                    <span
                                      data-testid="image-rotation-badge"
                                      className="inline-flex items-center gap-1 rounded-full bg-blue-100 text-blue-800 border border-blue-300 px-2 py-0.5 text-[10px] font-semibold shadow-xs"
                                      title="Rotated derivative representation. Original evidence file is preserved bit-for-bit."
                                    >
                                      ↻ Rotated {rot.rotation_angle}° • Original Preserved
                                    </span>
                                  ) : null}
                                </div>
                                <div className="absolute bottom-2 right-2">
                                  <button
                                    type="button"
                                    onClick={() => void rotateImage(image.id)}
                                    disabled={isRotating}
                                    data-testid="rotate-image-btn"
                                    data-image-id={image.id}
                                    className="inline-flex items-center gap-1 rounded-md bg-white/95 backdrop-blur-xs px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-sm border border-slate-300 hover:bg-slate-100 cursor-pointer disabled:opacity-50"
                                    title="Rotate 90° Clockwise (Non-destructive derivative; original evidence remains immutable)"
                                  >
                                    {isRotating ? 'Rotating...' : '↻ Rotate 90°'}
                                  </button>
                                </div>
                              </div>
                              <div className="p-3 text-xs space-y-2">
                                <div className="flex items-center justify-between gap-2 text-slate-700 font-medium">
                                  <span className="truncate" title={image.file_name}>{image.file_name}</span>
                                  <span className="text-slate-500 uppercase text-[10px] tracking-wider shrink-0">{getLabelForImageType(image.image_type)}</span>
                                </div>
                                {qa && (
                                  <div data-testid="quality-metrics" className="rounded-lg border border-slate-200/80 bg-white/80 p-2 text-[11px] text-slate-600 space-y-1">
                                    <div className="flex flex-wrap items-center justify-between gap-1 text-[10px] text-slate-500">
                                      <span>Sharpness: <strong className="text-slate-700">{qa.sharpness_score}</strong></span>
                                      <span>Glare: <strong className="text-slate-700">{qa.glare_percentage}%</strong></span>
                                      <span>Dimensions: <strong className="text-slate-700">{qa.width}×{qa.height}px</strong> {qa.resolution_adequate ? '✓' : '⚠'}</span>
                                    </div>
                                    {qa.issues.length > 0 && (
                                      <div className="text-rose-700 font-medium text-[10.5px]">
                                        {qa.issues.join(' ')}
                                      </div>
                                    )}
                                    {qa.recommendations.length > 0 && (
                                      <div className="text-slate-500 italic text-[10px]">
                                        Tip: {qa.recommendations.join(' ')}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card data-testid="ocr-analysis-card">
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>OCR Analysis & Extraction Review</CardTitle>
                  <CardDescription>
                    Structured declarations extracted from evidence. Inspectors may review and correct values.
                  </CardDescription>
                </div>
                {analysis && !isEditingDeclarations && (
                  <Button
                    type="button"
                    variant="outline"
                    data-testid="edit-declarations-btn"
                    onClick={startEditingDeclarations}
                    className="text-xs font-semibold"
                  >
                    ✎ Edit Declarations
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {uploadedImages.some((img) => img.quality_assessment?.quality_verdict === 'UNREADABLE') && (
                <div data-testid="quality-warning-banner" className="rounded-xl border border-rose-300 bg-rose-50 p-3.5 text-xs text-rose-800 space-y-1.5">
                  <div className="flex items-center gap-1.5 font-bold text-rose-900">
                    <span>⚠ Image Quality Pre-Check Advisory</span>
                  </div>
                  <p>
                    One or more uploaded images have been detected as <strong>UNREADABLE</strong> (due to severe blur, excessive glare reflection, or inadequate resolution). Fine print statutory declarations may fail extraction.
                  </p>
                  <p className="text-rose-700">
                    <strong>Recommendation:</strong> Retake the affected photo with steady focus and balanced lighting. You may still proceed with analysis below if you wish to inspect existing text.
                  </p>
                </div>
              )}
              {uploadedImages.some((img) => img.quality_assessment?.quality_verdict === 'WARNING_DEGRADED') && !uploadedImages.some((img) => img.quality_assessment?.quality_verdict === 'UNREADABLE') && (
                <div data-testid="quality-warning-banner" className="rounded-xl border border-amber-300 bg-amber-50 p-3.5 text-xs text-amber-800 space-y-1.5">
                  <div className="flex items-center gap-1.5 font-bold text-amber-900">
                    <span>ℹ Image Quality Diagnostic Notice</span>
                  </div>
                  <p>
                    Moderate blur, surface glare, or suboptimal resolution was detected on one or more images. Text extraction may require manual verification.
                  </p>
                </div>
              )}

              <Button onClick={runAnalysis} disabled={analyzing || uploadedImages.length === 0} data-testid="run-analysis-btn">
                {analyzing
                  ? (uploadedImages.length > 1 ? `Analyzing ${uploadedImages.length} package panels...` : 'Running analysis...')
                  : (uploadedImages.length > 1 ? `Run Demo Analysis (${uploadedImages.length} Panels Fused)` : 'Run Demo Analysis')}
              </Button>

              {analysis ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                    <div>
                      Demo confidence: <strong>{Math.round((analysis.confidence ?? 0) * 100)}%</strong>
                      {inspectorCorrections.length > 0 && (
                        <span className="ml-2 font-medium text-emerald-700">
                          • {inspectorCorrections.length} field(s) Inspector Verified
                        </span>
                      )}
                    </div>
                    {analysis.ocr_text && (
                      <button
                        type="button"
                        onClick={() => setShowRawOcrText(!showRawOcrText)}
                        className="text-xs font-semibold text-emerald-900 hover:underline cursor-pointer"
                        data-testid="toggle-raw-ocr-btn"
                      >
                        {showRawOcrText ? 'Hide Raw OCR Text' : 'View Raw OCR Text'}
                      </button>
                    )}
                  </div>

                  {showRawOcrText && analysis.ocr_text && (
                    <div
                      data-testid="raw-ocr-text-panel"
                      className="rounded-xl border border-slate-300 bg-slate-900 p-3.5 font-mono text-xs text-slate-100 space-y-1 overflow-x-auto max-h-48"
                    >
                      <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">
                        Immutable Raw OCR Text Stream (Evidence Baseline)
                      </div>
                      <pre className="whitespace-pre-wrap">{analysis.ocr_text}</pre>
                    </div>
                  )}

                  {isEditingDeclarations ? (
                    <div className="space-y-4 rounded-xl border border-indigo-200 bg-indigo-50/30 p-4" data-testid="extraction-review-editor">
                      <div className="flex items-center justify-between text-xs text-indigo-900">
                        <span className="font-bold">
                          Extraction Review Mode: Edit structured declarations below.
                        </span>
                        <span className="text-[11px] text-slate-500">
                          Deterministic ComplianceEngine re-evaluates upon save.
                        </span>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-2">
                        {Object.keys(editedDeclarations).map((fieldKey) => {
                          const origOcr = rawOcrDeclarations[fieldKey]
                          return (
                            <div key={fieldKey} className="rounded-lg border border-slate-200 bg-white p-3 space-y-1.5 shadow-xs">
                              <label htmlFor={`edit-${fieldKey}`} className="block text-[11px] font-semibold uppercase tracking-wider text-slate-700">
                                {DECLARATION_FIELD_LABELS[fieldKey] ?? fieldKey}
                              </label>
                              <input
                                id={`edit-${fieldKey}`}
                                name={fieldKey}
                                type="text"
                                data-testid={`input-${fieldKey}`}
                                value={editedDeclarations[fieldKey]}
                                onChange={(e) =>
                                  setEditedDeclarations((prev) => ({
                                    ...prev,
                                    [fieldKey]: e.target.value,
                                  }))
                                }
                                className="w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                                placeholder={`Enter ${DECLARATION_FIELD_LABELS[fieldKey] ?? fieldKey}`}
                              />
                              {origOcr != null && (
                                <div className="text-[10px] text-slate-500 truncate" title={String(origOcr)}>
                                  Raw OCR: &ldquo;{String(origOcr)}&rdquo;
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>

                      <div className="space-y-1.5">
                        <label htmlFor="correction-notes" className="block text-xs font-semibold text-slate-700">
                          Inspector Verification Notes (Audit Trail)
                        </label>
                        <input
                          id="correction-notes"
                          type="text"
                          data-testid="input-correction-notes"
                          value={declarationNotes}
                          onChange={(e) => setDeclarationNotes(e.target.value)}
                          placeholder="e.g. Magnified label examination confirmed MRP on crimp fold"
                          className="w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                        />
                      </div>

                      <div className="flex flex-wrap items-center gap-3 pt-2">
                        <Button
                          type="button"
                          data-testid="save-declarations-btn"
                          onClick={() => void handleSaveDeclarations()}
                          disabled={savingDeclarations}
                          className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs"
                        >
                          {savingDeclarations ? 'Re-evaluating compliance...' : 'Save & Re-evaluate Compliance'}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          data-testid="cancel-declarations-btn"
                          onClick={() => setIsEditingDeclarations(false)}
                          disabled={savingDeclarations}
                          className="text-xs"
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="grid gap-3 md:grid-cols-2">
                      {declarationEntries.map(([key, value]) => {
                        const verified = isFieldVerified(key)
                        const origOcrVal = getOriginalOcrValue(key)
                        const meta = analysis.extraction_metadata as Record<string, unknown> | undefined
                        const provenance = (meta?.fused_provenance as Record<string, { primary_image_type?: string }> | undefined)?.[key]
                        const conflict = (meta?.panel_conflicts as Record<string, { has_conflict?: boolean; conflict_description?: string; candidates?: Array<{ image_type?: string; raw_value?: string; file_name?: string }> }> | undefined)?.[key]
                        const hasConflict = Boolean(conflict?.has_conflict && !verified)

                        return (
                          <div
                            key={key}
                            className={`rounded-xl border p-3 transition-colors ${hasConflict
                                ? 'border-amber-300 bg-amber-50/50 shadow-xs'
                                : verified
                                  ? 'border-emerald-300 bg-emerald-50/40 shadow-xs'
                                  : 'border-slate-200 bg-slate-50'
                              }`}
                            data-testid="declaration-field-card"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600">
                                <span>{key}</span>
                                {DECLARATION_FIELD_LABELS[key] && (
                                  <span className="ml-1.5 text-[10px] font-normal lowercase tracking-normal text-slate-400 capitalize">
                                    • {DECLARATION_FIELD_LABELS[key]}
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-1.5">
                                {provenance?.primary_image_type && (
                                  <span
                                    data-testid={`panel-badge-${key}`}
                                    className="inline-flex items-center rounded-full bg-slate-200/80 px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-wider text-slate-700"
                                  >
                                    {provenance.primary_image_type} panel
                                  </span>
                                )}
                                {verified && (
                                  <span
                                    data-testid="inspector-verified-badge"
                                    className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800 border border-emerald-300 shadow-xs"
                                  >
                                    ✓ Inspector Verified
                                  </span>
                                )}
                              </div>
                            </div>
                            <div className="mt-1 text-sm font-medium text-slate-900" data-testid={`declaration-value-${key}`}>
                              {value != null && value !== '' ? (typeof value === 'object' ? JSON.stringify(value) : String(value)) : 'Not provided'}
                            </div>

                            {hasConflict && conflict && (
                              <div data-testid={`conflict-alert-${key}`} className="mt-2 rounded-lg border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900 space-y-1">
                                <div className="flex items-center gap-1 font-bold text-amber-950 text-[11px]">
                                  <span>⚠ Cross-Panel Conflict (Manual Review Required)</span>
                                </div>
                                <p className="text-[11px] leading-tight text-amber-850">
                                  {conflict.conflict_description}
                                </p>
                                {Array.isArray(conflict.candidates) && conflict.candidates.length > 0 && (
                                  <div className="flex flex-wrap gap-1.5 pt-0.5">
                                    {conflict.candidates.map((c, idx) => (
                                      <span key={idx} className="rounded bg-amber-100/90 border border-amber-200 px-1.5 py-0.5 text-[10px] font-mono text-amber-900">
                                        {c.image_type?.toUpperCase()} ({c.file_name}): &ldquo;{c.raw_value}&rdquo;
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}

                            {verified && origOcrVal !== null && origOcrVal !== String(value) && (
                              <div className="mt-2 pt-1.5 border-t border-emerald-200/60 text-[11px] text-slate-500" data-testid={`original-ocr-${key}`}>
                                <span className="font-medium text-slate-600">Original OCR:</span>{' '}
                                <span className="italic line-through text-slate-500">{origOcrVal || 'Empty'}</span>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              ) : null}
            </CardContent>
          </Card>

          {/* Phase 6F: Compliance Summary & Inspection Result */}
          {findings.length > 0 && (
            <Card data-testid="compliance-summary-card" className="border-slate-200 bg-white shadow-sm">
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-base font-semibold text-slate-900">Compliance & Review Summary</CardTitle>
                    <CardDescription>
                      Deterministic statutory evaluation & inspector decision audit
                      {summary?.catalog_version && (
                        <span className="ml-2 font-mono text-xs text-slate-500">
                          (Rules v{summary.catalog_version} • Date: {summary.inspection_date ?? 'N/A'})
                        </span>
                      )}
                    </CardDescription>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      data-testid="summary-engine-result"
                      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider ${summary?.engine_summary.overall_result === 'COMPLIANT'
                          ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                          : summary?.engine_summary.overall_result === 'POTENTIAL_VIOLATIONS_DETECTED'
                            ? 'bg-rose-100 text-rose-800 border border-rose-300'
                            : summary?.engine_summary.overall_result === 'WARNINGS_OR_MANUAL_REVIEW'
                              ? 'bg-amber-100 text-amber-800 border border-amber-300'
                              : 'bg-slate-100 text-slate-700 border border-slate-300'
                        }`}
                    >
                      Engine: {summary?.engine_summary.overall_result?.replace(/_/g, ' ') ?? 'PENDING'}
                    </span>
                    <span
                      data-testid="summary-inspector-result"
                      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider ${summary?.inspector_summary.review_status === 'COMPLETE'
                          ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                          : summary?.inspector_summary.review_status === 'IN_PROGRESS'
                            ? 'bg-sky-100 text-sky-800 border border-sky-300'
                            : 'bg-slate-100 text-slate-700 border border-slate-300'
                        }`}
                    >
                      Review: {summary?.inspector_summary.review_status ?? 'PENDING'}
                    </span>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <button
                    type="button"
                    onClick={() => setFindingFilter(findingFilter === 'passed' ? 'all' : 'passed')}
                    className={`rounded-xl border p-3 text-left transition hover:border-emerald-400 ${findingFilter === 'passed' ? 'border-emerald-500 bg-emerald-50/50 ring-1 ring-emerald-400' : 'border-slate-200 bg-slate-50'
                      }`}
                  >
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-emerald-700">Passed Checks</div>
                    <div className="mt-1 text-2xl font-bold text-emerald-800" data-testid="summary-passed-count">
                      {summary?.engine_summary.passed ?? findings.filter((f) => f.status === 'resolved' || f.severity === 'pass').length}
                    </div>
                    <div className="text-xs text-slate-500">Fully compliant declarations</div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setFindingFilter(findingFilter === 'violations' ? 'all' : 'violations')}
                    className={`rounded-xl border p-3 text-left transition hover:border-rose-400 ${findingFilter === 'violations' ? 'border-rose-500 bg-rose-50/50 ring-1 ring-rose-400' : 'border-slate-200 bg-slate-50'
                      }`}
                  >
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-rose-700">Potential Violations</div>
                    <div className="mt-1 text-2xl font-bold text-rose-800" data-testid="summary-violations-count">
                      {summary?.engine_summary.potential_violations ?? findings.filter((f) => f.status !== 'resolved' && f.title.toLowerCase().includes('violation')).length}
                    </div>
                    <div className="text-xs text-slate-500">Critical statutory defects</div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setFindingFilter(findingFilter === 'needs_review' ? 'all' : 'needs_review')}
                    className={`rounded-xl border p-3 text-left transition hover:border-amber-400 ${findingFilter === 'needs_review' ? 'border-amber-500 bg-amber-50/50 ring-1 ring-amber-400' : 'border-slate-200 bg-slate-50'
                      }`}
                  >
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-amber-700">Manual Review / Warnings</div>
                    <div className="mt-1 text-2xl font-bold text-amber-800" data-testid="summary-manual-review-count">
                      {(summary?.engine_summary.manual_review ?? 0) + (summary?.engine_summary.warnings ?? 0) ||
                        findings.filter(
                          (f) =>
                            f.status !== 'resolved' &&
                            (f.title.toLowerCase().includes('manual') ||
                              f.title.toLowerCase().includes('verification') ||
                              f.title.toLowerCase().includes('warning')),
                        ).length}
                    </div>
                    <div className="text-xs text-slate-500">Requires human judgment</div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setFindingFilter(findingFilter === 'pending_review' ? 'all' : 'pending_review')}
                    className={`rounded-xl border p-3 text-left transition hover:border-sky-400 ${findingFilter === 'pending_review' ? 'border-sky-500 bg-sky-50/50 ring-1 ring-sky-400' : 'border-slate-200 bg-slate-50'
                      }`}
                  >
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-sky-700">Inspector Review</div>
                    <div className="mt-1 text-2xl font-bold text-sky-800" data-testid="summary-review-progress">
                      {summary?.inspector_summary.reviewed_count ?? findings.filter((f) => f.inspector_decision != null).length} / {findings.length}
                    </div>
                    <div className="text-xs text-slate-500">
                      {summary?.inspector_summary.confirmed_count ?? findings.filter((f) => f.inspector_decision === 'confirm').length} approved • {summary?.inspector_summary.rejected_count ?? findings.filter((f) => f.inspector_decision === 'reject').length} rejected
                    </div>
                  </button>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-slate-700">Severity:</span>
                    <span className="text-rose-700 font-medium">Critical: {summary?.engine_summary.severity_distribution.critical ?? findings.filter((f) => f.severity === 'critical').length}</span>
                    <span className="text-amber-700 font-medium">Major: {summary?.engine_summary.severity_distribution.major ?? findings.filter((f) => f.severity === 'major').length}</span>
                    <span className="text-slate-600 font-medium">Warning: {summary?.engine_summary.severity_distribution.warning ?? findings.filter((f) => f.severity === 'warning').length}</span>
                    <span className="text-emerald-700 font-medium">Pass: {summary?.engine_summary.severity_distribution.pass_count ?? findings.filter((f) => f.severity === 'pass').length}</span>
                  </div>

                  {findingFilter !== 'all' && (
                    <button
                      type="button"
                      onClick={() => setFindingFilter('all')}
                      className="text-xs font-semibold text-sky-700 underline hover:text-sky-900"
                    >
                      Reset Filter (Showing {filteredFindings.length} of {findings.length})
                    </button>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle>Findings</CardTitle>
                  <CardDescription>
                    Deterministic validation results based on the extracted declaration fields.
                    {findingFilter !== 'all' && (
                      <span className="ml-1 text-sky-700 font-medium">(Filtered: {findingFilter.replace('_', ' ')})</span>
                    )}
                  </CardDescription>
                </div>
                {findingFilter !== 'all' && (
                  <button
                    type="button"
                    onClick={() => setFindingFilter('all')}
                    className="text-xs font-medium text-slate-500 underline hover:text-slate-800"
                  >
                    Clear filter
                  </button>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {findings.length === 0 ? (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">No findings generated yet.</div>
              ) : filteredFindings.length === 0 ? (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                  No findings matching current filter &ldquo;{findingFilter.replace('_', ' ')}&rdquo;.{' '}
                  <button
                    type="button"
                    onClick={() => setFindingFilter('all')}
                    className="text-sky-700 font-semibold underline"
                  >
                    Show all findings
                  </button>
                </div>
              ) : (
                filteredFindings.map((finding) => (
                  <div key={finding.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-900">{finding.rule_check_id}</span>
                        <p className="text-sm font-semibold text-slate-900">{finding.title}</p>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-700" title="Automated Statutory Engine Evaluation">
                          Engine: {finding.status}
                        </span>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${finding.severity === 'pass'
                            ? 'bg-emerald-100 text-emerald-800'
                            : finding.severity === 'critical'
                              ? 'bg-rose-100 text-rose-800'
                              : 'bg-amber-100 text-amber-800'
                          }`}>
                          {finding.severity}
                        </span>
                        <span
                          data-testid="inspector-decision-badge"
                          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${finding.inspector_decision === 'confirm'
                              ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                              : finding.inspector_decision === 'reject'
                                ? 'bg-rose-100 text-rose-800 border border-rose-300'
                                : finding.inspector_decision === 'manual_review'
                                  ? 'bg-amber-100 text-amber-800 border border-amber-300'
                                  : 'bg-slate-200/80 text-slate-600 border border-slate-300'
                            }`}
                        >
                          {finding.inspector_decision
                            ? `Inspector: ${formatInspectorDecision(finding.inspector_decision)}`
                            : 'Pending Inspector Review'}
                        </span>
                        <Button
                          id={`explain-finding-${finding.id}`}
                          data-testid={`explain-finding-${finding.id}`}
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setAssistantInitialFindingId(finding.id)
                            setAssistantInitialTab('explain')
                            setIsAssistantOpen(true)
                          }}
                          className="h-6 px-2 text-xs text-indigo-700 hover:bg-indigo-50 dark:text-indigo-400 gap-1"
                        >
                          <Bot className="h-3 w-3" />
                          <span>Explain</span>
                        </Button>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span>Rule: {finding.rule_check_id}</span>
                      {finding.panel_type && (
                        <span className="inline-flex items-center rounded-full bg-slate-200/90 text-slate-700 border border-slate-300 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider" data-testid={`finding-panel-${finding.rule_check_id}`}>
                          {finding.panel_type} Panel Evidence
                        </span>
                      )}
                      {finding.has_conflict && (
                        <span className="inline-flex items-center rounded-full bg-amber-100 text-amber-800 border border-amber-300 px-2 py-0.5 text-[10px] font-bold" data-testid={`finding-conflict-badge-${finding.rule_check_id}`}>
                          ⚠ Conflict Across Panels
                        </span>
                      )}
                    </div>

                    <div className="grid gap-2 text-xs text-slate-700 sm:grid-cols-2">
                      <div className="rounded-lg border border-slate-200/80 bg-white p-2.5">
                        <span className="font-semibold block text-[11px] uppercase tracking-wider text-slate-500">What</span>
                        <p className="mt-0.5 text-slate-800">{finding.what || finding.description}</p>
                      </div>
                      <div className="rounded-lg border border-slate-200/80 bg-white p-2.5">
                        <span className="font-semibold block text-[11px] uppercase tracking-wider text-slate-500">Why (Legal Basis)</span>
                        <p className="mt-0.5 text-slate-800">{finding.why || (finding.legal_citation ? `${finding.legal_citation}` : 'Statutory requirement under Legal Metrology Rules.')}</p>
                      </div>
                    </div>

                    <div className="grid gap-2 text-xs text-slate-700 sm:grid-cols-2">
                      <div className="rounded-lg border border-slate-200/80 bg-white p-2.5">
                        <span className="font-semibold block text-[11px] uppercase tracking-wider text-slate-500">Detected Value</span>
                        <p className="mt-0.5 font-mono text-slate-800">{finding.detected_value || 'None detected'}</p>
                      </div>
                      <div className="rounded-lg border border-slate-200/80 bg-white p-2.5">
                        <span className="font-semibold block text-[11px] uppercase tracking-wider text-slate-500">Expected Condition</span>
                        <p className="mt-0.5 text-slate-800">{finding.expected_condition || 'Statutory declaration required'}</p>
                      </div>
                    </div>

                    {(finding.source_image ||
                      finding.evidence_snippet ||
                      finding.evidence_location ||
                      finding.ocr_confidence != null ||
                      finding.storage_path ||
                      finding.image_id) && (
                        <VisualEvidenceViewer
                          finding={finding}
                          imageUrl={resolveFindingImageUrl(finding)}
                        />
                      )}

                    <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-200/80 text-xs">
                      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                        Inspector Decision:
                        {finding.reviewer_name && (
                          <span className="normal-case font-normal text-slate-400 ml-1">
                            (by {finding.reviewer_name})
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5" data-testid={`finding-actions-${finding.rule_check_id}`}>
                        <button
                          type="button"
                          aria-label={`Verify ${finding.rule_check_id}`}
                          onClick={() => void submitFindingDecision(finding.id, 'confirm')}
                          disabled={reviewing}
                          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${finding.inspector_decision === 'confirm'
                              ? 'bg-emerald-600 text-white font-semibold'
                              : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                            }`}
                        >
                          Confirm
                        </button>
                        <button
                          type="button"
                          aria-label={`Flag ${finding.rule_check_id}`}
                          onClick={() => void submitFindingDecision(finding.id, 'reject')}
                          disabled={reviewing}
                          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${finding.inspector_decision === 'reject'
                              ? 'bg-rose-600 text-white font-semibold'
                              : 'bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200'
                            }`}
                        >
                          Reject
                        </button>
                        <button
                          type="button"
                          aria-label={`Escalate ${finding.rule_check_id}`}
                          onClick={() => void submitFindingDecision(finding.id, 'manual_review')}
                          disabled={reviewing}
                          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${finding.inspector_decision === 'manual_review'
                              ? 'bg-amber-600 text-white font-semibold'
                              : 'bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200'
                            }`}
                        >
                          Manual Review
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Inspection metadata</CardTitle>
              <CardDescription>Review the package identifier and state of the current inspection.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500">Barcode / QR</div>
                <div className="mt-2 font-semibold text-slate-900">{inspection?.barcode_or_qr ?? 'Not provided'}</div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500">Inspection notes</div>
                <div className="mt-2 whitespace-pre-wrap">{inspection?.notes ?? 'No notes recorded.'}</div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Inspector review</CardTitle>
              <CardDescription>Confirm, reject, or escalate findings before finalization.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {findings.length > 0 && (
                <div className="rounded-lg border border-slate-200 bg-slate-100/60 p-2.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[11px] uppercase tracking-wider text-slate-500">Review Progress</span>
                    <span className="font-mono text-slate-700 font-semibold" data-testid="review-progress">
                      {reviewedCount} / {findings.length} Reviewed
                    </span>
                  </div>
                  <div className="mt-1.5 h-1.5 w-full rounded-full bg-slate-200 overflow-hidden">
                    <div
                      className="h-full bg-indigo-600 transition-all duration-300"
                      style={{ width: `${findings.length > 0 ? (reviewedCount / findings.length) * 100 : 0}%` }}
                    />
                  </div>
                </div>
              )}

              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 pt-1">
                Batch Actions:
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="default" onClick={() => void submitDecision('confirm')} disabled={reviewing || !analysis}>Confirm</Button>
                <Button variant="secondary" onClick={() => void submitDecision('reject')} disabled={reviewing || !analysis}>Reject</Button>
                <Button variant="outline" onClick={() => void submitDecision('manual_review')} disabled={reviewing || !analysis}>Manual Review</Button>
              </div>

              <div className="pt-2">
                <Button
                  onClick={() => void finalizeInspection()}
                  disabled={finalizing || !analysis || (findings.length > 0 && !allReviewed) || hasManualReview}
                  className="w-full"
                >
                  {finalizing ? 'Finalizing...' : 'Finalize inspection'}
                </Button>
                {findings.length > 0 && !allReviewed && (
                  <p className="mt-1.5 text-center text-[11px] text-amber-600">
                    All statutory findings must be reviewed before finalization.
                  </p>
                )}
                {hasManualReview && (
                  <p className="mt-1.5 text-center text-[11px] text-amber-600">
                    Resolve findings marked for manual review before finalization.
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          {inspection?.status === 'COMPLETED' && (
            <Card data-testid="inspection-report-card">
              <CardHeader>
                <CardTitle>Inspection report</CardTitle>
                <CardDescription>Formal evidence-backed statutory audit documentation.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-3 text-xs text-emerald-800">
                  <div className="font-semibold text-emerald-950">Inspection Finalized & Verified</div>
                  <div className="mt-1 text-emerald-800">
                    The inspection audit is complete. A formal PDF report including all findings, citations, evidence annotations, and inspector decisions is ready for download.
                  </div>
                </div>
                <a
                  href={`${API_BASE}/api/v1/inspections/${inspectionId}/report`}
                  download={`praman_inspection_report_${inspection?.inspection_number ?? 'record'}.pdf`}
                  className="flex items-center justify-center w-full rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600"
                  data-testid="download-report-button"
                >
                  Download inspection report (PDF)
                </a>
              </CardContent>
            </Card>
          )}

          {inspection?.status === 'COMPLETED' && (
            <Card data-testid="statutory-notice-action-card" className="border-indigo-100 shadow-sm">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <FileText className="w-4 h-4 text-indigo-600" />
                    Statutory Notice & Memo
                  </CardTitle>
                  {notice && (
                    <span
                      data-testid="notice-status-badge"
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${notice.status === 'ISSUED_BY_OFFICER'
                          ? 'bg-emerald-100 text-emerald-800'
                          : notice.status === 'REVIEWED'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                    >
                      {notice.status === 'ISSUED_BY_OFFICER'
                        ? 'ISSUED BY OFFICER'
                        : notice.status === 'REVIEWED'
                          ? 'REVIEWED'
                          : 'DRAFT'}
                    </span>
                  )}
                </div>
                <CardDescription className="text-xs">
                  Evidence-backed statutory notice drafting with mandatory human officer review.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 pt-0">
                {noticeMessage && (
                  <div className="rounded-lg border border-indigo-200 bg-indigo-50/70 p-2.5 text-xs text-indigo-900">
                    {noticeMessage}
                  </div>
                )}

                {!notice ? (
                  findings.filter((f) => f.inspector_decision !== 'reject').length === 0 ? (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                      Inspection completed with no confirmed violations. A statutory notice / inspection memo is not required.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="text-xs text-slate-600">
                        Confirmed statutory violations are present on this package. Prepare an evidence-backed statutory notice draft for authorized officer review.
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-slate-700">Addressee Legal Role</label>
                        <select
                          data-testid="recipient-role-select"
                          value={recipientRole}
                          onChange={(e) => setRecipientRole(e.target.value)}
                          className="w-full rounded border border-slate-300 p-1.5 text-xs bg-white text-slate-900"
                        >
                          <option value="MANUFACTURER">MANUFACTURER (LM Act Sec 36(1))</option>
                          <option value="PACKER">PACKER (LM Act Sec 36(1))</option>
                          <option value="IMPORTER">IMPORTER (LM Act Sec 36(1))</option>
                          <option value="WHOLESALER">WHOLESALER (LM Act Sec 36(1))</option>
                          <option value="RETAILER">RETAILER (LM Act Sec 36(1))</option>
                        </select>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-slate-700">Addressee Entity / Company Name</label>
                        <input
                          type="text"
                          data-testid="recipient-name-input"
                          value={recipientName}
                          placeholder="e.g. Acme Consumer Products Pvt Ltd"
                          onChange={(e) => setRecipientName(e.target.value)}
                          className="w-full rounded border border-slate-300 p-1.5 text-xs bg-white text-slate-900"
                        />
                      </div>
                      <Button
                        size="sm"
                        onClick={() => void handleDraftNotice()}
                        disabled={noticeActionLoading}
                        data-testid="draft-notice-button"
                        className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium"
                      >
                        {noticeActionLoading ? 'Drafting Notice...' : 'Draft Statutory Notice / Inspection Memo'}
                      </Button>
                    </div>
                  )
                ) : (
                  <div className="space-y-3">
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500 font-medium">Notice Reference:</span>
                        <span data-testid="notice-reference" className="font-mono font-bold text-slate-800">
                          {notice.notice_reference}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500 font-medium">Addressee:</span>
                        <span className="font-medium text-slate-800">
                          {notice.recipient_name} ({notice.recipient_role})
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500 font-medium">Statutory Charges:</span>
                        <span className="font-semibold text-slate-800">
                          {notice.statutory_charges.length} proposed charges
                        </span>
                      </div>
                    </div>

                    {notice.statutory_charges.some((c) => c.requires_manual_review) && (
                      <div
                        data-testid="notice-manual-review-alert"
                        className="rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-xs text-amber-900 flex items-start gap-2"
                      >
                        <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                        <div>
                          <span className="font-semibold">Statutory Review Alert:</span> One or more charges require manual legal review prior to officer issuance.
                        </div>
                      </div>
                    )}

                    <div className="flex flex-col gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setNoticeExpanded(!noticeExpanded)}
                        data-testid="toggle-notice-workspace"
                        className="w-full text-xs justify-between"
                      >
                        <span>{noticeExpanded ? 'Hide Notice Workspace' : 'Open Notice Drafting Workspace'}</span>
                        {noticeExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </Button>

                      <a
                        href={`${API_BASE}/api/v1/notices/${notice.id}/pdf`}
                        download={`notice_${notice.notice_reference.replace(/\//g, '_')}.pdf`}
                        data-testid="download-notice-pdf-button"
                        className="flex items-center justify-center gap-1.5 w-full rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
                      >
                        <Download className="w-3.5 h-3.5" />
                        {notice.status === 'ISSUED_BY_OFFICER'
                          ? 'Download Formal Notice (PDF)'
                          : 'Download Draft PDF (Watermarked)'}
                      </a>
                    </div>

                    {noticeExpanded && (
                      <div
                        data-testid="notice-workspace"
                        className="mt-4 pt-3 border-t border-slate-200 space-y-4"
                      >
                        <div className="font-semibold text-xs uppercase tracking-wider text-slate-700">
                          Notice Details & Drafting Controls
                        </div>

                        {/* Recipient Details */}
                        <div className="space-y-2 rounded-lg border border-slate-200 p-3 bg-slate-50/50">
                          <div className="text-xs font-semibold text-slate-800">Addressee Information</div>
                          <div className="grid grid-cols-1 gap-2">
                            <div>
                              <label className="text-[11px] font-medium text-slate-600">Legal Role</label>
                              <select
                                data-testid="recipient-role-select-workspace"
                                value={recipientRole}
                                disabled={notice.is_immutable}
                                onChange={(e) => setRecipientRole(e.target.value)}
                                className="mt-1 w-full rounded border border-slate-300 p-1.5 text-xs bg-white text-slate-900 disabled:bg-slate-100"
                              >
                                <option value="MANUFACTURER">MANUFACTURER</option>
                                <option value="PACKER">PACKER</option>
                                <option value="IMPORTER">IMPORTER</option>
                                <option value="WHOLESALER">WHOLESALER</option>
                                <option value="RETAILER">RETAILER</option>
                              </select>
                            </div>
                            <div>
                              <label className="text-[11px] font-medium text-slate-600">Entity Name</label>
                              <input
                                type="text"
                                data-testid="recipient-name-workspace-input"
                                value={recipientName}
                                disabled={notice.is_immutable}
                                onChange={(e) => setRecipientName(e.target.value)}
                                className="mt-1 w-full rounded border border-slate-300 p-1.5 text-xs bg-white text-slate-900 disabled:bg-slate-100"
                              />
                            </div>
                            <div>
                              <label className="text-[11px] font-medium text-slate-600">Registered Address</label>
                              <textarea
                                data-testid="recipient-address-input"
                                rows={2}
                                value={recipientAddress}
                                disabled={notice.is_immutable}
                                onChange={(e) => setRecipientAddress(e.target.value)}
                                placeholder="Registered / physical address of addressee"
                                className="mt-1 w-full rounded border border-slate-300 p-1.5 text-xs bg-white text-slate-900 disabled:bg-slate-100"
                              />
                            </div>
                            <div>
                              <label className="text-[11px] font-medium text-slate-600">Email Address (Optional)</label>
                              <input
                                type="email"
                                data-testid="recipient-email-input"
                                value={recipientEmail}
                                disabled={notice.is_immutable}
                                onChange={(e) => setRecipientEmail(e.target.value)}
                                placeholder="compliance@example.com"
                                className="mt-1 w-full rounded border border-slate-300 p-1.5 text-xs bg-white text-slate-900 disabled:bg-slate-100"
                              />
                            </div>
                          </div>
                        </div>

                        {/* Procedural Response Timeline */}
                        <div className="space-y-1.5 rounded-lg border border-slate-200 p-3 bg-slate-50/50">
                          <label className="text-xs font-semibold text-slate-800">
                            Procedural Response Period (Days)
                          </label>
                          <input
                            type="number"
                            min={1}
                            max={90}
                            data-testid="response-period-input"
                            value={responsePeriodDays}
                            disabled={notice.is_immutable}
                            onChange={(e) => setResponsePeriodDays(Number(e.target.value))}
                            className="w-full rounded border border-slate-300 p-1.5 text-xs bg-white text-slate-900 disabled:bg-slate-100"
                          />
                          <p
                            data-testid="response-period-note"
                            className="text-[11px] text-slate-500 italic mt-1 leading-relaxed"
                          >
                            *Note: Configured procedural term for draft administrative convenience (Default: 15 days). Officer must verify against applicable statutory rules. Not a legally mandated universal timeframe.*
                          </p>
                        </div>

                        {/* Compounding Option Clause Toggle */}
                        <div className="space-y-1 rounded-lg border border-slate-200 p-3 bg-slate-50/50">
                          <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-slate-800">
                            <input
                              type="checkbox"
                              data-testid="enable-compounding-toggle"
                              checked={compoundingAvailable}
                              disabled={notice.is_immutable}
                              onChange={(e) => setCompoundingAvailable(e.target.checked)}
                              className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                            />
                            <span>Include Section 48 Compounding Option Clause</span>
                          </label>
                          <p className="text-[11px] text-slate-500 ml-5">
                            Allows compounding of offences if this is the first offence under the Act, subject to officer determination.
                          </p>
                        </div>

                        {/* Statutory Charges Breakdown */}
                        <div className="space-y-2">
                          <div className="text-xs font-semibold text-slate-800 flex items-center justify-between">
                            <span>Statutory Charges & Provisions</span>
                            <span className="text-[11px] font-normal text-slate-500">
                              {notice.statutory_charges.length} charges
                            </span>
                          </div>
                          <div data-testid="statutory-charges-list" className="space-y-2 max-h-64 overflow-y-auto pr-1">
                            {notice.statutory_charges.map((charge, idx) => (
                              <div
                                key={idx}
                                className={`rounded-lg border p-2.5 text-xs space-y-1 ${charge.requires_manual_review
                                    ? 'border-amber-300 bg-amber-50/60'
                                    : 'border-slate-200 bg-white'
                                  }`}
                              >
                                <div className="flex items-center justify-between font-semibold">
                                  <span className="text-slate-900">{charge.rule_check_id}</span>
                                  {charge.requires_manual_review && (
                                    <span
                                      data-testid="charge-manual-review-badge"
                                      className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold bg-amber-200 text-amber-900"
                                    >
                                      MANUAL REVIEW
                                    </span>
                                  )}
                                </div>
                                <div className="text-[11px] text-slate-600">
                                  <span className="font-semibold text-slate-700">Legal Basis:</span> {charge.legal_basis}
                                </div>
                                <div className="text-[11px] text-slate-600">
                                  <span className="font-semibold text-slate-700">Liability:</span> {charge.statutory_citation}
                                </div>
                                <div className="text-[11px] text-slate-600">
                                  <span className="font-semibold text-slate-700">Factual Finding:</span> {charge.factual_basis}
                                </div>
                                {charge.requires_manual_review && charge.manual_review_reason && (
                                  <div className="text-[11px] font-medium text-amber-800 mt-1">
                                    ⚠️ {charge.manual_review_reason}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Officer Workflow Actions */}
                        {notice.status === 'DRAFT' && (
                          <div className="space-y-2 pt-2 border-t border-slate-200">
                            <div>
                              <label className="text-[11px] font-medium text-slate-600">Officer Review Notes</label>
                              <textarea
                                data-testid="officer-notes-input"
                                rows={2}
                                value={officerReviewNotes}
                                onChange={(e) => setOfficerReviewNotes(e.target.value)}
                                placeholder="Enter inspection audit notes or legal considerations..."
                                className="mt-1 w-full rounded border border-slate-300 p-1.5 text-xs bg-white text-slate-900"
                              />
                            </div>
                            <div className="flex gap-2">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => void handleSaveNotice()}
                                disabled={noticeActionLoading}
                                data-testid="save-notice-draft-button"
                                className="flex-1 text-xs"
                              >
                                {noticeActionLoading ? 'Saving...' : 'Save Draft'}
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => void handleReviewNotice()}
                                disabled={noticeActionLoading}
                                data-testid="mark-notice-reviewed-button"
                                className="flex-1 text-xs bg-blue-600 hover:bg-blue-700 text-white"
                              >
                                {noticeActionLoading ? 'Reviewing...' : 'Mark as Reviewed'}
                              </Button>
                            </div>
                          </div>
                        )}

                        {notice.status === 'REVIEWED' && (
                          <div className="space-y-3 pt-2 border-t border-slate-200">
                            <div className="rounded-md border border-blue-200 bg-blue-50/60 p-2 text-xs text-blue-900 font-medium">
                              Draft has been reviewed. Issuance is authoritatively bound to the authenticated issuing officer.
                            </div>
                            <div className="grid grid-cols-1 gap-2">
                              <div>
                                <label className="text-[11px] font-medium text-slate-600">Authenticated Issuing Officer</label>
                                <div
                                  data-testid="issuing-officer-name-display"
                                  className="mt-1 w-full rounded border border-slate-200 bg-slate-50 p-2 text-xs font-semibold text-slate-900"
                                >
                                  {user?.full_name || 'Authenticated Officer'}
                                </div>
                              </div>
                              <div className="grid grid-cols-2 gap-2">
                                <div>
                                  <label className="text-[11px] font-medium text-slate-600">Designation</label>
                                  <div
                                    data-testid="issuing-officer-designation-display"
                                    className="mt-1 w-full rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-800"
                                  >
                                    {user?.designation || 'Legal Metrology Officer'}
                                  </div>
                                </div>
                                <div>
                                  <label className="text-[11px] font-medium text-slate-600">Jurisdiction / Office</label>
                                  <div
                                    data-testid="issuing-officer-jurisdiction-display"
                                    className="mt-1 w-full rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-800"
                                  >
                                    {user?.jurisdiction_office || 'Department of Legal Metrology'}
                                  </div>
                                </div>
                              </div>
                            </div>
                            <label className="flex items-start gap-2 cursor-pointer text-xs text-slate-800 pt-1">
                              <input
                                type="checkbox"
                                data-testid="confirm-issuance-checkbox"
                                checked={confirmIssuance}
                                onChange={(e) => setConfirmIssuance(e.target.checked)}
                                className="mt-0.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                              />
                              <span className="leading-snug">
                                I confirm that I have verified the factual findings, applicable legal provisions, and addressee liability. Issuing this notice makes it permanently immutable under my authenticated officer credentials.
                              </span>
                            </label>
                            <Button
                              size="sm"
                              onClick={() => void handleIssueNotice()}
                              disabled={noticeActionLoading || !confirmIssuance}
                              data-testid="issue-notice-button"
                              className="w-full text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
                            >
                              {noticeActionLoading ? 'Issuing Notice...' : 'Issue Notice & Lock Record'}
                            </Button>
                          </div>
                        )}

                        {notice.status === 'ISSUED_BY_OFFICER' && (
                          <div
                            data-testid="notice-immutable-banner"
                            className="rounded-lg border border-slate-300 bg-slate-100 p-3 text-xs text-slate-700 flex items-start gap-2.5"
                          >
                            <Lock className="w-4 h-4 text-slate-600 mt-0.5 shrink-0" />
                            <div>
                              <div className="font-semibold text-slate-900">Notice Formally Issued & Locked</div>
                              <div className="mt-0.5 text-slate-600">
                                Issued by {notice.issuing_officer_name || 'Authorized Officer'} ({notice.issuing_officer_designation || 'Inspector'}) on {new Date(notice.issued_at || notice.updated_at).toLocaleDateString()}.
                                This statutory record is permanently immutable and cannot be modified.
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <PramanAssistantDrawer
        isOpen={isAssistantOpen}
        onClose={() => setIsAssistantOpen(false)}
        inspectionId={inspectionId ?? ''}
        findings={findings.map((f) => ({ id: f.id, rule_check_id: f.rule_check_id, title: f.title }))}
        initialFindingId={assistantInitialFindingId}
        initialTab={assistantInitialTab}
      />
    </div>
  )
}
