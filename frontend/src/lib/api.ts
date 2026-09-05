export const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const TOKEN_STORAGE_KEY = 'praman_token'
export const USER_STORAGE_KEY = 'praman_user'

export type UserRole = 'ADMIN' | 'SUPERVISING_OFFICER' | 'LEGAL_METROLOGY_INSPECTOR' | 'REVIEWER'

export interface UserProfile {
  id: string
  email: string
  full_name: string
  role: UserRole | string
  designation?: string | null
  badge_number?: string | null
  jurisdiction_office?: string | null
  is_active: boolean
  created_at?: string
  last_login_at?: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserProfile
}

export interface RolePermissionsMap {
  [role: string]: string[]
}

export const ROLE_PERMISSIONS: Record<string, string[]> = {
  ADMIN: [
    'inspections:read', 'inspections:create', 'inspections:edit', 'inspections:review', 'inspections:finalize',
    'notices:read', 'notices:create_draft', 'notices:edit', 'notices:review', 'notices:issue',
    'products:read', 'products:edit', 'rules:read', 'rules:edit', 'users:manage', 'audit:read', 'analytics:read',
  ],
  SUPERVISING_OFFICER: [
    'inspections:read', 'inspections:create', 'inspections:edit', 'inspections:review', 'inspections:finalize',
    'notices:read', 'notices:create_draft', 'notices:edit', 'notices:review', 'notices:issue',
    'products:read', 'products:edit', 'rules:read', 'audit:read', 'analytics:read',
  ],
  LEGAL_METROLOGY_INSPECTOR: [
    'inspections:read', 'inspections:create', 'inspections:edit',
    'notices:read', 'notices:create_draft', 'notices:edit',
    'products:read', 'products:edit', 'rules:read', 'analytics:read',
  ],
  REVIEWER: [
    'inspections:read', 'inspections:review',
    'notices:read', 'notices:review',
    'products:read', 'rules:read', 'analytics:read',
  ],
}

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null
  return sessionStorage.getItem(TOKEN_STORAGE_KEY) || localStorage.getItem(TOKEN_STORAGE_KEY)
}

export function setStoredToken(token: string): void {
  try {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, token)
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } catch {
    // ignore storage errors
  }
}

export function getStoredUser(): UserProfile | null {
  if (typeof window === 'undefined') return null
  const raw = sessionStorage.getItem(USER_STORAGE_KEY) || localStorage.getItem(USER_STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as UserProfile
  } catch {
    return null
  }
}

export function setStoredUser(user: UserProfile): void {
  try {
    const raw = JSON.stringify(user)
    sessionStorage.setItem(USER_STORAGE_KEY, raw)
    localStorage.setItem(USER_STORAGE_KEY, raw)
  } catch {
    // ignore storage errors
  }
}

export function clearAuthStorage(): void {
  try {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY)
    sessionStorage.removeItem(USER_STORAGE_KEY)
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    localStorage.removeItem(USER_STORAGE_KEY)
  } catch {
    // ignore storage errors
  }
}

/**
 * Global fetch interceptor to inject Authorization bearer header for
 * all internal API requests, strictly excluding consumer public endpoints and health checks.
 */
let interceptorInstalled = false

export function setupFetchInterceptor(): void {
  if (interceptorInstalled || typeof window === 'undefined') return
  interceptorInstalled = true

  const originalFetch = window.fetch.bind(window)

  window.fetch = async (input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> => {
    let urlString = ''
    if (typeof input === 'string') {
      urlString = input
    } else if (input instanceof URL) {
      urlString = input.toString()
    } else if (input && typeof input === 'object' && 'url' in input) {
      urlString = (input as Request).url
    }

    const isConsumerEndpoint = urlString.includes('/api/v1/consumer')
    const isHealthEndpoint = urlString.includes('/health')
    const isLoginEndpoint = urlString.includes('/api/v1/auth/login')

    const token = getStoredToken()

    let modifiedInit = init
    if (token && !isConsumerEndpoint && !isHealthEndpoint) {
      const headers = new Headers(init.headers || (input instanceof Request ? input.headers : {}))
      if (!headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${token}`)
      }
      modifiedInit = { ...init, headers }
    }

    const response = await originalFetch(input, modifiedInit)

    if (response.status === 401 && !isLoginEndpoint && !isConsumerEndpoint) {
      clearAuthStorage()
      window.dispatchEvent(new CustomEvent('praman:auth_unauthorized'))
    }

    return response
  }
}

// Auto-install interceptor on module import
setupFetchInterceptor()

export async function loginUser(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Authentication failed' }))
    const error = new Error(errorData.detail || `Login failed (${response.status})`) as Error & { status?: number }
    error.status = response.status
    throw error
  }

  const data: LoginResponse = await response.json()
  setStoredToken(data.access_token)
  setStoredUser(data.user)
  return data
}

export async function logoutUser(): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/v1/auth/logout`, {
      method: 'POST',
    })
  } finally {
    clearAuthStorage()
  }
}

export async function fetchCurrentUser(): Promise<UserProfile> {
  const response = await fetch(`${API_BASE}/api/v1/auth/me`)
  if (!response.ok) {
    throw new Error('Failed to fetch current user profile')
  }
  const user: UserProfile = await response.json()
  setStoredUser(user)
  return user
}

export async function fetchUsersList(): Promise<UserProfile[]> {
  const response = await fetch(`${API_BASE}/api/v1/users`)
  if (!response.ok) {
    throw new Error('Failed to fetch user directory')
  }
  return response.json()
}

export async function createNewUser(payload: {
  email: string
  password: string
  full_name: string
  role: string
  designation?: string
  badge_number?: string
  jurisdiction_office?: string
}): Promise<UserProfile> {
  const response = await fetch(`${API_BASE}/api/v1/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to create user' }))
    throw new Error(errorData.detail || 'Failed to create user')
  }
  return response.json()
}
