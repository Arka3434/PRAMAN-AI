import { NavLink } from 'react-router-dom'
import { cn } from '../../lib/utils'
import { useAuth } from '../../context/AuthContext'

interface NavItem {
  label: string
  to: string
  requiredPermission?: string
  requiredRole?: string | string[]
}

const navigation: NavItem[] = [
  { label: 'Overview', to: '/' },
  { label: 'New Inspection', to: '/inspections/new', requiredPermission: 'inspections:create' },
  { label: 'Inspections', to: '/inspections' },
  { label: 'Products', to: '/products' },
  { label: 'Violations', to: '/violations' },
  { label: 'Reports', to: '/reports' },
  { label: 'Analytics', to: '/analytics' },
  { label: 'Rules', to: '/rules' },
  { label: 'Consumer Scan', to: '/consumer' },
  { label: 'Users', to: '/users', requiredRole: 'ADMIN' },
  { label: 'Settings', to: '/settings' },
]

export function Sidebar({ open, onToggle, onNavigate }: { open: boolean; onToggle: () => void; onNavigate?: () => void }) {
  const { user, hasPermission, hasRole } = useAuth()

  const visibleNav = navigation.filter((item) => {
    if (item.requiredRole && !hasRole(item.requiredRole)) return false
    if (item.requiredPermission && !hasPermission(item.requiredPermission)) return false
    return true
  })

  return (
    <aside
      className={cn(
        'fixed inset-y-0 left-0 z-40 flex h-screen w-72 shrink-0 flex-col border-r border-slate-800 bg-[#0d1b2a] px-4 py-5 text-slate-200 transition-transform duration-200 lg:sticky lg:top-0 lg:z-auto lg:translate-x-0',
        open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
      )}
    >
      <div className="mb-8 flex items-center justify-between">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-sky-300">PRAMAN AI</div>
          <div className="mt-1 text-lg font-semibold text-white">Compliance Center</div>
        </div>
        <button type="button" className="rounded-md border border-slate-700 p-2 text-slate-200 lg:hidden" onClick={onToggle} aria-label="Close navigation menu">
          ✕
        </button>
      </div>

      <nav className="space-y-1 overflow-y-auto pr-1">
        {visibleNav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'flex items-center rounded-xl px-3 py-2.5 text-sm font-medium transition',
                isActive ? 'bg-slate-800 text-white shadow-inner' : 'text-slate-300 hover:bg-slate-800/70 hover:text-white',
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto space-y-3">
        {user && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-3 text-xs">
            <div className="text-[10px] uppercase tracking-wider text-slate-400">Authenticated As</div>
            <div className="mt-1 font-semibold text-white truncate">{user.full_name}</div>
            <div className="text-[11px] text-sky-400">{user.role}</div>
          </div>
        )}

        <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">System status</p>
          <div className="mt-2 flex items-center gap-2 text-sm font-medium text-emerald-300">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
            Phase 15 Secure Mesh
          </div>
        </div>
      </div>
    </aside>
  )
}
