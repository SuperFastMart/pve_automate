import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react'
import { useMsal, useIsAuthenticated, useMsalAuthentication } from '@azure/msal-react'
import { InteractionType } from '@azure/msal-browser'
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
  const { instance, accounts } = useMsal()
  const isAuthenticated = useIsAuthenticated()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Auto-trigger login redirect if not authenticated
  useMsalAuthentication(InteractionType.Redirect, loginRequest)

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
      setIsLoading(false)
    } else if (!isAuthenticated) {
      setIsLoading(false)
    }
  }, [isAuthenticated, accounts, getAccessToken])

  const logout = () => {
    instance.logoutRedirect()
  }

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, isLoading, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
