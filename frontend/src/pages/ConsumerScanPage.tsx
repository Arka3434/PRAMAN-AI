import { useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  Camera,
  CheckCircle2,
  Eye,
  FileCheck2,
  FileSearch,
  HelpCircle,
  Info,
  Package,
  RotateCcw,
  Search,
  ShieldCheck,
  UploadCloud,
} from 'lucide-react'

import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { PageHeader } from '../components/ui/page-header'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

interface ConsumerDeclarationItem {
  field_key: string
  field_label: string
  status: 'Detected' | 'Not detected in this image' | 'Image quality insufficient' | 'Not applicable / unknown'
  detected_value: string | null
  description: string
}

interface ConsumerQualityInfo {
  quality_verdict: 'ACCEPTABLE' | 'WARNING_DEGRADED' | 'UNREADABLE'
  quality_notes: string
  is_sufficient_for_scan: boolean
}

interface ConsumerScanResponse {
  scan_id: string
  image_name: string | null
  quality: ConsumerQualityInfo
  declarations: ConsumerDeclarationItem[]
  detected_commodity_name: string | null
  consumer_notice: string
}

interface ConsumerProductSummary {
  id: string
  name: string
  brand: string | null
  category: string | null
  manufacturer: string | null
  description: string | null
}

interface ConsumerProductDetail extends ConsumerProductSummary {
  declarations: ConsumerDeclarationItem[]
  consumer_notice: string
}

