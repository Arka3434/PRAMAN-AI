import React from 'react'
import { Navigate, useLocation, Outlet } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

interface ProtectedRouteProps {
  children?: React.ReactNode
  requiredPermission?: string
  requiredRole?: string | string[]
}

export function ProtectedRoute({ children, requiredPermission, requiredRole }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user, hasPermission, hasRole } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-slate-900 text-slate-200">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-sky-500 border-t-transparent" />
          <p className="text-sm font-medium text-slate-400">Verifying officer security credentials...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center p-6 text-center">
        <div className="mb-4 rounded-full bg-amber-500/10 p-4 text-amber-500">
          <svg className="h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-slate-900">Access Restricted</h2>
        <p className="mt-2 max-w-md text-sm text-slate-600">
          Your current assignment role (<span className="font-semibold text-slate-800">{user?.role}</span>) does not possess the required statutory permission (<code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-800">{requiredPermission}</code>) to access this workflow.
        </p>
        <button
          type="button"
          onClick={() => window.history.back()}
          className="mt-6 rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
        >
          Return to Previous Screen
        </button>
      </div>
    )
  }

  if (requiredRole && !hasRole(requiredRole)) {
    const rolesStr = Array.isArray(requiredRole) ? requiredRole.join(', ') : requiredRole
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center p-6 text-center">
        <div className="mb-4 rounded-full bg-rose-500/10 p-4 text-rose-500">
          <svg className="h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-slate-900">Designated Role Required</h2>
        <p className="mt-2 max-w-md text-sm text-slate-600">
          This operation is strictly reserved for officers with designation: <span className="font-semibold text-slate-800">{rolesStr}</span>.
        </p>
        <button
          type="button"
          onClick={() => window.history.back()}
          className="mt-6 rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
        >
          Return to Previous Screen
        </button>
      </div>
    )
  }

  return children ? <>{children}</> : <Outlet />
}
