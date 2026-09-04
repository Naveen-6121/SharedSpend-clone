import { useEffect, useState, useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, useParams } from 'react-router-dom'
import { Sparkles, ArrowLeft } from 'lucide-react'
import {
  useTransaction, useCreateTransaction, useUpdateTransaction,
  useCategories, useCategorize, useGroupMembers,
} from '@/hooks/useApi'
import { useGroup } from '@/context/GroupContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { PageSpinner } from '@/components/Spinner'
import { todayISO } from '@/lib/format'
import type { TransactionType } from '@/types'

const schema = z.object({
  description: z.string().min(1, 'Description is required').max(500),
  amount: z.coerce.number({ invalid_type_error: 'Enter a valid amount' }).positive('Must be greater than 0'),
  date: z.string().min(1, 'Date is required'),
  type: z.enum(['SHARED', 'PERSONAL']),
  category_id: z.string().optional().nullable(),
  group_id: z.string().optional().nullable(),
  payer_id: z.string().optional().nullable(),
  notes: z.string().max(1000).optional().nullable(),
  add_to_settlement: z.boolean(),
}).superRefine((d, ctx) => {
  if (d.type === 'SHARED' && !d.group_id) {
    ctx.addIssue({ code: 'custom', path: ['group_id'], message: 'Group is required for shared transactions' })
  }
  if (d.type === 'PERSONAL' && !d.payer_id) {
    ctx.addIssue({ code: 'custom', path: ['payer_id'], message: 'Payer is required for personal transactions' })
  }
})
type Form = z.infer<typeof schema>

