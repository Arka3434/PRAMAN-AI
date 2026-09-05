import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { useAuth } from '../../context/AuthContext'

export function TopBar({ onToggleSidebar }: { onToggleSidebar: () => void }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const roleBadgeColor: Record<string, string> = {
    ADMIN: 'bg-sky-500/10 text-sky-700 border-sky-300',
    SUPERVISING_OFFICER: 'bg-emerald-500/10 text-emerald-700 border-emerald-300',
    LEGAL_METROLOGY_INSPECTOR: 'bg-amber-500/10 text-amber-700 border-amber-300',
    REVIEWER: 'bg-purple-500/10 text-purple-700 border-purple-300',
  }

  const roleName = user?.role ? user.role.replace(/_/g, ' ') : 'Officer'
  const badgeClass = roleBadgeColor[user?.role || ''] || 'bg-slate-100 text-slate-700 border-slate-300'

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur-sm">
      <div className="flex items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onToggleSidebar}
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 text-slate-700 lg:hidden"
            aria-label="Open navigation menu"
          >
            ☰
          </button>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Legal Metrology Portal</p>
            <h2 className="text-base font-semibold text-slate-900">Enforcement Command Center</h2>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden relative w-64 md:block">
            <Input placeholder="Search inspections..." className="pl-9 text-xs h-9" aria-label="Search inspections" />
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs">⌕</span>
          </div>

          <Button asChild size="sm">
            <Link to="/inspections/new">New Inspection</Link>
          </Button>

          {/* Officer Identity & Logout */}
          {user && (
            <div className="flex items-center gap-3 border-l border-slate-200 pl-3">
              <div className="hidden text-right sm:block">
                <div className="flex items-center justify-end gap-1.5">
                  <span className="text-xs font-bold text-slate-900">{user.full_name}</span>
                  <span className={`inline-block rounded-full border px-1.5 py-0.2 text-[9px] font-semibold uppercase tracking-wider ${badgeClass}`}>
                    {roleName}
                  </span>
                </div>
                <div className="text-[11px] text-slate-500">
                  {user.badge_number ? `Badge: ${user.badge_number}` : (user.jurisdiction_office || user.email)}
                </div>
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={handleLogout}
                className="h-8 px-2.5 text-xs text-slate-700 hover:bg-rose-50 hover:text-rose-600 hover:border-rose-300"
                title="Sign Out"
                id="officer-logout-btn"
              >
                Sign Out
              </Button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
