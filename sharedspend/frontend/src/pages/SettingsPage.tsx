import { Link } from 'react-router-dom'
import { Settings, Users, Tag, User } from 'lucide-react'
import { useGroup } from '@/context/GroupContext'
import { useAuth } from '@/context/AuthContext'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

const settingsItems = [
  { to: '/settings/group', icon: Users, label: 'Group Settings', desc: 'Members, budget, invite' },
  { to: '/settings/categories', icon: Tag, label: 'Categories', desc: 'Manage spending categories' },
  { to: '/settings/profile', icon: User, label: 'Profile', desc: 'Display name, email, password' },
]

export function SettingsPage() {
  const { activeGroup } = useGroup()
  const { logout } = useAuth()

  return (
    <div className="max-w-lg mx-auto space-y-4">
      <h1 className="text-2xl font-semibold flex items-center gap-2"><Settings className="h-5 w-5" />Settings</h1>
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
