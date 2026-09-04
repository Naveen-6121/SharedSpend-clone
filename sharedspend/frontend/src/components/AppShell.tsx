import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, ArrowLeftRight, BarChart2, Settings, LogOut, ChevronDown, PlusCircle, Check
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/context/AuthContext'
import { useGroup } from '@/context/GroupContext'
import { Button } from '@/components/ui/button'
import type { GroupOut } from '@/types'
import { cn } from '@/lib/utils'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/transactions', icon: ArrowLeftRight, label: 'Transactions' },
  { to: '/analytics', icon: BarChart2, label: 'Analytics' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const { groups, activeGroup, setActiveGroup } = useGroup()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const switchGroup = (g: GroupOut) => {
    setActiveGroup(g)
    // Invalidate all group-specific queries so data refreshes immediately
    qc.invalidateQueries({ queryKey: ['analytics'] })
    qc.invalidateQueries({ queryKey: ['transactions'] })
    qc.invalidateQueries({ queryKey: ['budget'] })
    qc.invalidateQueries({ queryKey: ['group-members'] })
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* ── Desktop sidebar ─────────────────────────────────────── */}
      <aside className="hidden md:flex md:w-60 md:flex-col border-r bg-card">
        {/* Logo */}
        <div className="flex h-14 items-center px-4 border-b">
          <span className="font-semibold text-primary text-lg">SharedSpend</span>
        </div>

        {/* Group switcher */}
        <div className="px-3 py-2 border-b">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="w-full justify-between text-sm h-9 px-2">
                <span className="truncate">{activeGroup?.name ?? 'No group'}</span>
                <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-52">
              <DropdownMenuLabel>Your Groups</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {groups.map((g) => (
                <DropdownMenuItem key={g.id} onClick={() => switchGroup(g)}
                  className={cn('flex items-center gap-2', activeGroup?.id === g.id && 'font-medium')}>
                  <Check className={cn('h-4 w-4 shrink-0', activeGroup?.id === g.id ? 'opacity-100' : 'opacity-0')} />
                  {g.name}
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => navigate('/groups/new')}>
                <PlusCircle className="mr-2 h-4 w-4" /> New Group
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Nav links */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) => cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
              )}>
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User footer */}
        <div className="border-t px-3 py-3">
          <div className="flex items-center justify-between">
            <div className="text-sm">
              <p className="font-medium truncate">{user?.display_name}</p>
              <p className="text-muted-foreground text-xs truncate">{user?.username}</p>
            </div>
            <Button variant="ghost" size="icon" onClick={logout} title="Logout">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile header */}
        <header className="md:hidden flex h-14 items-center justify-between border-b px-4">
          <span className="font-semibold text-primary">SharedSpend</span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="gap-1 text-xs">
                {activeGroup?.name ?? 'No group'} <ChevronDown className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {groups.map((g) => (
                <DropdownMenuItem key={g.id} onClick={() => switchGroup(g)}
                  className={cn('flex items-center gap-2', activeGroup?.id === g.id && 'font-medium')}>
                  <Check className={cn('h-4 w-4 shrink-0', activeGroup?.id === g.id ? 'opacity-100' : 'opacity-0')} />
                  {g.name}
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => navigate('/groups/new')}>
                <PlusCircle className="mr-2 h-4 w-4" /> New Group
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          {children}
        </main>

        {/* Mobile bottom nav */}
        <nav className="md:hidden flex border-t bg-card">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) => cn(
                'flex flex-1 flex-col items-center gap-1 py-2 text-xs font-medium transition-colors',
                isActive ? 'text-primary' : 'text-muted-foreground',
              )}>
              <Icon className="h-5 w-5" />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}
