import apiClient from './client'
import type { GroupCreate, GroupDetailOut, GroupMemberOut, GroupOut, GroupUpdate, InviteMember } from '@/types'

export const groupsApi = {
  list: () =>
    apiClient.get<GroupOut[]>('/groups').then((r) => r.data),

  get: (id: string) =>
    apiClient.get<GroupDetailOut>(`/groups/${id}`).then((r) => r.data),

  create: (data: GroupCreate) =>
    apiClient.post<GroupOut>('/groups', data).then((r) => r.data),

  update: (id: string, data: GroupUpdate) =>
    apiClient.put<GroupOut>(`/groups/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/groups/${id}`).then((r) => r.data),

  // Members — backend has no dedicated /members endpoint; GET /groups/{id} returns members embedded
  members: (groupId: string) =>
    apiClient.get<GroupDetailOut>(`/groups/${groupId}`).then((r) => r.data.members as GroupMemberOut[]),

  invite: (groupId: string, data: InviteMember) =>
    apiClient.post<GroupMemberOut>(`/groups/${groupId}/members`, data).then((r) => r.data),

  removeMember: (groupId: string, userId: string) =>
    apiClient.delete(`/groups/${groupId}/members/${userId}`).then((r) => r.data),

  leave: (groupId: string) =>
    apiClient.delete(`/groups/${groupId}/members/me`).then((r) => r.data),
}
