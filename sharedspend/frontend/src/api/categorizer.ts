import apiClient from './client'
import type { CategorizeRequest, CategorizeResponse } from '@/types'

export const categorizerApi = {
  suggest: (data: CategorizeRequest) =>
    apiClient.post<CategorizeResponse>('/categorize', data).then((r) => r.data),
}
