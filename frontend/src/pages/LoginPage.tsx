import React, { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!email.trim() || !password) {
      setErrorMessage('Please enter both email address and password.')
      return
    }

    setIsSubmitting(true)
    try {
      await login(email.trim(), password)
      navigate(from, { replace: true })
    } catch (err: unknown) {
      const error = err as Error & { status?: number }
      if (error.status === 423 || error.message.toLowerCase().includes('locked')) {
        setErrorMessage('Account locked due to excessive failed attempts. Please try again after 15 minutes or contact a system administrator.')
      } else if (error.status === 401 || error.message.toLowerCase().includes('incorrect') || error.message.toLowerCase().includes('invalid')) {
        setErrorMessage('Invalid officer email address or password. Please verify your credentials.')
      } else {
        setErrorMessage(error.message || 'Authentication failed. Please verify server connectivity.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const fillQuickEmail = (e: string) => {
    setEmail(e)
    setErrorMessage(null)
  }

  return (
    <div className="flex min-h-screen flex-col justify-center bg-gradient-to-br from-slate-950 via-[#0B132B] to-[#1C2541] px-4 py-12 text-slate-100 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        {/* Emblem & Branding */}
        <div className="flex flex-col items-center text-center">
          <div className="relative mb-3 flex h-20 w-20 items-center justify-center rounded-2xl border border-sky-500/30 bg-gradient-to-br from-slate-900 via-sky-950 to-slate-900 shadow-2xl shadow-sky-500/10">
            <span className="text-3xl font-extrabold tracking-wider text-sky-400">प्र</span>
            <div className="absolute -inset-0.5 -z-10 rounded-2xl bg-gradient-to-r from-sky-500 to-indigo-500 opacity-20 blur-sm" />
          </div>
          <span className="text-xs font-bold uppercase tracking-[0.25em] text-sky-400">
            Government of India • Ministry of Consumer Affairs
          </span>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-white sm:text-3xl">
            PRAMAN AI
          </h1>
          <p className="mt-1 text-xs uppercase tracking-widest text-slate-400">
            Legal Metrology Automated Enforcement Portal
          </p>
        </div>

        {/* Card */}
        <div className="mt-8 rounded-2xl border border-slate-800/80 bg-slate-900/80 p-8 shadow-2xl backdrop-blur-xl sm:rounded-3xl">
          <div className="mb-6 flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-base font-semibold text-white">Officer Authentication</h2>
              <p className="text-xs text-slate-400">Sign in to your assigned statutory portal</p>
            </div>
            <span className="inline-flex items-center rounded-full bg-sky-500/10 px-2.5 py-1 text-[11px] font-medium text-sky-400 border border-sky-500/20">
              Phase 15 RBAC
            </span>
          </div>

          {errorMessage && (
            <div className="mb-6 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300 shadow-inner">
              <div className="flex items-start gap-3">
                <span className="text-lg leading-none">⚠️</span>
                <p className="leading-snug">{errorMessage}</p>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="officer-email" className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Official Email Address
              </label>
              <div className="mt-1.5 relative">
                <input
                  id="officer-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="officer@praman.gov.in"
                  className="w-full rounded-xl border border-slate-700/80 bg-slate-950/60 px-4 py-2.5 text-sm text-white placeholder-slate-500 transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/30"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label htmlFor="officer-password" className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-xs font-medium text-sky-400 hover:text-sky-300"
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              <div className="mt-1.5 relative">
                <input
                  id="officer-password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full rounded-xl border border-slate-700/80 bg-slate-950/60 px-4 py-2.5 text-sm text-white placeholder-slate-500 transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/30"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-2 flex w-full items-center justify-center rounded-xl bg-gradient-to-r from-sky-600 to-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-600/25 transition hover:from-sky-500 hover:to-indigo-500 focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? (
                <div className="flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Verifying Credentials...</span>
                </div>
              ) : (
                'Sign In to Enforcement Console'
              )}
            </button>
          </form>

          {/* Development-Only Email Quick-Select (Zero Passwords, Eliminated in Production Builds) */}
          {import.meta.env.DEV && (
            <div className="mt-6 border-t border-slate-800/80 pt-5">
              <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                Development Quick Select (Email Only)
              </p>
              <div className="mt-2.5 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => fillQuickEmail('admin@praman.gov.in')}
                  className="rounded-lg border border-slate-800 bg-slate-950/40 p-2 text-left transition hover:border-slate-700 hover:bg-slate-800/50"
                >
                  <div className="text-xs font-semibold text-sky-400">Administrator</div>
                  <div className="text-[10px] text-slate-500">admin@praman.gov.in</div>
                </button>
                <button
                  type="button"
                  onClick={() => fillQuickEmail('supervisor@praman.gov.in')}
                  className="rounded-lg border border-slate-800 bg-slate-950/40 p-2 text-left transition hover:border-slate-700 hover:bg-slate-800/50"
                >
                  <div className="text-xs font-semibold text-emerald-400">Supervisor</div>
                  <div className="text-[10px] text-slate-500">supervisor@praman.gov.in</div>
                </button>
                <button
                  type="button"
                  onClick={() => fillQuickEmail('inspector1@praman.gov.in')}
                  className="rounded-lg border border-slate-800 bg-slate-950/40 p-2 text-left transition hover:border-slate-700 hover:bg-slate-800/50"
                >
                  <div className="text-xs font-semibold text-amber-400">Inspector</div>
                  <div className="text-[10px] text-slate-500">inspector1@praman.gov.in</div>
                </button>
                <button
                  type="button"
                  onClick={() => fillQuickEmail('reviewer@praman.gov.in')}
                  className="rounded-lg border border-slate-800 bg-slate-950/40 p-2 text-left transition hover:border-slate-700 hover:bg-slate-800/50"
                >
                  <div className="text-xs font-semibold text-purple-400">Reviewer</div>
                  <div className="text-[10px] text-slate-500">reviewer@praman.gov.in</div>
                </button>
              </div>
            </div>
          )}

          <div className="mt-6 flex items-center justify-between text-xs text-slate-400">
            <Link to="/consumer" className="text-sky-400 hover:underline">
              ← Public Consumer Scan Portal
            </Link>
            <span>v1.0-Phase15</span>
          </div>
        </div>

        {/* Statutory Legal Disclaimer */}
        <p className="mt-6 text-center text-[11px] leading-relaxed text-slate-500">
          This is an official computational portal of the Department of Legal Metrology, Government of India.
          Access is monitored and unauthorized access attempts are recorded under the IT Act, 2000.
        </p>
      </div>
    </div>
  )
}
