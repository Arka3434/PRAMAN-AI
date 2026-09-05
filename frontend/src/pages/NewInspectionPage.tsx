import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Check, PlusCircle, Search } from 'lucide-react'

import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { PageHeader } from '../components/ui/page-header'
import { Select } from '../components/ui/select'
import type { ProductSummary } from './ProductsPage'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

type CaptureSide = 'front' | 'back' | 'left_side' | 'right_side' | 'other'

export function NewInspectionPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const preSelectedProductId = searchParams.get('productId')

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [selectedImageType, setSelectedImageType] = useState<CaptureSide>('front')
  const [barcodeValue, setBarcodeValue] = useState('PRAMAN-123456')
  const [cameraOpen, setCameraOpen] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const [capturedPreview, setCapturedPreview] = useState<string | null>(null)

  // Product Intake State
  const [productMode, setProductMode] = useState<'existing' | 'new'>(
    preSelectedProductId ? 'existing' : 'new'
  )
  const [availableProducts, setAvailableProducts] = useState<ProductSummary[]>([])
  const [selectedProductId, setSelectedProductId] = useState<string>(preSelectedProductId || '')
  const [loadingProducts, setLoadingProducts] = useState(false)

  const [form, setForm] = useState({
    title: 'Packaged goods inspection',
    productName: 'PRAMAN Premium Rice 5kg',
    category: 'Food & Beverages',
    brand: 'PRAMAN',
    manufacturer: 'PRAMAN Foods Ltd',
    notes: 'Field inspection created for package evidence capture and OCR review.',
  })

  useEffect(() => {
    const fetchAvailableProducts = async () => {
      setLoadingProducts(true)
      try {
        const res = await fetch(`${API_BASE}/api/v1/products`)
        if (res.ok) {
          const data = (await res.json()) as ProductSummary[]
          setAvailableProducts(data)
          if (preSelectedProductId) {
            const matched = data.find((p) => p.id === preSelectedProductId)
            if (matched) {
              setProductMode('existing')
              setSelectedProductId(matched.id)
              setForm((prev) => ({
                ...prev,
                productName: matched.name,
                category: matched.category || 'Food & Beverages',
                brand: matched.brand || '',
                manufacturer: matched.manufacturer || '',
              }))
            }
          }
        }
      } catch {
        // Fallback gracefully
      } finally {
        setLoadingProducts(false)
      }
    }

    void fetchAvailableProducts()
  }, [preSelectedProductId])

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop())
      }
    }
  }, [])

  const handleSelectProduct = (productId: string) => {
    setSelectedProductId(productId)
    const product = availableProducts.find((p) => p.id === productId)
    if (product) {
      setForm((prev) => ({
        ...prev,
        productName: product.name,
        category: product.category || 'Food & Beverages',
        brand: product.brand || '',
        manufacturer: product.manufacturer || '',
      }))
    }
  }

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    setCameraOpen(false)
  }

  const openCamera = async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraError('This browser does not support device camera access.')
      return
    }

    try {
      setCameraError('')
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false,
      })
      streamRef.current = stream
      setCameraOpen(true)

      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
    } catch {
      setCameraError('Unable to access the device camera. Use upload or manual barcode entry instead.')
      setCameraOpen(false)
    }
  }

  const captureCameraFrame = () => {
    if (!videoRef.current) {
      return
    }

    const video = videoRef.current
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth || 1200
    canvas.height = video.videoHeight || 900
    const context = canvas.getContext('2d')
    if (!context) {
      return
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob((blob) => {
      if (!blob) {
        return
      }
      const capturedFile = new File([blob], `capture-${Date.now()}.jpg`, { type: 'image/jpeg' })
      setSelectedFiles((current) => [...current, capturedFile])
      setCapturedPreview(URL.createObjectURL(capturedFile))
      stopCamera()
    }, 'image/jpeg', 0.9)
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIsSubmitting(true)
    setErrorMessage('')

    try {
      let finalProductId = selectedProductId

      // If user chose to register a new product or no existing product was selected
      if (productMode === 'new' || !finalProductId) {
        const productResponse = await fetch(`${API_BASE}/api/v1/products`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: form.productName || 'Unnamed product',
            category: form.category,
            brand: form.brand,
            manufacturer: form.manufacturer || 'Registered inspection manufacturer',
            description: 'Packaged commodity registered via field inspection intake.',
          }),
        })

        if (!productResponse.ok) {
          throw new Error('Unable to register the product in master catalog.')
        }

        const product = await productResponse.json()
        finalProductId = product.id
      }

      const inspectionResponse = await fetch(`${API_BASE}/api/v1/inspections`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          inspection_number: `INSP-${Date.now().toString().slice(-6)}`,
          status: 'DRAFT',
          title: form.title || 'Untitled inspection',
          notes: form.notes,
          barcode_or_qr: barcodeValue.trim() || null,
          product_id: finalProductId,
          inspector_id: null,
        }),
      })

      if (!inspectionResponse.ok) {
        const detail = await inspectionResponse.text()
        throw new Error(detail || 'Unable to create the inspection.')
      }

      const inspection = await inspectionResponse.json()

      if (selectedFiles.length > 0) {
        const formData = new FormData()
        formData.append('image_type', selectedImageType)
        selectedFiles.forEach((file) => formData.append('files', file))

        const uploadResponse = await fetch(`${API_BASE}/api/v1/inspections/${inspection.id}/upload-images`, {
          method: 'POST',
          body: formData,
        })

        if (!uploadResponse.ok) {
          const detail = await uploadResponse.text()
          throw new Error(detail || 'Unable to upload the inspection images.')
        }
      }

      navigate(`/inspections/${inspection.id}`)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to create inspection.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const actionCardClass = 'rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg'

  return (
    <div>
      <PageHeader
        title="New Inspection"
        description="Capture package evidence, associate with product identity, and proceed into OCR analysis and review."
      />

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid gap-4 xl:grid-cols-3">
          <button type="button" className={actionCardClass} onClick={openCamera}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-600">Capture</div>
                <div className="mt-2 text-xl font-bold text-slate-900">SCAN PACKAGE</div>
              </div>
              <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-100 to-cyan-100 text-sky-700 shadow-inner">
                <div className="absolute inset-2 rounded-xl border-2 border-sky-500/80" />
                <div className="absolute left-3 top-3 h-3 w-3 rounded-full border-2 border-sky-600" />
                <div className="absolute right-3 top-3 h-3 w-3 rounded-full border-2 border-sky-600" />
                <div className="absolute bottom-3 left-3 h-3 w-3 rounded-full border-2 border-sky-600" />
                <div className="absolute bottom-3 right-3 h-3 w-3 rounded-full border-2 border-sky-600" />
                <div className="h-7 w-9 rounded-xl border-2 border-sky-600 bg-sky-50" />
                <div className="absolute h-3 w-3 rounded-full bg-sky-600" />
              </div>
            </div>
          </button>

          <button type="button" className={actionCardClass}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-600">Library</div>
                <div className="mt-2 text-xl font-bold text-slate-900">UPLOAD IMAGES</div>
              </div>
              <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-100 to-purple-100 text-violet-700 shadow-inner">
                <div className="absolute inset-3 rounded-2xl border-2 border-violet-500/80" />
                <div className="absolute left-5 top-5 h-5 w-8 rounded-t-xl border-2 border-violet-600 bg-white/60" />
                <div className="absolute bottom-4 left-4 h-6 w-10 rounded-xl border-2 border-violet-600 bg-violet-100" />
                <div className="absolute bottom-2 right-3 h-5 w-5 rounded-full border-2 border-violet-600 bg-violet-200" />
                <div className="absolute -bottom-0.5 right-3 h-3.5 w-3.5 rounded-full bg-violet-600" />
              </div>
            </div>
          </button>

          <button type="button" className={actionCardClass} onClick={() => setCameraOpen((current) => !current)}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-600">Lookup</div>
                <div className="mt-2 text-xl font-bold text-slate-900">SCAN BARCODE / QR</div>
              </div>
              <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-100 to-teal-100 text-emerald-700 shadow-inner">
                <div className="absolute inset-2 rounded-xl border-2 border-emerald-500/80" />
                <div className="absolute h-8 w-8 rounded-lg border-2 border-emerald-600 bg-emerald-50" />
                <div className="absolute h-3 w-3 rounded-sm bg-emerald-600" />
                <div className="absolute left-3 top-3 h-2 w-2 border border-emerald-600" />
                <div className="absolute right-3 top-3 h-2 w-2 border border-emerald-600" />
                <div className="absolute bottom-3 left-3 h-2 w-2 border border-emerald-600" />
                <div className="absolute bottom-3 right-3 h-2 w-2 border border-emerald-600" />
              </div>
            </div>
          </button>
        </div>

        {cameraOpen ? (
          <Card>
            <CardHeader>
              <CardTitle>Camera capture</CardTitle>
              <CardDescription>Use the device camera to capture package evidence or a barcode/QR image.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-950">
                <video ref={videoRef} className="h-72 w-full object-cover" playsInline muted autoPlay />
              </div>
              <div className="flex flex-wrap gap-3">
                <Button type="button" onClick={captureCameraFrame}>Capture frame</Button>
                <Button type="button" variant="secondary" onClick={stopCamera}>Close camera</Button>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {cameraError ? <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">{cameraError}</p> : null}

        {/* Product Selection Mode Card */}
        <Card>
          <CardHeader className="border-b border-slate-100 pb-4">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Commodity Association</CardTitle>
                <CardDescription>
                  Link this inspection to a registered product in the Master Catalog or register a new commodity.
                </CardDescription>
              </div>
              <div className="flex items-center rounded-lg bg-slate-100 p-1 text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => setProductMode('existing')}
                  className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 transition-all ${productMode === 'existing'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-600 hover:text-slate-900'
                    }`}
                  data-testid="mode-existing-btn"
                >
                  <Search className="h-3.5 w-3.5" /> Select Existing Product
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setProductMode('new')
                    setSelectedProductId('')
                  }}
                  className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 transition-all ${productMode === 'new'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-600 hover:text-slate-900'
                    }`}
                  data-testid="mode-new-btn"
                >
                  <PlusCircle className="h-3.5 w-3.5" /> Register New Product
                </button>
              </div>
            </div>
          </CardHeader>

          <CardContent className="pt-5 space-y-4">
            {productMode === 'existing' ? (
              <div className="space-y-4">
                <div>
                  <label htmlFor="productSelect" className="mb-2 block text-sm font-medium text-slate-700">
                    Registered Product *
                  </label>
                  {loadingProducts ? (
                    <div className="text-xs text-slate-500">Loading registered products...</div>
                  ) : (
                    <select
                      id="productSelect"
                      value={selectedProductId}
                      onChange={(e) => handleSelectProduct(e.target.value)}
                      className="w-full rounded-md border border-slate-200 bg-white p-2.5 text-sm text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                      data-testid="product-select"
                    >
                      <option value="">-- Choose from Master Catalog ({availableProducts.length} registered) --</option>
                      {availableProducts.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} {p.brand ? `[${p.brand}]` : ''} — {p.category || 'General'}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                {selectedProductId && (
                  <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-4 text-xs space-y-2">
                    <div className="flex items-center gap-2 text-indigo-800 font-semibold">
                      <Check className="h-4 w-4" /> Linked to Master Catalog Record
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-slate-600 pt-1">
                      <div><span className="text-slate-400">Brand:</span> {form.brand || '—'}</div>
                      <div><span className="text-slate-400">Category:</span> {form.category || '—'}</div>
                      <div className="col-span-2"><span className="text-slate-400">Manufacturer:</span> {form.manufacturer || '—'}</div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label htmlFor="productName" className="mb-2 block text-sm font-medium text-slate-700">Product name *</label>
                    <Input
                      id="productName"
                      placeholder="e.g. Premium Basmati Rice 5kg"
                      value={form.productName}
                      onChange={(event) => setForm((current) => ({ ...current, productName: event.target.value }))}
                      required
                      data-testid="product-name-input"
                    />
                  </div>
                  <div>
                    <label htmlFor="brand" className="mb-2 block text-sm font-medium text-slate-700">Brand</label>
                    <Input
                      id="brand"
                      placeholder="e.g. Heritage"
                      value={form.brand}
                      onChange={(event) => setForm((current) => ({ ...current, brand: event.target.value }))}
                      data-testid="product-brand-input"
                    />
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label htmlFor="category" className="mb-2 block text-sm font-medium text-slate-700">Category</label>
                    <select
                      id="category"
                      value={form.category}
                      onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))}
                      className="w-full rounded-md border border-slate-200 bg-white p-2.5 text-sm text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                      data-testid="product-category-select"
                    >
                      <option value="Food & Beverages">Food & Beverages</option>
                      <option value="Cosmetics">Cosmetics</option>
                      <option value="Electronics">Electronics</option>
                      <option value="Personal Care">Personal Care</option>
                      <option value="Household">Household Goods</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="manufacturer" className="mb-2 block text-sm font-medium text-slate-700">Manufacturer / Packer</label>
                    <Input
                      id="manufacturer"
                      placeholder="e.g. Heritage Foods Ltd"
                      value={form.manufacturer}
                      onChange={(event) => setForm((current) => ({ ...current, manufacturer: event.target.value }))}
                      data-testid="product-manufacturer-input"
                    />
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Inspection Details Card */}
        <Card>
          <CardHeader>
            <CardTitle>Inspection Details</CardTitle>
            <CardDescription>Configure inspection title, barcode identifiers, and field notes.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <label htmlFor="title" className="mb-2 block text-sm font-medium text-slate-700">Inspection title</label>
              <Input
                id="title"
                value={form.title}
                onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                data-testid="inspection-title-input"
              />
            </div>

            <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
              <div>
                <label htmlFor="barcode-or-qr" className="mb-2 block text-sm font-medium text-slate-700">Barcode / QR</label>
                <Input
                  id="barcode-or-qr"
                  value={barcodeValue}
                  onChange={(event) => setBarcodeValue(event.target.value)}
                  placeholder="Enter barcode or QR value"
                  data-testid="barcode-input"
                />
              </div>
              <div className="w-full md:w-auto">
                <label htmlFor="capture-side" className="mb-2 block text-sm font-medium text-slate-700">Image side</label>
                <Select
                  id="capture-side"
                  value={selectedImageType}
                  onChange={(event) => setSelectedImageType(event.target.value as CaptureSide)}
                >
                  <option value="front">Front</option>
                  <option value="back">Back</option>
                  <option value="left_side">Left Side</option>
                  <option value="right_side">Right Side</option>
                  <option value="other">Other</option>
                </Select>
              </div>
            </div>

            <div>
              <label htmlFor="notes" className="mb-2 block text-sm font-medium text-slate-700">Notes</label>
              <textarea
                id="notes"
                rows={3}
                value={form.notes}
                onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-200"
              />
            </div>

            {selectedFiles.length > 0 ? (
              <div className="space-y-3">
                <div className="text-sm font-medium text-slate-700">Selected evidence ({selectedFiles.length})</div>
                <div className="grid gap-3 md:grid-cols-3">
                  {(selectedFiles.slice(0, 6) ?? []).map((file, index) => (
                    <div key={`${file.name}-${index}`} className="overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
                      <img
                        src={URL.createObjectURL(file)}
                        alt={`Captured evidence ${index + 1}`}
                        className="h-28 w-full object-cover"
                      />
                      <div className="truncate px-2 py-2 text-xs text-slate-600">{file.name}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : capturedPreview ? (
              <img src={capturedPreview} alt="Captured package frame" className="h-48 w-full rounded-xl object-cover border border-slate-200" />
            ) : null}

            {errorMessage ? <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{errorMessage}</p> : null}

            <div className="flex justify-end">
              <Button type="submit" disabled={isSubmitting} data-testid="create-inspection-submit-btn">
                {isSubmitting ? 'Creating...' : 'Create inspection'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  )
}
