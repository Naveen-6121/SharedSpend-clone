import { Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  return user?.is_admin ? <>{children}</> : <Navigate to="/" replace />
}
