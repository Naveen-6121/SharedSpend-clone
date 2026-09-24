import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Settings, Users, Tag, User } from 'lucide-react'
import { useGroup } from '@/context/GroupContext'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/context/ThemeContext'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { budgetAlertsEnabled, setBudgetAlertsEnabled } from '@/lib/budgetNotifications'

const settingsItems = [
  { to: '/settings/group', icon: Users, label: 'Group Settings', desc: 'Members, budget, invite' },
  { to: '/settings/categories', icon: Tag, label: 'Categories', desc: 'Manage spending categories' },
  { to: '/settings/profile', icon: User, label: 'Profile', desc: 'Display name, email, password' },
]

export function SettingsPage() {
  const { activeGroup } = useGroup()
  const { logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [budgetAlerts, setBudgetAlerts] = useState(budgetAlertsEnabled)

  const toggleBudgetAlerts = async () => {
    if (budgetAlerts) {
      setBudgetAlertsEnabled(false)
      setBudgetAlerts(false)
      return
    }
    if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
      await Notification.requestPermission()
    }
    setBudgetAlertsEnabled(true)
    setBudgetAlerts(true)
  }

  return (
    <div className="max-w-lg mx-auto space-y-4">
      <h1 className="text-2xl font-semibold flex items-center gap-2"><Settings className="h-5 w-5" />Settings</h1>
      <Card>
        <CardContent className="flex items-center justify-between gap-4 pt-4">
          <div>
            <p className="text-sm font-medium">Appearance</p>
            <p className="text-xs text-muted-foreground">Choose a light or dark theme for this device.</p>
          </div>
          <Button type="button" variant="outline" aria-pressed={theme === 'dark'} onClick={toggleTheme}>
            {theme === 'dark' ? 'Dark mode' : 'Light mode'}
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="flex items-center justify-between gap-4 pt-4">
          <div>
            <p className="text-sm font-medium">Budget alerts</p>
            <p className="text-xs text-muted-foreground">Alert at 80% and 100% of the shared budget while this app is open.</p>
          </div>
          <Button type="button" variant="outline" aria-pressed={budgetAlerts} onClick={toggleBudgetAlerts}>
            {budgetAlerts ? 'Alerts on' : 'Alerts off'}
          </Button>
        </CardContent>
      </Card>
      {activeGroup && <p className="text-sm text-muted-foreground">Active group: <strong>{activeGroup.name}</strong></p>}
      <Card>
        <CardContent className="pt-4 divide-y">
          {settingsItems.map(({ to, icon: Icon, label, desc }) => (
            <Link key={to} to={to} className="flex items-center justify-between py-3 hover:text-primary transition-colors group">
              <div className="flex items-center gap-3">
                <Icon className="h-4 w-4 text-muted-foreground group-hover:text-primary" />
                <div>
                  <p className="text-sm font-medium">{label}</p>
                  <p className="text-xs text-muted-foreground">{desc}</p>
                </div>
              </div>
              <span className="text-muted-foreground text-lg">›</span>
            </Link>
          ))}
        </CardContent>
      </Card>
      <Separator />
      <Button variant="destructive" className="w-full" onClick={logout}>Sign Out</Button>
    </div>
  )
}
