import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return <div className="text-center py-12 text-gray-500">Loading...</div>
  }

  if (!user?.isAdmin) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
