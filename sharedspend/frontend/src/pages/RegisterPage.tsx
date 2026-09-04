import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { parseApiError } from '@/lib/format'

const schema = z.object({
  username: z.string().min(3, 'At least 3 characters').max(50),
  email: z.string().email('Invalid email'),
  display_name: z.string().min(1, 'Display name is required'),
  password: z.string().min(8, 'At least 8 characters'),
  confirm_password: z.string(),
}).refine((d) => d.password === d.confirm_password, {
  message: 'Passwords do not match',
  path: ['confirm_password'],
})
type Form = z.infer<typeof schema>

export function RegisterPage() {
  const { register: authRegister } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)

  const { register, handleSubmit, formState: { errors } } = useForm<Form>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async ({ confirm_password: _, ...data }: Form) => {
    setLoading(true)
    try {
      await authRegister(data)
      toast.success('Account created!')
      navigate('/', { replace: true })
    } catch (err) {
      toast.error(parseApiError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4 bg-muted/30">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Create Account</CardTitle>
          <CardDescription>Join SharedSpend today</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {([
              { id: 'username', label: 'Username', type: 'text', ac: 'username' },
              { id: 'email', label: 'Email', type: 'email', ac: 'email' },
              { id: 'display_name', label: 'Display Name', type: 'text', ac: 'name' },
              { id: 'password', label: 'Password', type: 'password', ac: 'new-password' },
              { id: 'confirm_password', label: 'Confirm Password', type: 'password', ac: 'new-password' },
            ] as const).map(({ id, label, type, ac }) => (
              <div key={id} className="space-y-1">
                <Label htmlFor={id}>{label}</Label>
                <Input id={id} type={type} autoComplete={ac} {...register(id)} />
                {errors[id] && <p className="text-xs text-destructive">{errors[id]?.message}</p>}
              </div>
            ))}
            <Button type="submit" className="w-full" loading={loading}>Create Account</Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link to="/login" className="text-primary underline-offset-4 hover:underline">Sign in</Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
