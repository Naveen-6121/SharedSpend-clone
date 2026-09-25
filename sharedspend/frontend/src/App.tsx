import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { AuthProvider } from '@/context/AuthContext'
import { GroupProvider } from '@/context/GroupContext'
import { RequireAuth } from '@/components/RequireAuth'
import { RequireAdmin } from '@/components/RequireAdmin'
import { AppShell } from '@/components/AppShell'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ThemeProvider } from '@/context/ThemeContext'

const LoginPage = lazy(() => import('@/pages/LoginPage').then((page) => ({ default: page.LoginPage })))
const RegisterPage = lazy(() => import('@/pages/RegisterPage').then((page) => ({ default: page.RegisterPage })))
const DashboardPage = lazy(() => import('@/pages/DashboardPage').then((page) => ({ default: page.DashboardPage })))
const TransactionsPage = lazy(() => import('@/pages/TransactionsPage').then((page) => ({ default: page.TransactionsPage })))
const TransactionFormPage = lazy(() => import('@/pages/TransactionFormPage').then((page) => ({ default: page.TransactionFormPage })))
const AnalyticsPage = lazy(() => import('@/pages/AnalyticsPage').then((page) => ({ default: page.AnalyticsPage })))
const SettlementPage = lazy(() => import('@/pages/SettlementPage').then((page) => ({ default: page.SettlementPage })))
const SettingsPage = lazy(() => import('@/pages/SettingsPage').then((page) => ({ default: page.SettingsPage })))
const GroupSettingsPage = lazy(() => import('@/pages/GroupPages').then((page) => ({ default: page.GroupSettingsPage })))
const CreateGroupPage = lazy(() => import('@/pages/GroupPages').then((page) => ({ default: page.CreateGroupPage })))
const CategoriesPage = lazy(() => import('@/pages/CategoriesPage').then((page) => ({ default: page.CategoriesPage })))
const ProfilePage = lazy(() => import('@/pages/ProfilePage').then((page) => ({ default: page.ProfilePage })))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage').then((page) => ({ default: page.NotFoundPage })))
const AdminPage = lazy(() => import('@/pages/AdminPage').then((page) => ({ default: page.AdminPage })))

function RouteLoading() {
  return <div role="status" className="p-6 text-sm text-muted-foreground">Loading page…</div>
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failCount, error: unknown) => {
        const status = (error as { response?: { status?: number } })?.response?.status
        if (status === 401 || status === 403 || status === 404) return false
        return failCount < 2
      },
    },
  },
})

function AuthenticatedApp() {
  return (
      <GroupProvider>
        <AppShell>
        <Suspense fallback={<RouteLoading />}>
          <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/transactions/new" element={<TransactionFormPage />} />
          <Route path="/transactions/:id/edit" element={<TransactionFormPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/settlement" element={<SettlementPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/settings/group" element={<GroupSettingsPage />} />
          <Route path="/settings/categories" element={<CategoriesPage />} />
          <Route path="/settings/profile" element={<ProfilePage />} />
          <Route path="/admin" element={<RequireAdmin><AdminPage /></RequireAdmin>} />
          <Route path="/groups/new" element={<CreateGroupPage />} />
          <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </AppShell>
    </GroupProvider>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <AuthProvider>
            <BrowserRouter>
              <Suspense fallback={<RouteLoading />}>
                <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="*" element={
                <RequireAuth>
                  <ErrorBoundary>
                    <AuthenticatedApp />
                  </ErrorBoundary>
                </RequireAuth>
              } />
                </Routes>
              </Suspense>
            </BrowserRouter>
            <Toaster richColors position="top-right" closeButton />
          </AuthProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
