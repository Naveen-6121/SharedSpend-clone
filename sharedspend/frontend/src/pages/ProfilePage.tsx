import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { ArrowLeft } from 'lucide-react'
import { usersApi } from '@/api'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { parseApiError } from '@/lib/format'

const profileSchema = z.object({
  display_name: z.string().min(1, 'Required'),
  email: z.string().email('Invalid email'),
})
const passwordSchema = z.object({
  old_password: z.string().min(1),
  new_password: z.string().min(8, 'At least 8 characters'),
  confirm: z.string(),
}).refine((d) => d.new_password === d.confirm, { message: 'Passwords do not match', path: ['confirm'] })

type ProfileForm = z.infer<typeof profileSchema>
type PasswordForm = z.infer<typeof passwordSchema>

export function ProfilePage() {
  const { user, refreshUser, logout } = useAuth()
  const [profileOk, setProfileOk] = useState(false)
  const [pwOk, setPwOk] = useState(false)

  const profileForm = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    values: user ? { display_name: user.display_name, email: user.email } : undefined,
  })

  const pwForm = useForm<PasswordForm>({ resolver: zodResolver(passwordSchema) })

  const profileMutation = useMutation({
    mutationFn: (d: ProfileForm) => usersApi.update(d),
    onSuccess: async () => {
      await refreshUser()
      setProfileOk(true)
      toast.success('Profile updated')
    },
    onError: (err) => toast.error(parseApiError(err)),
  })

  const pwMutation = useMutation({
    mutationFn: ({ old_password, new_password }: PasswordForm) =>
      usersApi.changePassword({ old_password, new_password }),
    onSuccess: () => {
      pwForm.reset()
      setPwOk(true)
      toast.success('Password changed. Please log in again.')
      setTimeout(() => logout(), 1500)
    },
    onError: (err) => toast.error(parseApiError(err)),
  })

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ml-2 gap-1 text-muted-foreground">
        <Link to="/settings"><ArrowLeft className="h-4 w-4" />Back to Settings</Link>
      </Button>
      <h1 className="text-2xl font-semibold">Profile</h1>

      <Card>
        <CardHeader><CardTitle className="text-base">Account Details</CardTitle></CardHeader>
        <CardContent>
          <div className="mb-4">
            <p className="text-sm text-muted-foreground">Username</p>
            <p className="font-medium">@{user?.username}</p>
          </div>
          <Separator className="mb-4" />
          <form onSubmit={profileForm.handleSubmit((d) => profileMutation.mutate(d))} className="space-y-4">
            <div className="space-y-1">
              <Label>Display Name</Label>
              <Input {...profileForm.register('display_name')} />
              {profileForm.formState.errors.display_name && (
                <p className="text-xs text-destructive">{profileForm.formState.errors.display_name.message}</p>
              )}
            </div>
            <div className="space-y-1">
              <Label>Email</Label>
              <Input type="email" {...profileForm.register('email')} />
              {profileForm.formState.errors.email && (
                <p className="text-xs text-destructive">{profileForm.formState.errors.email.message}</p>
              )}
            </div>
            {profileOk && <p className="text-sm text-green-600">Profile saved ✓</p>}
            <Button type="submit" loading={profileMutation.isPending}>Save Profile</Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Change Password</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={pwForm.handleSubmit((d) => pwMutation.mutate(d))} className="space-y-4">
            {([
              { id: 'old_password', label: 'Current Password' },
              { id: 'new_password', label: 'New Password' },
              { id: 'confirm', label: 'Confirm New Password' },
            ] as const).map(({ id, label }) => (
              <div key={id} className="space-y-1">
                <Label>{label}</Label>
                <Input type="password" {...pwForm.register(id)} />
                {pwForm.formState.errors[id] && (
                  <p className="text-xs text-destructive">{pwForm.formState.errors[id]?.message}</p>
                )}
              </div>
            ))}
            {pwOk && <p className="text-sm text-green-600">Password changed ✓</p>}
            <Button type="submit" loading={pwMutation.isPending}>Change Password</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
