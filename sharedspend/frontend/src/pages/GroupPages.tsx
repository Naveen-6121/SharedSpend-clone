import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate, Link } from 'react-router-dom'
import { toast } from 'sonner'
import { UserMinus, Crown, ArrowLeft } from 'lucide-react'
import { groupsApi, budgetsApi } from '@/api'
import { useGroup } from '@/context/GroupContext'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { formatINR, parseApiError, currentYear, currentMonth, monthName } from '@/lib/format'

// ─── Create Group ──────────────────────────────────────────────────────────────
const createSchema = z.object({ name: z.string().min(1), description: z.string().optional() })
type CreateForm = z.infer<typeof createSchema>

export function CreateGroupPage() {
  const qc = useQueryClient()
  const { reloadGroups, setActiveGroup } = useGroup()
  const navigate = useNavigate()
  const { register, handleSubmit, formState: { errors } } = useForm<CreateForm>({ resolver: zodResolver(createSchema) })

  const mutation = useMutation({
    mutationFn: groupsApi.create,
    onSuccess: async (group) => {
      toast.success('Group created!')
      await reloadGroups()
      setActiveGroup(group)
      qc.invalidateQueries({ queryKey: ['groups'] })
      navigate('/')
    },
    onError: (err) => toast.error(parseApiError(err)),
  })

  return (
    <div className="max-w-md mx-auto">
      <Card>
        <CardHeader><CardTitle>Create a Group</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit((d) => mutation.mutate(d))} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="name">Group Name</Label>
              <Input id="name" {...register('name')} placeholder="e.g. Home, Roommates" />
              {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="description">Description (optional)</Label>
              <Input id="description" {...register('description')} />
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="outline" className="flex-1" onClick={() => navigate(-1)}>Cancel</Button>
              <Button type="submit" className="flex-1" loading={mutation.isPending}>Create Group</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

// ─── Group Settings ────────────────────────────────────────────────────────────
const budgetSchema = z.object({ amount: z.coerce.number().positive('Must be positive') })
const inviteSchema = z.object({ username: z.string().min(1, 'Username required') })
const renameSchema = z.object({ name: z.string().min(1), description: z.string().optional() })

export function GroupSettingsPage() {
  const { activeGroup, isOwner, reloadGroups } = useGroup()
  const { user } = useAuth()
  const qc = useQueryClient()
  const [removingId, setRemovingId] = useState<string | null>(null)
  const year = currentYear()
  const month = currentMonth()

  // Members
  const { data: members, isLoading: membersLoading } = useQuery({
    queryKey: ['group-members', activeGroup?.id],
    queryFn: () => groupsApi.members(activeGroup!.id),
    enabled: !!activeGroup,
  })

  // Budget
  const { data: budget, isLoading: budgetLoading } = useQuery({
    queryKey: ['budget', activeGroup?.id, year, month],
    queryFn: () => budgetsApi.get(activeGroup!.id, year, month),
    enabled: !!activeGroup,
    retry: false,
  })

  // Invite form
  const inviteForm = useForm<{ username: string }>({ resolver: zodResolver(inviteSchema) })
  const inviteMutation = useMutation({
    mutationFn: (d: { username: string }) => groupsApi.invite(activeGroup!.id, d),
    onSuccess: () => {
      toast.success('Member invited!')
      inviteForm.reset()
      qc.invalidateQueries({ queryKey: ['group-members', activeGroup?.id] })
    },
    onError: (err) => toast.error(parseApiError(err)),
  })

  // Budget form
  const budgetForm = useForm<{ amount: number }>({
    resolver: zodResolver(budgetSchema),
    values: budget ? { amount: budget.amount } : undefined,
  })
  const budgetMutation = useMutation({
    mutationFn: (d: { amount: number }) => budgetsApi.upsert(activeGroup!.id, { year, month, amount: d.amount }),
    onSuccess: () => {
      toast.success('Budget saved!')
      qc.invalidateQueries({ queryKey: ['budget', activeGroup?.id, year, month] })
      qc.invalidateQueries({ queryKey: ['analytics'] })
    },
    onError: (err) => toast.error(parseApiError(err)),
  })

  // Rename form
  const renameForm = useForm<{ name: string; description?: string }>({
    resolver: zodResolver(renameSchema),
    values: activeGroup ? { name: activeGroup.name, description: activeGroup.description ?? '' } : undefined,
  })
  const renameMutation = useMutation({
    mutationFn: (d: { name: string; description?: string }) => groupsApi.update(activeGroup!.id, d),
    onSuccess: async () => {
      toast.success('Group updated!')
      await reloadGroups()
      qc.invalidateQueries({ queryKey: ['groups'] })
    },
    onError: (err) => toast.error(parseApiError(err)),
  })

  // Remove member
  const removeMutation = useMutation({
    mutationFn: (userId: string) => groupsApi.removeMember(activeGroup!.id, userId),
    onSuccess: () => {
      toast.success('Member removed')
      setRemovingId(null)
      qc.invalidateQueries({ queryKey: ['group-members', activeGroup?.id] })
    },
    onError: (err) => toast.error(parseApiError(err)),
  })

  if (!activeGroup) return <p className="text-muted-foreground text-center py-12">No active group</p>

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild className="-ml-2 gap-1 text-muted-foreground">
          <Link to="/settings"><ArrowLeft className="h-4 w-4" />Back to Settings</Link>
        </Button>
      </div>
      <h1 className="text-2xl font-semibold">Group Settings</h1>

      {/* Rename group */}
      {isOwner && (
        <Card>
          <CardHeader><CardTitle className="text-base">Group Details</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={renameForm.handleSubmit((d) => renameMutation.mutate(d))} className="space-y-3">
              <div className="space-y-1">
                <Label>Name</Label>
                <Input {...renameForm.register('name')} />
              </div>
              <div className="space-y-1">
                <Label>Description</Label>
                <Input {...renameForm.register('description')} />
              </div>
              <Button type="submit" size="sm" loading={renameMutation.isPending}>Save</Button>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Monthly budget */}
      <Card>
        <CardHeader><CardTitle className="text-base">Monthly Budget — {monthName(month)} {year}</CardTitle></CardHeader>
        <CardContent>
          {budgetLoading ? <Skeleton className="h-10 w-full" /> : (
            <>
              {budget && <p className="text-sm text-muted-foreground mb-3">Current: <strong>{formatINR(budget.amount)}</strong></p>}
              {isOwner && (
                <form onSubmit={budgetForm.handleSubmit((d) => budgetMutation.mutate(d))} className="flex gap-2">
                  <Input type="number" min="0.01" step="0.01" placeholder="Amount (₹)" className="flex-1"
                    {...budgetForm.register('amount')} />
                  <Button type="submit" loading={budgetMutation.isPending}>
                    {budget ? 'Update' : 'Set Budget'}
                  </Button>
                </form>
              )}
              {!budget && !isOwner && <p className="text-sm text-muted-foreground">No budget set for this month</p>}
            </>
          )}
        </CardContent>
      </Card>

      {/* Members */}
      <Card>
        <CardHeader><CardTitle className="text-base">Members</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {membersLoading
            ? Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)
            : members?.map((m) => {
              const displayName = m.display_name || m.username || m.user_id
              const initial = displayName[0].toUpperCase()
              return (
                <div key={m.id} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-medium text-primary">
                      {initial}
                    </div>
                    <div>
                      <p className="text-sm font-medium flex items-center gap-1">
                        {displayName}
                        {m.role === 'OWNER' && <Crown className="h-3 w-3 text-yellow-500" />}
                      </p>
                      {m.username && m.username !== displayName && (
                        <p className="text-xs text-muted-foreground">@{m.username}</p>
                      )}
                      <p className="text-xs text-muted-foreground">Member since {new Date(m.joined_at).toLocaleDateString()}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={m.role === 'OWNER' ? 'default' : 'secondary'}>{m.role}</Badge>
                    {isOwner && m.user_id !== user?.id && (
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive"
                        onClick={() => setRemovingId(m.user_id)}>
                        <UserMinus className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                </div>
              )
            })
          }

          {isOwner && (
            <>
              <Separator />
              <form onSubmit={inviteForm.handleSubmit((d) => inviteMutation.mutate(d))} className="flex gap-2">
                <Input placeholder="Username to invite" className="flex-1" {...inviteForm.register('username')} />
                <Button type="submit" loading={inviteMutation.isPending}>Invite</Button>
              </form>
              {inviteForm.formState.errors.username && (
                <p className="text-xs text-destructive">{inviteForm.formState.errors.username.message}</p>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Confirm remove member */}
      <AlertDialog open={!!removingId} onOpenChange={() => setRemovingId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove member?</AlertDialogTitle>
            <AlertDialogDescription>This member will lose access to the group.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => removingId && removeMutation.mutate(removingId)}>
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
