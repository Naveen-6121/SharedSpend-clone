import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Pencil, Trash2, Plus, X, Check, ArrowLeft } from 'lucide-react'
import { categoriesApi } from '@/api'
import { useGroup } from '@/context/GroupContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { parseApiError } from '@/lib/format'
import type { CategoryOut } from '@/types'

const categorySchema = z.object({
  name: z.string().min(1),
  icon: z.string().optional(),
})
type CategoryForm = z.infer<typeof categorySchema>

export function CategoriesPage() {
  const { activeGroup } = useGroup()
  const qc = useQueryClient()
  const [editing, setEditing] = useState<CategoryOut | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<CategoryOut | null>(null)
  const [reassignTo, setReassignTo] = useState('')

  const { data: categories, isLoading } = useQuery({
    queryKey: ['categories', activeGroup?.id],
    queryFn: () => categoriesApi.list(activeGroup?.id),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['categories'] })
    qc.invalidateQueries({ queryKey: ['transactions'] })
  }

  const createMutation = useMutation({
    mutationFn: (d: CategoryForm) => {
      if (!activeGroup) throw new Error('No active group')
      return categoriesApi.create(activeGroup.id, d)
    },
    onSuccess: () => { toast.success('Category created'); invalidate(); setCreating(false) },
    onError: (err) => toast.error(parseApiError(err)),
  })

  const updateMutation = useMutation({
    mutationFn: (d: CategoryForm) => categoriesApi.update(editing!.id, d),
    onSuccess: () => { toast.success('Category updated'); invalidate(); setEditing(null) },
    onError: (err) => toast.error(parseApiError(err)),
  })

  const deleteMutation = useMutation({
    /**
     * Delete with optional reassignment in a single request.
     * Backend DELETE /categories/{id} accepts { reassign_to_category_id } in the JSON body.
     */
    mutationFn: () => categoriesApi.delete(
      deleteTarget!.id,
      reassignTo ? { reassign_to_category_id: reassignTo } : {}
    ),
    onSuccess: () => { toast.success('Category deleted'); invalidate(); setDeleteTarget(null); setReassignTo('') },
    onError: (err) => toast.error(parseApiError(err)),
  })

  const handleDelete = () => {
    deleteMutation.mutate()
  }

  const otherCategories = categories?.filter((c) => c.id !== deleteTarget?.id) ?? []

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <Button variant="ghost" size="sm" asChild className="-ml-2 gap-1 text-muted-foreground">
        <Link to="/settings"><ArrowLeft className="h-4 w-4" />Back to Settings</Link>
      </Button>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Categories</h1>
        <Button size="sm" onClick={() => setCreating(true)}><Plus className="mr-2 h-4 w-4" />New</Button>
      </div>

      <Card>
        <CardContent className="pt-4 divide-y">
          {isLoading
            ? Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full mb-2" />)
            : categories?.map((cat) => (
              <CategoryRow
                key={cat.id}
                category={cat}
                onEdit={() => setEditing(cat)}
                onDelete={() => setDeleteTarget(cat)}
              />
            ))
          }
          {!isLoading && !categories?.length && (
            <p className="text-sm text-muted-foreground text-center py-8">No categories yet</p>
          )}
        </CardContent>
      </Card>

      {/* Create / Edit dialog */}
      <CategoryDialog
        open={creating || !!editing}
        title={editing ? 'Edit Category' : 'New Category'}
        defaultValues={editing ?? undefined}
        onClose={() => { setCreating(false); setEditing(null) }}
        onSubmit={(d) => editing ? updateMutation.mutate(d) : createMutation.mutate(d)}
        loading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete / reassign dialog */}
      <AlertDialog open={!!deleteTarget} onOpenChange={() => { setDeleteTarget(null); setReassignTo('') }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete "{deleteTarget?.name}"?</AlertDialogTitle>
            <AlertDialogDescription>
              If transactions use this category, reassign them first.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-2">
            <Label className="text-sm">Reassign existing transactions to (optional)</Label>
            <Select value={reassignTo} onValueChange={setReassignTo}>
              <SelectTrigger className="mt-1"><SelectValue placeholder="Keep uncategorized (or pick)" /></SelectTrigger>
              <SelectContent>
                {otherCategories.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDelete}>
              {reassignTo ? 'Reassign & Delete' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function CategoryRow({ category, onEdit, onDelete }: { category: CategoryOut; onEdit: () => void; onDelete: () => void }) {
  return (
    <div className="flex items-center justify-between py-3">
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-sm">
          {category.icon ?? '🏷️'}
        </div>
        <div>
          <p className="text-sm font-medium">{category.name}</p>
          {category.is_global && <Badge variant="secondary" className="text-xs">Global</Badge>}
        </div>
      </div>
      <div className="flex gap-1">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onEdit}><Pencil className="h-3.5 w-3.5" /></Button>
        {!category.is_global && (
          <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={onDelete}><Trash2 className="h-3.5 w-3.5" /></Button>
        )}
      </div>
    </div>
  )
}

function CategoryDialog({ open, title, defaultValues, onClose, onSubmit, loading }: {
  open: boolean; title: string; defaultValues?: Partial<CategoryOut>
  onClose: () => void; onSubmit: (d: CategoryForm) => void; loading: boolean
}) {
  const { register, handleSubmit, formState: { errors } } = useForm<CategoryForm>({
    resolver: zodResolver(categorySchema),
    values: defaultValues ? { name: defaultValues.name ?? '', icon: defaultValues.icon ?? '💰' } : undefined,
  })

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1">
            <Label>Name</Label>
            <Input {...register('name')} />
            {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
          </div>
          <div className="space-y-1">
            <Label>Icon (emoji)</Label>
            <Input {...register('icon')} placeholder="💰" maxLength={2} />
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="outline" className="flex-1" onClick={onClose}><X className="mr-2 h-4 w-4" />Cancel</Button>
            <Button type="submit" className="flex-1" loading={loading}><Check className="mr-2 h-4 w-4" />Save</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
