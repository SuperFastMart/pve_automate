import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react'
import { useMsal, useIsAuthenticated, useMsalAuthentication, useAccount } from '@azure/msal-react'
import { InteractionType, InteractionStatus } from '@azure/msal-browser'
import { loginRequest } from './msalConfig'
import { setTokenAcquirer } from '../api/client'

interface AuthUser {
  name: string
  email: string
  roles: string[]
  isAdmin: boolean
}

interface AuthContextType {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  logout: () => void
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  logout: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const { instance, accounts, inProgress } = useMsal()
  const isAuthenticated = useIsAuthenticated()
  const [user, setUser] = useState<AuthUser | null>(null)

  // Auto-trigger login redirect if not authenticated
  const { error } = useMsalAuthentication(InteractionType.Redirect, loginRequest)

  const getAccessToken = useCallback(async (): Promise<string> => {
    if (accounts.length === 0) throw new Error('No account')
    const response = await instance.acquireTokenSilent({
      ...loginRequest,
      account: accounts[0],
    })
    return response.accessToken
  }, [instance, accounts])

  useEffect(() => {
    if (isAuthenticated && accounts.length > 0) {
      const account = accounts[0]
      const claims = account.idTokenClaims as Record<string, unknown> | undefined
      const roles = (claims?.roles as string[]) ?? []

      setUser({
        name: account.name ?? '',
        email: account.username ?? '',
        roles,
        isAdmin: roles.includes('Admin'),
      })

      // Wire up the token acquirer so Axios can inject Bearer tokens
      setTokenAcquirer(getAccessToken)
    }
  }, [isAuthenticated, accounts, getAccessToken])

  const logout = () => {
    instance.logoutRedirect()
  }

  // Show loading while MSAL is handling login/redirect
  if (inProgress !== InteractionStatus.None) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Signing in...</div>
      </div>
    )
  }

  // If not authenticated and no interaction in progress, MSAL will redirect
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Redirecting to sign in...</div>
      </div>
    )
  }

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, isLoading: false, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
