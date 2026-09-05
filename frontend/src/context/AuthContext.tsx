import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react'
import {
  type UserProfile,
  ROLE_PERMISSIONS,
  getStoredToken,
  getStoredUser,
  setStoredToken,
  setStoredUser,
  clearAuthStorage,
  loginUser,
  logoutUser,
  fetchCurrentUser,
} from '../lib/api'

interface AuthContextType {
  user: UserProfile | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<UserProfile>
  logout: () => Promise<void>
  hasPermission: (permission: string) => boolean
  hasRole: (role: string | string[]) => boolean
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

function initAuthSession(): { token: string | null; user: UserProfile | null } {
  if (typeof window === 'undefined') return { token: null, user: null }
  return { token: getStoredToken(), user: getStoredUser() }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const initialSession = initAuthSession()
  const [token, setToken] = useState<string | null>(initialSession.token)
  const [user, setUser] = useState<UserProfile | null>(initialSession.user)
  const [isLoading, setIsLoading] = useState<boolean>(() => Boolean(initialSession.token && !initialSession.user))

  const checkAuthStatus = useCallback(async () => {
    const currentToken = getStoredToken()
    if (!currentToken) {
      setUser(null)
      setToken(null)
      setIsLoading(false)
      return
    }

    try {
      const refreshedUser = await fetchCurrentUser()
      setUser(refreshedUser)
      setToken(currentToken)
    } catch {
      clearAuthStorage()
      setUser(null)
      setToken(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void checkAuthStatus()

    const handleUnauthorized = () => {
      setUser(null)
      setToken(null)
      setIsLoading(false)
    }

    window.addEventListener('praman:auth_unauthorized', handleUnauthorized)
    return () => {
      window.removeEventListener('praman:auth_unauthorized', handleUnauthorized)
    }
  }, [checkAuthStatus])

  const login = useCallback(async (email: string, password: string): Promise<UserProfile> => {
    setIsLoading(true)
    try {
      const response = await loginUser(email, password)
      setToken(response.access_token)
      setUser(response.user)
      setStoredToken(response.access_token)
      setStoredUser(response.user)
      return response.user
    } finally {
      setIsLoading(false)
    }
  }, [])

  const logout = useCallback(async (): Promise<void> => {
    try {
      await logoutUser()
    } finally {
      clearAuthStorage()
      setToken(null)
      setUser(null)
    }
  }, [])

  const hasPermission = useCallback((permission: string): boolean => {
    if (!user) return false
    const roleKey = user.role.toUpperCase()
    const allowed = ROLE_PERMISSIONS[roleKey] || []
    return allowed.includes(permission.toLowerCase())
  }, [user])

  const hasRole = useCallback((roles: string | string[]): boolean => {
    if (!user) return false
    const roleList = Array.isArray(roles) ? roles : [roles]
    const userRole = user.role.toUpperCase()
    return roleList.some((r) => r.toUpperCase() === userRole)
  }, [user])

  const refreshUser = useCallback(async (): Promise<void> => {
    if (!token) return
    try {
      const updated = await fetchCurrentUser()
      setUser(updated)
    } catch {
      // Ignored if offline
    }
  }, [token])

  const value = useMemo<AuthContextType>(() => ({
    user,
    token,
    isAuthenticated: Boolean(token && user),
    isLoading,
    login,
    logout,
    hasPermission,
    hasRole,
    refreshUser,
  }), [user, token, isLoading, login, logout, hasPermission, hasRole, refreshUser])

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