export function ConsumerScanPage() {
  const [activeTab, setActiveTab] = useState<'scan' | 'catalog'>('scan')

  // Scan state
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState<ConsumerScanResponse | null>(null)
  const [scanError, setScanError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Catalog search state
  const [searchTerm, setSearchTerm] = useState('')
  const [catalogProducts, setCatalogProducts] = useState<ConsumerProductSummary[]>([])
  const [loadingCatalog, setLoadingCatalog] = useState(false)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [selectedProductDetail, setSelectedProductDetail] = useState<ConsumerProductDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Fetch catalog products
  const fetchCatalogProducts = async () => {
    setLoadingCatalog(true)
    setCatalogError(null)
    try {
      const params = new URLSearchParams()
      if (searchTerm.trim()) params.append('search', searchTerm.trim())

      const res = await fetch(`${API_BASE}/api/v1/consumer/products?${params.toString()}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load catalog products`)
      const data = (await res.json()) as ConsumerProductSummary[]
      setCatalogProducts(data)
    } catch (err) {
      setCatalogError(err instanceof Error ? err.message : 'Error fetching products')
    } finally {
      setLoadingCatalog(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'catalog') {
      const timer = setTimeout(() => {
        void fetchCatalogProducts()
      }, 250)
      return () => clearTimeout(timer)
    }
  }, [searchTerm, activeTab])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setSelectedFile(file)
    setScanResult(null)
    setScanError(null)

    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
  }

  const handleRunScan = async () => {
    if (!selectedFile) return
    setScanning(true)
    setScanError(null)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      const res = await fetch(`${API_BASE}/api/v1/consumer/scan`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || `Scan failed with status ${res.status}`)
      }

      const data = (await res.json()) as ConsumerScanResponse
      setScanResult(data)
    } catch (err) {
      setScanError(err instanceof Error ? err.message : 'Network error during scan')
    } finally {
      setScanning(false)
    }
  }

  const handleResetScan = () => {
    setSelectedFile(null)
    setPreviewUrl(null)
    setScanResult(null)
    setScanError(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleSelectCatalogProduct = async (productId: string) => {
    setLoadingDetail(true)
    try {
      const res = await fetch(`${API_BASE}/api/v1/consumer/products/${productId}`)
      if (!res.ok) throw new Error(`Failed to load product detail: HTTP ${res.status}`)
      const data = (await res.json()) as ConsumerProductDetail
      setSelectedProductDetail(data)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Error loading product details')
    } finally {
      setLoadingDetail(false)
    }
  }

  const getStatusBadge = (status: ConsumerDeclarationItem['status']) => {
    switch (status) {
      case 'Detected':
        return (
          <Badge variant="pass" className="gap-1">
            <CheckCircle2 className="h-3 w-3" />
            Detected
          </Badge>
        )
      case 'Not detected in this image':
        return (
          <Badge variant="default" className="gap-1 bg-slate-100 text-slate-700">
            <Info className="h-3 w-3 text-slate-400" />
            Not detected in this image
          </Badge>
        )
      case 'Image quality insufficient':
        return (
          <Badge variant="warning" className="gap-1">
            <AlertCircle className="h-3 w-3" />
            Image quality insufficient
          </Badge>
        )
      case 'Not applicable / unknown':
      default:
        return (
          <Badge variant="neutral" className="gap-1">
            <HelpCircle className="h-3 w-3" />
            Not applicable / unknown
          </Badge>
        )
    }
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      <PageHeader
        title="Consumer Packaging Transparency"
        description="Public informational tool to verify mandatory statutory packaging declarations under Legal Metrology Rules, 2011."
      />

      {/* Prominent Statutory Purpose Banner */}
      <div className="rounded-xl border border-sky-200 bg-sky-50/70 p-4 text-xs text-sky-900 shadow-sm flex items-start gap-3">
        <ShieldCheck className="h-5 w-5 text-sky-700 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-sky-950 text-sm">Consumer Transparency & Packaging Verification</span>
          <p className="text-slate-700 leading-relaxed">
            Every pre-packaged retail commodity in India is required by law to clearly display essential consumer
            declarations: Maximum Retail Price (MRP), Net Quantity, Packaging Date, Manufacturer Identity, and Customer
            Care contact. Use this portal to scan packaging photos or browse registered commodity packaging information.
          </p>
        </div>
      </div>

      {/* Senior-Friendly / High-Contrast Mode Navigation */}
      <div className="flex border-b border-slate-200 bg-white rounded-t-xl p-1 shadow-sm">
        <button
          type="button"
          onClick={() => setActiveTab('scan')}
          className={`flex-1 py-3 px-4 text-center font-semibold text-sm rounded-lg transition-all flex items-center justify-center gap-2 ${
            activeTab === 'scan'
              ? 'bg-slate-900 text-white shadow-md'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
          data-testid="tab-scan-photo"
        >
          <Camera className="h-4 w-4" />
          Scan Package Photo
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('catalog')}
          className={`flex-1 py-3 px-4 text-center font-semibold text-sm rounded-lg transition-all flex items-center justify-center gap-2 ${
            activeTab === 'catalog'
              ? 'bg-slate-900 text-white shadow-md'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
          data-testid="tab-search-catalog"
        >
          <FileSearch className="h-4 w-4" />
          Search Product Catalog
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: SCAN PACKAGE PHOTO                                                 */}
      {/* ========================================================================= */}
      {activeTab === 'scan' && (
        <div className="space-y-6">
          <Card className="border-slate-200 bg-white shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
                <UploadCloud className="h-5 w-5 text-indigo-600" />
                Upload or Capture Package Image
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Upload a clear photo of the product package or label panel showing printed text.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleFileChange}
                className="hidden"
                id="consumer-package-file"
                data-testid="consumer-file-input"
              />

              {!previewUrl ? (
                <label
                  htmlFor="consumer-package-file"
                  className="flex flex-col items-center justify-center p-8 border-2 border-dashed border-slate-300 rounded-xl bg-slate-50 hover:bg-indigo-50/40 hover:border-indigo-300 cursor-pointer transition-colors text-center"
                >
                  <Camera className="h-10 w-10 text-slate-400 mb-2" />
                  <span className="font-semibold text-sm text-slate-800">
                    Click to Choose or Take a Package Photo
                  </span>
                  <span className="text-xs text-slate-500 mt-1">Supports JPG, PNG, WebP</span>
                </label>
              ) : (
                <div className="space-y-4">
                  <div className="relative rounded-xl border border-slate-200 overflow-hidden bg-slate-100 max-h-80 flex items-center justify-center">
                    <img
                      src={previewUrl}
                      alt="Selected package"
                      className="max-h-80 w-auto object-contain rounded-lg"
                    />
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                    <div className="text-xs text-slate-600 truncate max-w-sm">
                      Selected: <span className="font-semibold text-slate-900">{selectedFile?.name}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleResetScan}
                        className="text-xs"
                        disabled={scanning}
                      >
                        <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                        Choose Another
                      </Button>

                      <Button
                        size="sm"
                        onClick={() => void handleRunScan()}
                        disabled={scanning}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs px-4"
                        data-testid="consumer-scan-button"
                      >
                        {scanning ? 'Reading Declarations...' : 'Scan Package Declarations'}
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {scanError && (
                <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg">
                  {scanError}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Scan Results Display */}
          {scanResult && (
            <div className="space-y-6" data-testid="consumer-scan-results">
              {/* Informational Guidance & Quality Banner */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-2 rounded-xl border border-amber-200 bg-amber-50/70 p-4 text-xs text-amber-900 space-y-1">
                  <div className="font-bold flex items-center gap-1.5 text-amber-950 text-sm">
                    <Info className="h-4 w-4 text-amber-600" />
                    Informational Transparency Results
                  </div>
                  <p className="text-slate-700 leading-relaxed">
                    {scanResult.consumer_notice}
                  </p>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-4 text-xs space-y-2 shadow-sm">
                  <div className="font-semibold text-slate-700 uppercase tracking-wider text-[10px]">
                    Image Diagnostic Quality
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        scanResult.quality.quality_verdict === 'ACCEPTABLE'
                          ? 'bg-emerald-100 text-emerald-800'
                          : scanResult.quality.quality_verdict === 'WARNING_DEGRADED'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-rose-100 text-rose-800'
                      }`}
                    >
                      {scanResult.quality.quality_verdict === 'ACCEPTABLE'
                        ? '✓ Clear Photo'
                        : scanResult.quality.quality_verdict === 'WARNING_DEGRADED'
                        ? '⚠ Minor Glare/Blur'
                        : '✖ Blurry / Unreadable'}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500 leading-tight">
                    {scanResult.quality.quality_notes}
                  </p>
                </div>
              </div>

              {/* Declarations Checklist Cards */}
              <Card className="border-slate-200 bg-white shadow-sm">
                <CardHeader className="pb-3 border-b border-slate-100">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
                        <FileCheck2 className="h-5 w-5 text-emerald-600" />
                        Mandatory Packaging Declarations Checklist
                      </CardTitle>
                      <CardDescription className="text-xs text-slate-500">
                        Evaluated under Rule 6(1) of the Legal Metrology (Packaged Commodities) Rules, 2011.
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="p-0 divide-y divide-slate-100">
                  {scanResult.declarations.map((item) => (
                    <div
                      key={item.field_key}
                      className="p-4 hover:bg-slate-50/50 transition-colors flex flex-col md:flex-row md:items-center md:justify-between gap-3"
                      data-testid={`declaration-item-${item.field_key}`}
                    >
                      <div className="space-y-1 max-w-xl">
                        <div className="font-semibold text-sm text-slate-900 flex items-center gap-2">
                          <span>{item.field_label}</span>
                        </div>
                        <p className="text-xs text-slate-500 leading-relaxed">{item.description}</p>
                        {item.detected_value && (
                          <div className="mt-1 inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-2 py-1 text-xs font-mono font-medium text-slate-800">
                            <span className="text-[10px] uppercase text-slate-500 font-sans">Read Value:</span>
                            <span>{item.detected_value}</span>
                          </div>
                        )}
                      </div>

                      <div className="shrink-0 flex items-center gap-2">
                        {getStatusBadge(item.status)}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: SEARCH PRODUCT CATALOG                                             */}
      {/* ========================================================================= */}
      {activeTab === 'catalog' && (
        <div className="space-y-6">
          <Card className="border-slate-200 bg-white shadow-sm">
            <CardHeader className="pb-3 border-b border-slate-100">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                  <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <Package className="h-5 w-5 text-indigo-600" />
                    Commodity Packaging Catalog
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Search registered pre-packaged commodities and view known packaging declarations.
                  </CardDescription>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <div className="relative w-72">
                    <Input
                      placeholder="Search product, brand, or packer..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-9 text-xs"
                      data-testid="consumer-catalog-search"
                    />
                    <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                  </div>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-4">
              {catalogError && (
                <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg mb-4">
                  {catalogError}
                </div>
              )}

              {loadingCatalog ? (
                <div className="p-12 text-center text-xs text-slate-500">Loading catalog commodities...</div>
              ) : catalogProducts.length === 0 ? (
                <div className="p-12 text-center" data-testid="empty-consumer-products">
                  <Package className="mx-auto h-8 w-8 text-slate-300" />
                  <div className="mt-2 text-sm font-semibold text-slate-700">No commodities found</div>
                  <div className="mt-1 text-xs text-slate-500">
                    Try searching for another product name or brand.
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="consumer-products-grid">
                  {catalogProducts.map((p) => (
                    <div
                      key={p.id}
                      className="rounded-xl border border-slate-200 bg-white p-4 hover:border-indigo-300 hover:shadow-sm transition-all flex flex-col justify-between"
                      data-testid={`consumer-product-card-${p.id}`}
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-start justify-between gap-2">
                          <span className="font-bold text-sm text-slate-900 leading-snug">{p.name}</span>
                          {p.category && (
                            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600 uppercase shrink-0">
                              {p.category}
                            </span>
                          )}
                        </div>

                        {p.brand && (
                          <div className="text-xs text-indigo-700 font-medium">Brand: {p.brand}</div>
                        )}

                        {p.manufacturer && (
                          <div className="text-xs text-slate-500 truncate" title={p.manufacturer}>
                            Packer/Mfg: {p.manufacturer}
                          </div>
                        )}
                      </div>

                      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                        <span className="text-[11px] text-slate-400">Registered Commodity</span>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={loadingDetail}
                          onClick={() => void handleSelectCatalogProduct(p.id)}
                          className="h-8 text-xs font-semibold text-indigo-700 hover:text-indigo-900"
                          data-testid={`view-declarations-btn-${p.id}`}
                        >
                          <Eye className="mr-1.5 h-3.5 w-3.5" />
                          {loadingDetail ? 'Loading...' : 'View Declarations'}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Product Declarations Modal / Drawer View */}
          {selectedProductDetail && (
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm"
              data-testid="product-detail-modal"
            >
              <div className="relative w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
                <div className="flex items-start justify-between border-b border-slate-100 pb-3">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">{selectedProductDetail.name}</h3>
                    <div className="text-xs text-slate-500 mt-0.5">
                      Brand: <span className="text-indigo-700 font-medium">{selectedProductDetail.brand ?? 'Standard'}</span> • Category: {selectedProductDetail.category ?? 'General Retail'}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedProductDetail(null)}
                    className="text-slate-400 hover:text-slate-700 text-lg font-bold p-1"
                    data-testid="close-detail-modal"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-3">
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                    Known Mandatory Packaging Declarations
                  </div>

                  <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 overflow-hidden">
                    {selectedProductDetail.declarations.map((decl) => (
                      <div key={decl.field_key} className="p-3 text-xs flex items-center justify-between gap-3 bg-white">
                        <div className="space-y-0.5">
                          <span className="font-semibold text-slate-900">{decl.field_label}</span>
                          <p className="text-[11px] text-slate-500">{decl.description}</p>
                          {decl.detected_value && (
                            <div className="font-mono text-slate-800 font-medium text-[11px] mt-0.5">
                              {decl.detected_value}
                            </div>
                          )}
                        </div>
                        <div>{getStatusBadge(decl.status)}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-lg bg-sky-50 border border-sky-100 p-3 text-xs text-sky-800 leading-relaxed">
                  {selectedProductDetail.consumer_notice}
                </div>

                <div className="flex justify-end pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedProductDetail(null)}
                    className="text-xs"
                  >
                    Close Window
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Statutory Public Disclaimer Footer */}
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-center text-xs text-slate-500 space-y-1">
        <div className="font-semibold text-slate-700">PRAMAN AI Public Citizen Transparency Portal</div>
        <p className="max-w-3xl mx-auto leading-relaxed text-[11px]">
          Statutory Notice: This portal provides informational transparency on packaging declarations under the Legal
          Metrology (Packaged Commodities) Rules, 2011. Results are intended for consumer awareness and educational
          verification. This service does not constitute an official Legal Metrology seizure, statutory notice, or
          enforcement order.
        </p>
      </div>
    </div>
  )
}
