import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function AdminPage() {
  const queryClient = useQueryClient()
  const users = useQuery({ queryKey: ['admin', 'users'], queryFn: adminApi.users })
  const database = useQuery({ queryKey: ['admin', 'database'], queryFn: adminApi.database })
  const changeStatus = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      adminApi.setUserActive(id, is_active),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
  })

  const activeAdminCount = users.data?.filter((user) => user.is_admin && user.is_active).length ?? 0

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Administration</h1>

      <Card>
        <CardHeader><CardTitle>Database status</CardTitle></CardHeader>
        <CardContent>
          {database.isLoading ? <p>Checking database…</p> : database.data == null ? (
            <p role="alert">Database status could not be loaded.</p>
          ) : (
            <dl className="grid gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-sm text-muted-foreground">Connection</dt>
                <dd><Badge variant={database.data.database_connected ? 'default' : 'destructive'}>
                  {database.data.database_connected ? 'Connected' : 'Unavailable'}
                </Badge></dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">Migrations</dt>
                <dd><Badge variant={database.data.migrations_current ? 'default' : 'secondary'}>
                  {database.data.migrations_current ? 'Up to date' : 'Pending or uninitialized'}
                </Badge></dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">Applied revision</dt>
                <dd>{database.data.current_revisions.join(', ') || 'None recorded'}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">Application revision</dt>
                <dd>{database.data.head_revisions.join(', ') || 'Unavailable'}</dd>
              </div>
            </dl>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>User management</CardTitle></CardHeader>
        <CardContent>
          {users.isLoading ? <p>Loading users…</p> : users.data == null ? (
            <p role="alert">Users could not be loaded.</p>
          ) : users.data.length === 0 ? <p>No users found.</p> : (
            <div className="divide-y">
              {users.data.map((user) => {
                const isLastAdmin = user.is_admin && user.is_active && activeAdminCount <= 1
                return (
                  <div key={user.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <div>
                      <p className="font-medium">{user.display_name || user.username}</p>
                      <p className="text-sm text-muted-foreground">@{user.username}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {user.is_admin && <Badge variant="secondary">Admin</Badge>}
                      <Badge variant={user.is_active ? 'default' : 'destructive'}>
                        {user.is_active ? 'Active' : 'Disabled'}
                      </Badge>
                      <Button
                        size="sm"
                        variant={user.is_active ? 'outline' : 'default'}
                        disabled={changeStatus.isPending || isLastAdmin}
                        onClick={() => changeStatus.mutate({ id: user.id, is_active: !user.is_active })}
                      >
                        {user.is_active ? 'Disable' : 'Enable'}
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
          {changeStatus.isError && <p className="mt-3 text-sm text-destructive" role="alert">
            User status could not be updated.
          </p>}
        </CardContent>
      </Card>
    </div>
  )
}
