import { useEffect, useState } from 'react'
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  FileCheck,
  FileCode,
  HelpCircle,
  Search,
  Shield,
  ShieldCheck,
} from 'lucide-react'

import { Badge } from '../components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { PageHeader } from '../components/ui/page-header'
import { getStoredToken } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type RuleDefinition = {
  rule_id: str
  title: str
  legal_citation: str
  source_document: str
  effective_from: str
  effective_to: str | null
  applicability: str
  exemptions: string[]
  input_fields: string[]
  check_type: str
  expected_condition: str
  severity: str
  executable_status: string
  evidence_requirement: str
  is_currently_effective: boolean
}

type str = string

export type RuleCatalog = {
  catalog_version: string
  catalog_hash: string
  jurisdiction: string
  regulatory_framework: string
  description: string
  last_updated: string
  coverage_notice: string
  total_rules: number
  safe_rules_count: number
  needs_verification_count: number
  rules: RuleDefinition[]
}

export function RulesPage() {
  const [catalog, setCatalog] = useState<RuleCatalog | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'safe' | 'needs_verification'>('all')
  const [expandedRules, setExpandedRules] = useState<Record<string, boolean>>({})
  const [copiedHash, setCopiedHash] = useState(false)

  const fetchCatalog = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (statusFilter === 'safe') {
        params.append('status', 'SAFE')
      } else if (statusFilter === 'needs_verification') {
        params.append('status', 'NEEDS_VERIFICATION')
      }
      if (searchTerm.trim()) {
        params.append('search', searchTerm.trim())
      }

      const token = getStoredToken()
      const res = await fetch(`${API_BASE}/api/v1/rules?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) {
        throw new Error(`Failed to load legal rule catalog: HTTP ${res.status}`)
      }
      const data = (await res.json()) as RuleCatalog
      setCatalog(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error fetching legal rule catalog')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const handler = setTimeout(() => {
      void fetchCatalog()
    }, 200)
    return () => clearTimeout(handler)
  }, [searchTerm, statusFilter])

  const toggleExpand = (ruleId: string) => {
    setExpandedRules((prev) => ({
      ...prev,
      [ruleId]: !prev[ruleId],
    }))
  }

  const toggleAll = () => {
    if (!catalog) return
    const allExpanded = catalog.rules.every((r) => expandedRules[r.rule_id])
    const nextState: Record<string, boolean> = {}
    catalog.rules.forEach((r) => {
      nextState[r.rule_id] = !allExpanded
    })
    setExpandedRules(nextState)
  }

  const copyDigest = (hash: string) => {
    void navigator.clipboard.writeText(hash)
    setCopiedHash(true)
    setTimeout(() => setCopiedHash(false), 2000)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Legal Rule Catalog"
        description="Versioned statutory rules, legal citations, and deterministic check criteria under Chapter II of PCR 2011."
      />

      {/* Catalog Metadata & Cryptographic Integrity Banner */}
      <Card className="border-indigo-100 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white shadow-md">
        <CardContent className="p-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-500/20 px-3 py-0.5 text-xs font-semibold text-indigo-300 border border-indigo-500/30">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {catalog?.regulatory_framework ?? 'Legal Metrology (Packaged Commodities) Rules, 2011'}
                </span>
                <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-mono font-medium text-slate-300">
                  Version {catalog?.catalog_version ?? '1.0.0'}
                </span>
                <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-xs font-medium text-emerald-300 border border-emerald-500/30">
                  Jurisdiction: {catalog?.jurisdiction ?? 'India'}
                </span>
              </div>
              <h2 className="text-xl font-bold tracking-tight text-white">
                Statutory Packaging Compliance Framework
              </h2>
              <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
                {catalog?.description ??
                  'Formal versioned rule catalog for pre-packaged commodities statutory declarations under Chapter II of PCR 2011.'}
              </p>
            </div>

            {/* SHA-256 Digest Box */}
            <div className="rounded-lg bg-slate-800/80 p-3 border border-slate-700/60 md:w-80 shrink-0">
              <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                <span className="font-semibold uppercase tracking-wider flex items-center gap-1">
                  <FileCode className="h-3 w-3" /> Catalog SHA-256 Hash
                </span>
                <button
                  type="button"
                  onClick={() => catalog && copyDigest(catalog.catalog_hash)}
                  className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 text-[10px]"
                  title="Copy SHA-256 Digest"
                >
                  <Copy className="h-3 w-3" />
                  {copiedHash ? 'Copied' : 'Copy'}
                </button>
              </div>
              <div
                className="font-mono text-[11px] text-indigo-200 break-all bg-slate-900/90 p-2 rounded border border-slate-700/80 select-all"
                data-testid="catalog-hash-badge"
              >
                {catalog?.catalog_hash ?? 'Loading digest...'}
              </div>
            </div>
          </div>

          {/* Statutory Scope Disclaimer Notice */}
          <div className="mt-4 rounded-md bg-amber-500/10 p-3 border border-amber-500/20 text-xs text-amber-200/90 flex items-start gap-2.5">
            <HelpCircle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
            <div className="leading-relaxed">
              <span className="font-semibold text-amber-300">Statutory Notice: </span>
              {catalog?.coverage_notice ??
                'This catalog codifies standard statutory declarations for pre-packaged retail commodities under Chapter II of PCR 2011 as an auditing and decision-support tool. It does not replace the statutory inspection powers or judicial discretion vested in Legal Metrology Officers.'}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="border-slate-200 bg-white shadow-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs">Codified Legal Rules</CardDescription>
            <CardTitle className="text-2xl font-bold text-slate-900" data-testid="total-rules-count">
              {catalog?.total_rules ?? 8}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0 text-xs text-slate-500">
            Chapter II mandatory declarations
          </CardContent>
        </Card>

        <Card className="border-emerald-200 bg-emerald-50/40 shadow-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs text-emerald-700">Automated Execution (SAFE)</CardDescription>
            <CardTitle className="text-2xl font-bold text-emerald-800" data-testid="safe-rules-count">
              {catalog?.safe_rules_count ?? 6}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0 text-xs text-emerald-600">
            Deterministic evaluation with OCR evidence
          </CardContent>
        </Card>

        <Card className="border-amber-200 bg-amber-50/40 shadow-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs text-amber-700">Manual Verification Required</CardDescription>
            <CardTitle className="text-2xl font-bold text-amber-800" data-testid="needs-verification-count">
              {catalog?.needs_verification_count ?? 2}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0 text-xs text-amber-600">
            Perishability & Calibrated PDP font height
          </CardContent>
        </Card>
      </div>

      {/* Rules Register & Filter Area */}
      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b border-slate-100 pb-4">
          <div>
            <CardTitle>Statutory Rules Register</CardTitle>
            <CardDescription>
              Inspect legal provisions, applicability scopes, statutory exemptions, and evidence requirements.
            </CardDescription>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Filter Tabs */}
            <div className="flex rounded-lg bg-slate-100 p-1 text-xs">
              <button
                type="button"
                onClick={() => setStatusFilter('all')}
                className={`rounded-md px-3 py-1.5 font-medium transition-all ${
                  statusFilter === 'all'
                    ? 'bg-white text-slate-900 shadow-sm font-semibold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
                data-testid="filter-tab-all"
              >
                All ({catalog?.total_rules ?? 8})
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter('safe')}
                className={`rounded-md px-3 py-1.5 font-medium transition-all ${
                  statusFilter === 'safe'
                    ? 'bg-white text-emerald-800 shadow-sm font-semibold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
                data-testid="filter-tab-safe"
              >
                Automated SAFE ({catalog?.safe_rules_count ?? 6})
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter('needs_verification')}
                className={`rounded-md px-3 py-1.5 font-medium transition-all ${
                  statusFilter === 'needs_verification'
                    ? 'bg-white text-amber-800 shadow-sm font-semibold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
                data-testid="filter-tab-needs-verification"
              >
                Assisted Review ({catalog?.needs_verification_count ?? 2})
              </button>
            </div>

            {/* Search Input */}
            <div className="relative w-64">
              <Input
                placeholder="Search rule ID, title, citation..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 text-xs"
                data-testid="rules-search-input"
              />
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            </div>

            <button
              type="button"
              onClick={toggleAll}
              className="text-xs font-medium text-indigo-700 hover:text-indigo-900 hover:underline px-2 py-1"
            >
              Toggle All
            </button>
          </div>
        </CardHeader>

        <CardContent className="p-4 space-y-4">
          {error && (
            <div className="p-4 text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-md">
              {error}
            </div>
          )}

          {loading ? (
            <div className="p-12 text-center text-sm text-slate-500">Loading statutory rule catalog...</div>
          ) : !catalog || catalog.rules.length === 0 ? (
            <div className="p-12 text-center" data-testid="empty-rules-message">
              <BookOpen className="mx-auto h-8 w-8 text-slate-300" />
              <div className="mt-2 text-sm font-semibold text-slate-700">No legal rules match your criteria</div>
              <div className="mt-1 text-xs text-slate-500">
                Try resetting your search query or switching filter tabs.
              </div>
            </div>
          ) : (
            <div className="space-y-3" data-testid="rules-list">
              {catalog.rules.map((rule) => {
                const isExpanded = !!expandedRules[rule.rule_id]
                return (
                  <div
                    key={rule.rule_id}
                    className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden transition-all hover:border-indigo-200"
                    data-testid={`rule-card-${rule.rule_id}`}
                  >
                    {/* Collapsible Header */}
                    <button
                      type="button"
                      onClick={() => toggleExpand(rule.rule_id)}
                      className="w-full text-left p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between hover:bg-slate-50/60 transition-colors"
                      data-testid={`rule-header-${rule.rule_id}`}
                    >
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                            {rule.rule_id}
                          </span>
                          <span className="font-semibold text-sm text-slate-900">{rule.title}</span>
                        </div>
                        <div className="text-xs text-slate-600 flex items-center gap-1.5">
                          <BookOpen className="h-3.5 w-3.5 text-slate-400" />
                          <span>{rule.legal_citation}</span>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 shrink-0">
                        {rule.executable_status === 'SAFE' ? (
                          <Badge variant="pass" className="text-[11px] gap-1">
                            <Shield className="h-3 w-3" /> SAFE / AUTOMATED
                          </Badge>
                        ) : (
                          <Badge variant="warning" className="text-[11px] gap-1">
                            <AlertCircle className="h-3 w-3" /> MANUAL VERIFICATION
                          </Badge>
                        )}

                        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 uppercase">
                          {rule.severity}
                        </span>

                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 border border-emerald-100">
                          <Clock className="h-3 w-3" /> Effective since {rule.effective_from}
                        </span>

                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4 text-slate-400 ml-1" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-slate-400 ml-1" />
                        )}
                      </div>
                    </button>

                    {/* Detailed Body */}
                    {isExpanded && (
                      <div className="border-t border-slate-100 bg-slate-50/40 p-5 space-y-4 text-xs">
                        {/* Statutory Expected Condition */}
                        <div>
                          <div className="font-semibold text-slate-900 mb-1 flex items-center gap-1.5">
                            <FileCheck className="h-3.5 w-3.5 text-indigo-600" />
                            Statutory Expected Condition
                          </div>
                          <div className="p-3 bg-white rounded border border-slate-200 text-slate-700 leading-relaxed font-sans">
                            {rule.expected_condition}
                          </div>
                        </div>

                        {/* Applicability & Source Document */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="p-3 bg-white rounded border border-slate-200 space-y-1">
                            <div className="font-semibold text-slate-900">Applicability Scope</div>
                            <div className="text-slate-600 leading-relaxed">{rule.applicability}</div>
                          </div>

                          <div className="p-3 bg-white rounded border border-slate-200 space-y-1">
                            <div className="font-semibold text-slate-900">Legal Source Document</div>
                            <div className="text-slate-600 font-mono text-[11px]">{rule.source_document}</div>
                            <div className="text-slate-500 text-[11px] pt-1">
                              Check type: <span className="font-mono text-slate-700">{rule.check_type}</span>
                            </div>
                          </div>
                        </div>

                        {/* Statutory Exemptions */}
                        {rule.exemptions && rule.exemptions.length > 0 && (
                          <div className="p-3 bg-white rounded border border-slate-200 space-y-1.5">
                            <div className="font-semibold text-slate-900">Statutory Exemptions</div>
                            <ul className="list-disc pl-5 space-y-1 text-slate-600">
                              {rule.exemptions.map((ex, idx) => (
                                <li key={idx} className="leading-relaxed">
                                  {ex}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Evidence & Verification Requirement */}
                        <div className="p-3 bg-indigo-50/60 rounded border border-indigo-100 space-y-2">
                          <div className="font-semibold text-indigo-950 flex items-center gap-1.5">
                            <CheckCircle2 className="h-3.5 w-3.5 text-indigo-600" />
                            Evidence & Technical Verification Criteria
                          </div>
                          <div className="text-slate-700 leading-relaxed font-sans">
                            {rule.evidence_requirement}
                          </div>

                          <div className="pt-2 flex flex-wrap items-center gap-2">
                            <span className="text-slate-500 text-[11px]">Required Declaration Fields:</span>
                            {rule.input_fields.map((field) => (
                              <span
                                key={field}
                                className="font-mono text-[11px] bg-white px-2 py-0.5 rounded border border-slate-200 text-slate-700"
                              >
                                {field}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
