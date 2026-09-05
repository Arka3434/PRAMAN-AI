import { useEffect, useState } from 'react'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { PageHeader } from '../components/ui/page-header'
import { StatusBadge } from '../components/ui/status-badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table'
import { fetchUsersList, createNewUser, type UserProfile } from '../lib/api'
import { useAuth } from '../context/AuthContext'

export function UsersPage() {
  const { hasRole } = useAuth()
  const [users, setUsers] = useState<UserProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)

  // New user form state
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState('LEGAL_METROLOGY_INSPECTOR')
  const [designation, setDesignation] = useState('')
  const [badgeNumber, setBadgeNumber] = useState('')
  const [jurisdictionOffice, setJurisdictionOffice] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const loadUsers = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchUsersList()
      setUsers(data)
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to load user directory')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadUsers()
  }, [])

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateError(null)
    setCreating(true)
    try {
      await createNewUser({
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        role,
        designation: designation.trim() || undefined,
        badge_number: badgeNumber.trim() || undefined,
        jurisdiction_office: jurisdictionOffice.trim() || undefined,
      })
      setShowCreateModal(false)
      // Reset form
      setEmail('')
      setPassword('')
      setFullName('')
      setDesignation('')
      setBadgeNumber('')
      setJurisdictionOffice('')
      await loadUsers()
    } catch (err: unknown) {
      setCreateError((err as Error).message || 'Failed to create officer account')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="Statutory enforcement roster and role assignments for Legal Metrology officers."
        action={
          hasRole('ADMIN') ? (
            <Button onClick={() => setShowCreateModal(true)}>+ Register New Officer</Button>
          ) : undefined
        }
      />

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {error}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Active Officer Roster</CardTitle>
          <CardDescription>
            Authoritative officer identity footprint registered for statutory inspections and notices.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 text-center text-sm text-slate-500">Loading officer records...</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Officer Name & Email</TableHead>
                  <TableHead>Statutory Role</TableHead>
                  <TableHead>Designation</TableHead>
                  <TableHead>Badge / Office</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell>
                      <div className="font-semibold text-slate-900">{u.full_name}</div>
                      <div className="text-xs text-slate-500">{u.email}</div>
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex rounded-md bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-800 border border-slate-200">
                        {u.role}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm text-slate-700">{u.designation || '—'}</TableCell>
                    <TableCell className="text-sm text-slate-600">
                      <div>{u.badge_number ? `Badge: ${u.badge_number}` : '—'}</div>
                      <div className="text-xs text-slate-400">{u.jurisdiction_office || ''}</div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={u.is_active ? 'pass' : 'review'} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Register New Officer Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-900 p-6 text-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-lg font-bold">Register New Officer Account</h3>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            {createError && (
              <div className="mt-4 rounded-lg bg-rose-500/20 border border-rose-500/40 p-3 text-xs text-rose-300">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateUser} className="mt-4 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300">Full Name *</label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. S. K. Sharma"
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300">Official Email *</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="officer@praman.gov.in"
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300">Password (min 12 characters) *</label>
                <input
                  type="password"
                  required
                  minLength={12}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="StrongPass123!@#"
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300">Statutory Role *</label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                  >
                    <option value="LEGAL_METROLOGY_INSPECTOR">Legal Metrology Inspector</option>
                    <option value="SUPERVISING_OFFICER">Supervising Officer</option>
                    <option value="ADMIN">Administrator</option>
                    <option value="REVIEWER">Reviewer</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300">Badge / ID Number</label>
                  <input
                    type="text"
                    value={badgeNumber}
                    onChange={(e) => setBadgeNumber(e.target.value)}
                    placeholder="e.g. LMI-DEL-404"
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300">Designation</label>
                  <input
                    type="text"
                    value={designation}
                    onChange={(e) => setDesignation(e.target.value)}
                    placeholder="e.g. Senior Inspector"
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300">Jurisdiction / Office</label>
                  <input
                    type="text"
                    value={jurisdictionOffice}
                    onChange={(e) => setJurisdictionOffice(e.target.value)}
                    placeholder="e.g. Delhi Central Division"
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="mt-6 flex justify-end gap-3 border-t border-slate-800 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={creating}>
                  {creating ? 'Registering...' : 'Confirm Officer Registration'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