export function TransactionFormPage() {
  const { id } = useParams<{ id?: string }>()
  const isEdit = !!id
  const navigate = useNavigate()
  const { activeGroup } = useGroup()

  const [suggestion, setSuggestion] = useState<{ name: string; id: string } | null>(null)
  const [debounceTimer, setDebounceTimer] = useState<ReturnType<typeof setTimeout> | null>(null)
  // participant IDs for settlement split (all group members by default)
  const [participantIds, setParticipantIds] = useState<Set<string>>(new Set())

  const { data: existing, isLoading: loadingTx } = useTransaction(id)
  const { data: categories } = useCategories(activeGroup?.id)
  const categorizeMutation = useCategorize()
  const createMutation = useCreateTransaction()
  const updateMutation = useUpdateTransaction(id ?? '')

  const { register, handleSubmit, watch, setValue, reset, formState: { errors } } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: {
      description: '',
      amount: undefined,
      date: todayISO(),
      type: 'SHARED',
      category_id: null,
      group_id: activeGroup?.id ?? null,
      payer_id: null,
      notes: null,
      add_to_settlement: false,
    },
  })

  const txType = watch('type') as TransactionType
  const groupId = watch('group_id')
  const description = watch('description')
  const selectedCategoryId = watch('category_id')
  const addToSettlement = watch('add_to_settlement')

  // Populate form for edit
  useEffect(() => {
    if (existing) {
      reset({
        description: existing.description,
        amount: existing.amount,
        date: existing.date,
        type: existing.type,
        category_id: existing.category_id,
        group_id: existing.group_id,
        payer_id: existing.payer_id,
        notes: existing.notes,
        add_to_settlement: existing.add_to_settlement ?? false,
      })
    }
  }, [existing, reset])

  // When type switches, update dependent fields
  useEffect(() => {
    if (txType === 'SHARED') {
      // SHARED: no payer, set group
      setValue('payer_id', null)
      if (!groupId && activeGroup) setValue('group_id', activeGroup.id)
      setValue('add_to_settlement', false) // not applicable to SHARED
    } else {
      // PERSONAL: no group
      setValue('group_id', null)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [txType])

  // Load group members for PERSONAL payer selector + settlement participants
  const { data: members } = useGroupMembers(txType === 'PERSONAL' ? (activeGroup?.id ?? undefined) : undefined)

  // When members load, default all members as participants
  useEffect(() => {
    if (members && members.length > 0) {
      setParticipantIds(new Set(members.map((m) => m.user_id)))
    }
  }, [members])

  // Smart categorize with debounce
  const suggestCategory = useCallback(async (desc: string) => {
    if (desc.length < 2) { setSuggestion(null); return }
    try {
      const res = await categorizeMutation.mutateAsync({ description: desc })
      if (res.category_id && res.category_name) {
        setSuggestion({ name: res.category_name, id: res.category_id })
      } else {
        setSuggestion(null)
      }
    } catch { setSuggestion(null) }
  }, [categorizeMutation])

  useEffect(() => {
    if (debounceTimer) clearTimeout(debounceTimer)
    if (!description) { setSuggestion(null); return }
    const t = setTimeout(() => suggestCategory(description), 700)
    setDebounceTimer(t)
    return () => clearTimeout(t)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [description])

  const onSubmit = (data: Form) => {
    const payload = {
      description: data.description,
      amount: data.amount,
      date: data.date,
      type: data.type,
      // SHARED: no payer, has group; PERSONAL: has payer, no group
      group_id: data.type === 'SHARED' ? (data.group_id || null) : null,
      payer_id: data.type === 'PERSONAL' ? (data.payer_id || null) : null,
      category_id: data.category_id || null,
      notes: data.notes || null,
      add_to_settlement: data.type === 'PERSONAL' ? (data.add_to_settlement ?? false) : false,
    }
    if (isEdit) {
      updateMutation.mutate(payload, { onSuccess: () => navigate('/transactions') })
    } else {
      createMutation.mutate(payload, { onSuccess: () => navigate('/transactions') })
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  if (isEdit && loadingTx) return <PageSpinner />

  return (
    <div className="max-w-lg mx-auto">
      <Button variant="ghost" size="sm" className="mb-4 -ml-2 gap-1 text-muted-foreground"
        onClick={() => navigate(-1)}>
        <ArrowLeft className="h-4 w-4" /> Back
      </Button>
      <Card>
        <CardHeader>
          <CardTitle>{isEdit ? 'Edit Transaction' : 'Add Transaction'}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>

            {/* Description */}
            <div className="space-y-1">
              <Label htmlFor="description">Description *</Label>
              <div className="relative">
                <Input
                  id="description"
                  autoFocus
                  aria-required="true"
                  aria-describedby={errors.description ? 'desc-error' : undefined}
                  {...register('description')}
                />
                {categorizeMutation.isPending && (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground animate-pulse">
                    ✦
                  </span>
                )}
              </div>
              {errors.description && (
                <p id="desc-error" className="text-xs text-destructive" role="alert">{errors.description.message}</p>
              )}
              {/* Smart categorization suggestion */}
              {suggestion && selectedCategoryId !== suggestion.id && (
                <div className="flex items-center gap-2 mt-1 p-2 rounded-md bg-primary/5 border border-primary/20">
                  <Sparkles className="h-3.5 w-3.5 text-primary shrink-0" aria-hidden="true" />
                  <span className="text-xs text-muted-foreground">Suggested category:</span>
                  <Badge
                    variant="outline"
                    className="text-xs cursor-pointer hover:bg-accent focus-visible:ring-2"
                    tabIndex={0}
                    role="button"
                    aria-label={`Accept suggestion: ${suggestion.name}`}
                    onClick={() => setValue('category_id', suggestion.id)}
                    onKeyDown={(e) => e.key === 'Enter' && setValue('category_id', suggestion.id)}>
                    {suggestion.name}
                  </Badge>
                  <button
                    type="button"
                    className="text-xs text-muted-foreground hover:text-foreground ml-auto"
                    aria-label="Dismiss suggestion"
                    onClick={() => setSuggestion(null)}>
                    ✕
                  </button>
                </div>
              )}
            </div>

            {/* Amount + Date */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label htmlFor="amount">Amount (₹) *</Label>
                <Input
                  id="amount"
                  type="number"
                  step="0.01"
                  min="0.01"
                  inputMode="decimal"
                  aria-required="true"
                  aria-describedby={errors.amount ? 'amount-error' : undefined}
                  {...register('amount')}
                />
                {errors.amount && (
                  <p id="amount-error" className="text-xs text-destructive" role="alert">{errors.amount.message}</p>
                )}
              </div>
              <div className="space-y-1">
                <Label htmlFor="date">Date *</Label>
                <Input
                  id="date"
                  type="date"
                  aria-required="true"
                  {...register('date')}
                />
                {errors.date && (
                  <p className="text-xs text-destructive" role="alert">{errors.date.message}</p>
                )}
              </div>
            </div>

            {/* Type toggle */}
            <fieldset className="space-y-1">
              <legend className="text-sm font-medium leading-none">Type</legend>
              <div className="flex gap-2 mt-1" role="group" aria-label="Transaction type">
                {(['SHARED', 'PERSONAL'] as TransactionType[]).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setValue('type', t)}
                    aria-pressed={txType === t}
                    className={`flex-1 rounded-md border py-2 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
                      txType === t
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'border-input hover:bg-accent'
                    }`}>
                    {t === 'SHARED' ? '🤝 Shared' : '👤 Personal'}
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {txType === 'SHARED'
                  ? 'Shared expenses come from the group budget. No individual payer.'
                  : 'Personal expenses are paid by one person and can be included in settlement.'}
              </p>
            </fieldset>

            {/* PERSONAL only: Payer selector */}
            {txType === 'PERSONAL' && (
              <div className="space-y-1">
                <Label htmlFor="payer">Paid by *</Label>
                <Select
                  value={watch('payer_id') ?? ''}
                  onValueChange={(v) => setValue('payer_id', v || null)}
                >
                  <SelectTrigger id="payer" aria-required="true"
                    aria-describedby={errors.payer_id ? 'payer-error' : undefined}>
                    <SelectValue placeholder="Who paid?" />
                  </SelectTrigger>
                  <SelectContent>
                    {!members?.length
                      ? <SelectItem value="_none" disabled>No group members — join a group first</SelectItem>
                      : members.map((m) => (
                        <SelectItem key={m.user_id} value={m.user_id}>
                          {m.display_name || m.username || m.user_id}
                        </SelectItem>
                      ))
                    }
                  </SelectContent>
                </Select>
                {errors.payer_id && (
                  <p id="payer-error" className="text-xs text-destructive" role="alert">{errors.payer_id.message}</p>
                )}
              </div>
            )}

            {/* PERSONAL only: Add to settlement + participants */}
            {txType === 'PERSONAL' && (
              <div className="rounded-md border bg-muted/30 p-3 space-y-3">
                <div className="flex items-start gap-3">
                  <input
                    id="add_to_settlement"
                    type="checkbox"
                    className="mt-0.5 h-4 w-4 rounded border-input accent-primary cursor-pointer"
                    checked={addToSettlement}
                    onChange={(e) => setValue('add_to_settlement', e.target.checked)}
                    aria-describedby="settlement-hint"
                  />
                  <div>
                    <Label htmlFor="add_to_settlement" className="cursor-pointer font-medium">
                      Add to Settlement
                    </Label>
                    <p id="settlement-hint" className="text-xs text-muted-foreground mt-0.5">
                      Split this expense equally among selected group members.
                    </p>
                  </div>
                </div>

                {/* Participants — only visible when add_to_settlement is checked */}
                {addToSettlement && members && members.length > 0 && (
                  <div className="space-y-1 pl-7">
                    <p className="text-xs font-medium text-muted-foreground mb-1">Participants</p>
                    {members.map((m) => {
                      const name = m.display_name || m.username || m.user_id
                      const checked = participantIds.has(m.user_id)
                      const share = participantIds.size > 0
                        ? (watch('amount') || 0) / participantIds.size
                        : 0
                      return (
                        <div key={m.user_id} className="flex items-center justify-between text-sm">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              className="h-3.5 w-3.5 rounded border-input accent-primary"
                              checked={checked}
                              onChange={(e) => {
                                const next = new Set(participantIds)
                                if (e.target.checked) next.add(m.user_id)
                                else next.delete(m.user_id)
                                setParticipantIds(next)
                              }}
                            />
                            <span>{name}</span>
                          </label>
                          {checked && (
                            <span className="text-xs tabular-nums text-muted-foreground">
                              ₹{share.toFixed(2)}
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Category */}
            <div className="space-y-1">
              <Label htmlFor="category">Category</Label>
              <Select
                value={watch('category_id') ?? ''}
                onValueChange={(v) => { setValue('category_id', v || null); setSuggestion(null) }}
              >
                <SelectTrigger id="category">
                  <SelectValue placeholder="Select category (optional)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">None</SelectItem>
                  {categories?.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      <span className="mr-2" aria-hidden="true">{c.icon}</span>{c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Notes */}
            <div className="space-y-1">
              <Label htmlFor="notes">Notes (optional)</Label>
              <Textarea
                id="notes"
                placeholder="Any extra details…"
                rows={2}
                {...register('notes')}
              />
            </div>

            <div className="flex gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                className="flex-1"
                onClick={() => navigate(-1)}
                disabled={isPending}>
                Cancel
              </Button>
              <Button type="submit" className="flex-1" loading={isPending}>
                {isEdit ? 'Save Changes' : 'Add Transaction'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
