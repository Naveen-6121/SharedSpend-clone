import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { AuthProvider } from '@/context/AuthContext'
import { GroupProvider } from '@/context/GroupContext'
import { RequireAuth } from '@/components/RequireAuth'
import { AppShell } from '@/components/AppShell'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { LoginPage } from '@/pages/LoginPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { TransactionsPage } from '@/pages/TransactionsPage'
import { TransactionFormPage } from '@/pages/TransactionFormPage'
import { AnalyticsPage } from '@/pages/AnalyticsPage'
import { SettlementPage } from '@/pages/SettlementPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { GroupSettingsPage, CreateGroupPage } from '@/pages/GroupPages'
import { CategoriesPage } from '@/pages/CategoriesPage'
import { ProfilePage } from '@/pages/ProfilePage'
import { NotFoundPage } from '@/pages/NotFoundPage'

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
          <Route path="/groups/new" element={<CreateGroupPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AppShell>
    </GroupProvider>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
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
          </BrowserRouter>
          <Toaster richColors position="top-right" closeButton />
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
