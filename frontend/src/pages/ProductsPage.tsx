import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  ArrowUpRight,
  Boxes,
  CheckCircle2,
  Edit2,
  ExternalLink,
  History,
  Package,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  X,
} from 'lucide-react'

import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { PageHeader } from '../components/ui/page-header'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table'
import { getStoredToken } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type ProductSummary = {
  id: string
  name: string
  category: string | null
  brand: string | null
  manufacturer: string | null
  description: string | null
  created_at: string
  updated_at: string
  inspection_count: number
  last_inspected_at: string | null
  compliance_score: number | null
  latest_verdict: string | null
}

export type ProductInspectionRecord = {
  id: string
  inspection_number: string
  status: string
  created_at: string
  overall_result: string | null
  finding_count: number
  report_available: boolean
}

export type ProductDetailResponse = ProductSummary & {
  inspections: ProductInspectionRecord[]
}

const CATEGORIES = [
  'All',
  'Food & Beverages',
  'Cosmetics',
  'Electronics',
  'Personal Care',
  'Household',
  'Other',
]

export function ProductsPage() {
  const navigate = useNavigate()
  const [products, setProducts] = useState<ProductSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('All')

  // Detail Drawer State
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null)
  const [productDetail, setProductDetail] = useState<ProductDetailResponse | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState({
    name: '',
    brand: '',
    category: '',
    manufacturer: '',
    description: '',
  })
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  // Register Modal State
  const [registerModalOpen, setRegisterModalOpen] = useState(false)
  const [newProductForm, setNewProductForm] = useState({
    name: '',
    brand: '',
    category: 'Food & Beverages',
    manufacturer: '',
    description: '',
  })
  const [isRegistering, setIsRegistering] = useState(false)
  const [registerError, setRegisterError] = useState<string | null>(null)

  const fetchProducts = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (categoryFilter !== 'All') {
        params.append('category', categoryFilter)
      }
      if (searchTerm.trim()) {
        params.append('search', searchTerm.trim())
      }

      const token = getStoredToken()
      const res = await fetch(`${API_BASE}/api/v1/products?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) {
        throw new Error(`Failed to load products: HTTP ${res.status}`)
      }
      const data = (await res.json()) as ProductSummary[]
      setProducts(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error fetching products')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchProducts()
    }, 200)
    return () => clearTimeout(timer)
  }, [searchTerm, categoryFilter])

  const openProductDrawer = async (productId: string) => {
    setSelectedProductId(productId)
    setLoadingDetail(true)
    setActionError(null)
    setActionSuccess(null)
    setIsEditing(false)
    try {
      const token = getStoredToken()
      const res = await fetch(`${API_BASE}/api/v1/products/${productId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) {
        throw new Error('Failed to load product details')
      }
      const data = (await res.json()) as ProductDetailResponse
      setProductDetail(data)
      setEditForm({
        name: data.name || '',
        brand: data.brand || '',
        category: data.category || '',
        manufacturer: data.manufacturer || '',
        description: data.description || '',
      })
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Error loading details')
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleUpdateProduct = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedProductId) return
    setActionError(null)
    setActionSuccess(null)
    try {
      const token = getStoredToken()
      const res = await fetch(`${API_BASE}/api/v1/products/${selectedProductId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(editForm),
      })
      if (!res.ok) {
        const detail = await res.text()
        throw new Error(detail || 'Failed to update product metadata')
      }
      const updated = (await res.json()) as ProductSummary
      setProductDetail((prev) => (prev ? { ...prev, ...updated } : null))
      setIsEditing(false)
      setActionSuccess('Product catalog entry updated successfully.')
      void fetchProducts()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Error updating product')
    }
  }

  const handleDeleteProduct = async () => {
    if (!selectedProductId) return
    if (!window.confirm('Are you sure you want to delete this product?')) return
    setActionError(null)
    try {
      const token = getStoredToken()
      const res = await fetch(`${API_BASE}/api/v1/products/${selectedProductId}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Cannot delete product')
      }
      setSelectedProductId(null)
      setProductDetail(null)
      void fetchProducts()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Error deleting product')
    }
  }

  const handleRegisterProduct = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsRegistering(true)
    setRegisterError(null)
    try {
      const token = getStoredToken()
      const res = await fetch(`${API_BASE}/api/v1/products`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(newProductForm),
      })
      if (!res.ok) {
        const detail = await res.text()
        throw new Error(detail || 'Failed to register product')
      }
      setRegisterModalOpen(false)
      setNewProductForm({
        name: '',
        brand: '',
        category: 'Food & Beverages',
        manufacturer: '',
        description: '',
      })
      void fetchProducts()
    } catch (err) {
      setRegisterError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setIsRegistering(false)
    }
  }

  const renderVerdictBadge = (verdict: string | null) => {
    switch (verdict) {
      case 'COMPLIANT':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="h-3.5 w-3.5" /> Compliant
          </span>
        )
      case 'POTENTIAL_VIOLATION':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-semibold text-rose-700 border border-rose-200">
            <AlertCircle className="h-3.5 w-3.5" /> Potential Violation
          </span>
        )
      case 'WARNINGS_OR_MANUAL_REVIEW':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-700 border border-amber-200">
            <AlertCircle className="h-3.5 w-3.5" /> Review / Warning
          </span>
        )
      case 'PENDING_ANALYSIS':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-50 px-2.5 py-0.5 text-xs font-semibold text-slate-600 border border-slate-200">
            <RefreshCw className="h-3.5 w-3.5" /> Pending Analysis
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-500">
            Uninspected
          </span>
        )
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Products"
        description="Master catalog of registered packaged commodities, inspection frequency, and statutory compliance history."
        action={
          <Button
            onClick={() => setRegisterModalOpen(true)}
            data-testid="register-product-button"
            className="flex items-center gap-2"
          >
            <Plus className="h-4 w-4" /> Register Product
          </Button>
        }
      />

      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b border-slate-100 pb-4">
          <div>
            <CardTitle>Product Portfolio</CardTitle>
            <CardDescription>
              Registered commodity identities, cross-inspection history, and evaluated statutory rule outcomes.
            </CardDescription>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Category Filter Chips */}
            <div className="flex flex-wrap items-center gap-1 rounded-lg bg-slate-100 p-1 text-xs">
              {CATEGORIES.slice(0, 5).map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setCategoryFilter(cat)}
                  className={`rounded-md px-2.5 py-1 font-medium transition-all ${
                    categoryFilter === cat
                      ? 'bg-white text-slate-900 shadow-sm font-semibold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                  data-testid={`category-tab-${cat}`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Search Input */}
            <div className="relative w-64">
              <Input
                placeholder="Search products, brands..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 text-xs"
                data-testid="products-search-input"
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
            <div className="p-12 text-center text-sm text-slate-500">
              <RefreshCw className="mx-auto h-6 w-6 animate-spin text-slate-400 mb-2" />
              Loading product portfolio...
            </div>
          ) : products.length === 0 ? (
            <div className="p-12 text-center" data-testid="empty-products-message">
              <Package className="mx-auto h-10 w-10 text-slate-300" />
              <div className="mt-2 text-sm font-semibold text-slate-700">No products found</div>
              <div className="mt-1 text-xs text-slate-500">
                {searchTerm || categoryFilter !== 'All'
                  ? 'Try adjusting your search criteria or category filter.'
                  : 'Register a product to start organizing inspection records by commodity.'}
              </div>
              <div className="mt-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setRegisterModalOpen(true)}
                >
                  Register First Product
                </Button>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Product & Brand</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Manufacturer</TableHead>
                    <TableHead className="text-center">Inspections</TableHead>
                    <TableHead className="text-center">Compliance Ratio</TableHead>
                    <TableHead>Latest Verdict</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {products.map((prod) => (
                    <TableRow
                      key={prod.id}
                      className="hover:bg-slate-50/70 transition-colors"
                      data-testid={`product-row-${prod.id}`}
                    >
                      <TableCell>
                        <div className="font-semibold text-slate-900">{prod.name}</div>
                        {prod.brand && (
                          <div className="text-xs text-slate-500 font-medium">
                            Brand: {prod.brand}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-700 font-medium">
                          {prod.category || 'General'}
                        </span>
                      </TableCell>
                      <TableCell className="text-xs text-slate-600">
                        {prod.manufacturer || '—'}
                      </TableCell>
                      <TableCell className="text-center font-medium text-slate-700">
                        {prod.inspection_count > 0 ? (
                          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-800">
                            {prod.inspection_count}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">0</span>
                        )}
                      </TableCell>
                      <TableCell className="text-center font-medium">
                        {prod.compliance_score !== null ? (
                          <div className="inline-block">
                            <span
                              className={`text-sm font-bold ${
                                prod.compliance_score >= 80
                                  ? 'text-emerald-700'
                                  : prod.compliance_score >= 50
                                  ? 'text-amber-700'
                                  : 'text-rose-700'
                              }`}
                            >
                              {prod.compliance_score}%
                            </span>
                            <div className="text-[10px] text-slate-400">evaluated rules</div>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </TableCell>
                      <TableCell>{renderVerdictBadge(prod.latest_verdict)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openProductDrawer(prod.id)}
                            className="text-xs text-slate-600 hover:text-slate-900"
                            data-testid={`view-product-${prod.id}`}
                          >
                            Details
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigate(`/inspections/new?productId=${prod.id}`)}
                            className="text-xs flex items-center gap-1"
                            data-testid={`inspect-product-${prod.id}`}
                          >
                            Inspect <ArrowUpRight className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Slide-over Product Detail Drawer */}
      {selectedProductId && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-slate-950/40 backdrop-blur-sm transition-opacity"
          data-testid="product-detail-drawer"
        >
          <div className="flex h-full w-full max-w-xl flex-col bg-white shadow-2xl border-l border-slate-200 overflow-y-auto">
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-slate-100 p-6">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-indigo-50 p-2 text-indigo-700">
                  <Boxes className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-slate-900">Product Portfolio Detail</h2>
                  <p className="text-xs text-slate-500">
                    ID: {selectedProductId.slice(0, 8)}...
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedProductId(null)}
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
                aria-label="Close drawer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Drawer Content */}
            <div className="flex-1 p-6 space-y-6">
              {actionError && (
                <div className="rounded-lg bg-rose-50 p-3 text-xs text-rose-700 border border-rose-200">
                  {actionError}
                </div>
              )}
              {actionSuccess && (
                <div className="rounded-lg bg-emerald-50 p-3 text-xs text-emerald-700 border border-emerald-200">
                  {actionSuccess}
                </div>
              )}

              {loadingDetail || !productDetail ? (
                <div className="py-12 text-center text-sm text-slate-500">
                  <RefreshCw className="mx-auto h-6 w-6 animate-spin text-slate-400 mb-2" />
                  Loading product details...
                </div>
              ) : (
                <>
                  {/* Summary Metric Cards */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-center">
                      <div className="text-xs text-slate-500 font-medium">Total Inspections</div>
                      <div className="mt-1 text-xl font-bold text-slate-900">
                        {productDetail.inspection_count}
                      </div>
                    </div>
                    <div className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-center">
                      <div className="text-xs text-slate-500 font-medium">Compliance Ratio</div>
                      <div className="mt-1 text-xl font-bold text-slate-900">
                        {productDetail.compliance_score !== null
                          ? `${productDetail.compliance_score}%`
                          : '—'}
                      </div>
                      <div className="text-[9px] text-slate-400">passed rules</div>
                    </div>
                    <div className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-center">
                      <div className="text-xs text-slate-500 font-medium">Latest Verdict</div>
                      <div className="mt-1">
                        {renderVerdictBadge(productDetail.latest_verdict)}
                      </div>
                    </div>
                  </div>

                  {/* Metadata Specification Card */}
                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-2 border-b border-slate-100">
                      <CardTitle className="text-sm font-bold text-slate-900">
                        Product Specification
                      </CardTitle>
                      {!isEditing && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setIsEditing(true)}
                          className="h-8 text-xs text-indigo-600 hover:text-indigo-800"
                          data-testid="edit-product-btn"
                        >
                          <Edit2 className="h-3.5 w-3.5 mr-1" /> Edit
                        </Button>
                      )}
                    </CardHeader>
                    <CardContent className="pt-4 text-xs space-y-3">
                      {isEditing ? (
                        <form onSubmit={handleUpdateProduct} className="space-y-3">
                          <div>
                            <label className="block text-slate-600 font-semibold mb-1">
                              Product Name
                            </label>
                            <Input
                              value={editForm.name}
                              onChange={(e) =>
                                setEditForm((prev) => ({ ...prev, name: e.target.value }))
                              }
                              required
                              className="text-xs"
                            />
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="block text-slate-600 font-semibold mb-1">Brand</label>
                              <Input
                                value={editForm.brand}
                                onChange={(e) =>
                                  setEditForm((prev) => ({ ...prev, brand: e.target.value }))
                                }
                                className="text-xs"
                              />
                            </div>
                            <div>
                              <label className="block text-slate-600 font-semibold mb-1">Category</label>
                              <Input
                                value={editForm.category}
                                onChange={(e) =>
                                  setEditForm((prev) => ({ ...prev, category: e.target.value }))
                                }
                                className="text-xs"
                              />
                            </div>
                          </div>
                          <div>
                            <label className="block text-slate-600 font-semibold mb-1">
                              Manufacturer
                            </label>
                            <Input
                              value={editForm.manufacturer}
                              onChange={(e) =>
                                setEditForm((prev) => ({ ...prev, manufacturer: e.target.value }))
                              }
                              className="text-xs"
                            />
                          </div>
                          <div>
                            <label className="block text-slate-600 font-semibold mb-1">
                              Description
                            </label>
                            <textarea
                              value={editForm.description}
                              onChange={(e) =>
                                setEditForm((prev) => ({ ...prev, description: e.target.value }))
                              }
                              rows={2}
                              className="w-full rounded-md border border-slate-200 p-2 text-xs"
                            />
                          </div>
                          <div className="text-[10px] text-slate-500 bg-amber-50 p-2 rounded border border-amber-200">
                            Note: Editing product metadata updates catalog specifications only and does not alter historical inspection evidence, findings, or decisions.
                          </div>
                          <div className="flex justify-end gap-2 pt-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => setIsEditing(false)}
                            >
                              Cancel
                            </Button>
                            <Button type="submit" size="sm" data-testid="save-product-btn">
                              Save Changes
                            </Button>
                          </div>
                        </form>
                      ) : (
                        <div className="space-y-2">
                          <div className="flex justify-between py-1 border-b border-slate-100">
                            <span className="text-slate-500">Name:</span>
                            <span className="font-semibold text-slate-900">{productDetail.name}</span>
                          </div>
                          <div className="flex justify-between py-1 border-b border-slate-100">
                            <span className="text-slate-500">Brand:</span>
                            <span className="font-semibold text-slate-900">{productDetail.brand || '—'}</span>
                          </div>
                          <div className="flex justify-between py-1 border-b border-slate-100">
                            <span className="text-slate-500">Category:</span>
                            <span className="font-semibold text-slate-900">{productDetail.category || '—'}</span>
                          </div>
                          <div className="flex justify-between py-1 border-b border-slate-100">
                            <span className="text-slate-500">Manufacturer:</span>
                            <span className="font-semibold text-slate-900">{productDetail.manufacturer || '—'}</span>
                          </div>
                          <div className="flex justify-between py-1 border-b border-slate-100">
                            <span className="text-slate-500">Registered Date:</span>
                            <span className="text-slate-700">
                              {new Date(productDetail.created_at).toLocaleDateString()}
                            </span>
                          </div>
                          {productDetail.description && (
                            <div className="pt-2">
                              <span className="text-slate-500 block mb-1">Description:</span>
                              <p className="text-slate-700 bg-slate-50 p-2 rounded border border-slate-100">
                                {productDetail.description}
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  {/* Historical Inspections Section */}
                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-2 border-b border-slate-100">
                      <div>
                        <CardTitle className="text-sm font-bold text-slate-900">
                          Inspection History
                        </CardTitle>
                        <CardDescription className="text-xs">
                          Chronological audit records associated with this product identity.
                        </CardDescription>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => navigate(`/inspections/new?productId=${productDetail.id}`)}
                        className="text-xs flex items-center gap-1.5"
                        data-testid="inspect-product-drawer-btn"
                      >
                        <Plus className="h-3.5 w-3.5" /> Inspect Product
                      </Button>
                    </CardHeader>
                    <CardContent className="p-0">
                      {productDetail.inspections.length === 0 ? (
                        <div className="p-8 text-center text-xs text-slate-500">
                          <History className="mx-auto h-6 w-6 text-slate-300 mb-1" />
                          No inspections conducted yet for this product.
                        </div>
                      ) : (
                        <div className="divide-y divide-slate-100">
                          {productDetail.inspections.map((insp) => (
                            <div
                              key={insp.id}
                              className="p-3 hover:bg-slate-50 transition flex items-center justify-between text-xs"
                            >
                              <div>
                                <button
                                  type="button"
                                  onClick={() => navigate(`/inspections/${insp.id}`)}
                                  className="font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                                >
                                  {insp.inspection_number} <ExternalLink className="h-3 w-3" />
                                </button>
                                <div className="text-[11px] text-slate-400 mt-0.5">
                                  {new Date(insp.created_at).toLocaleDateString()} • {insp.finding_count} checks
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                {renderVerdictBadge(insp.overall_result)}
                                <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] uppercase font-semibold text-slate-600">
                                  {insp.status}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  {/* Deletion Safeguard */}
                  <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-[11px] text-slate-400">
                      {productDetail.inspection_count > 0
                        ? 'Product cannot be deleted because it has linked inspections.'
                        : 'No inspections linked. Product may be archived.'}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleDeleteProduct}
                      disabled={productDetail.inspection_count > 0}
                      className="text-xs text-rose-600 hover:text-rose-800 hover:bg-rose-50 disabled:opacity-40"
                      data-testid="delete-product-btn"
                    >
                      <Trash2 className="h-3.5 w-3.5 mr-1" /> Delete Product
                    </Button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Register New Product Modal */}
      {registerModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 backdrop-blur-sm p-4"
          data-testid="register-modal"
        >
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Package className="h-5 w-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900">Register New Product</h3>
              </div>
              <button
                type="button"
                onClick={() => setRegisterModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleRegisterProduct} className="space-y-4 pt-4">
              {registerError && (
                <div className="rounded-lg bg-rose-50 p-3 text-xs text-rose-700 border border-rose-200">
                  {registerError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Product Name *
                </label>
                <Input
                  placeholder="e.g. Basmati Rice 5kg"
                  value={newProductForm.name}
                  onChange={(e) =>
                    setNewProductForm((prev) => ({ ...prev, name: e.target.value }))
                  }
                  required
                  className="text-xs"
                  data-testid="new-product-name-input"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Brand</label>
                  <Input
                    placeholder="e.g. Heritage"
                    value={newProductForm.brand}
                    onChange={(e) =>
                      setNewProductForm((prev) => ({ ...prev, brand: e.target.value }))
                    }
                    className="text-xs"
                    data-testid="new-product-brand-input"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Category</label>
                  <select
                    value={newProductForm.category}
                    onChange={(e) =>
                      setNewProductForm((prev) => ({ ...prev, category: e.target.value }))
                    }
                    className="w-full rounded-md border border-slate-200 p-2 text-xs"
                    data-testid="new-product-category-select"
                  >
                    {CATEGORIES.filter((c) => c !== 'All').map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Manufacturer / Packer
                </label>
                <Input
                  placeholder="e.g. Heritage Foods India Ltd"
                  value={newProductForm.manufacturer}
                  onChange={(e) =>
                    setNewProductForm((prev) => ({ ...prev, manufacturer: e.target.value }))
                  }
                  className="text-xs"
                  data-testid="new-product-manufacturer-input"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Description
                </label>
                <textarea
                  placeholder="Optional packaging or commodity specifications..."
                  value={newProductForm.description}
                  onChange={(e) =>
                    setNewProductForm((prev) => ({ ...prev, description: e.target.value }))
                  }
                  rows={2}
                  className="w-full rounded-md border border-slate-200 p-2 text-xs"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setRegisterModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isRegistering}
                  data-testid="register-submit-btn"
                >
                  {isRegistering ? 'Registering...' : 'Register Product'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
