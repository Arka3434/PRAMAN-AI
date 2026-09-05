import { useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './context/AuthContext'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { Sidebar } from './components/layout/sidebar'
import { TopBar } from './components/layout/top-bar'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { ConsumerScanPage } from './pages/ConsumerScanPage'
import { InspectionWorkflowPage } from './pages/InspectionWorkflowPage'
import { InspectionsPage } from './pages/InspectionsPage'
import { LoginPage } from './pages/LoginPage'
import { NewInspectionPage } from './pages/NewInspectionPage'
import { OverviewPage } from './pages/OverviewPage'
import { ProductsPage } from './pages/ProductsPage'
import { ReportsPage } from './pages/ReportsPage'
import { RulesPage } from './pages/RulesPage'
import { SettingsPage } from './pages/SettingsPage'
import { UsersPage } from './pages/UsersPage'
import { ViolationsPage } from './pages/ViolationsPage'

function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="h-screen overflow-hidden bg-slate-100 text-slate-900">
      <div className="flex h-full">
        <Sidebar open={sidebarOpen} onToggle={() => setSidebarOpen((current) => !current)} onNavigate={() => setSidebarOpen(false)} />

        {sidebarOpen ? <button type="button" aria-label="Close overlay" className="fixed inset-0 z-30 bg-slate-950/30 lg:hidden" onClick={() => setSidebarOpen(false)} /> : null}

        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar onToggleSidebar={() => setSidebarOpen((current) => !current)} />
          <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
            <div className="mx-auto max-w-[1600px]">
              <Routes>
                <Route path="/" element={<OverviewPage />} />
                <Route path="/inspections" element={<InspectionsPage />} />
                <Route path="/inspections/:inspectionId" element={<InspectionWorkflowPage />} />
                <Route
                  path="/inspections/new"
                  element={
                    <ProtectedRoute requiredPermission="inspections:create">
                      <NewInspectionPage />
                    </ProtectedRoute>
                  }
                />
                <Route path="/products" element={<ProductsPage />} />
                <Route path="/violations" element={<ViolationsPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/rules" element={<RulesPage />} />
                <Route
                  path="/users"
                  element={
                    <ProtectedRoute requiredRole="ADMIN">
                      <UsersPage />
                    </ProtectedRoute>
                  }
                />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public unauthenticated routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/consumer" element={<ConsumerScanPage />} />

          {/* Protected internal enforcement portal */}
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
