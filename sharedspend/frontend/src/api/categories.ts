import apiClient from './client'
import type { CategoryCreate, CategoryDeleteRequest, CategoryOut, CategoryUpdate } from '@/types'

export const categoriesApi = {
  list: (groupId?: string) =>
    apiClient.get<CategoryOut[]>('/categories', { params: groupId ? { group_id: groupId } : {} }).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<CategoryOut>(`/categories/${id}`).then((r) => r.data),

  /**
   * Create a group-scoped category.
   * Backend route: POST /groups/{group_id}/categories
   * group_id is required; callers must provide it.
   */
  create: (groupId: string, data: CategoryCreate) =>
    apiClient.post<CategoryOut>(`/groups/${groupId}/categories`, data).then((r) => r.data),

  update: (id: string, data: CategoryUpdate) =>
    apiClient.put<CategoryOut>(`/categories/${id}`, data).then((r) => r.data),

  /**
   * Delete a category. Pass reassign_to_category_id in body to bulk-reassign
   * any transactions that reference this category before deletion.
   * Backend: DELETE /categories/{id} with optional JSON body.
   */
  delete: (id: string, body?: CategoryDeleteRequest) =>
    apiClient.delete(`/categories/${id}`, { data: body ?? {} }).then((r) => r.data),
}
