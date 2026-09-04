import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { groupsApi } from '@/api'
import type { GroupOut, MemberRole } from '@/types'
import { useAuth } from './AuthContext'

const GROUP_KEY = 'ss_active_group'

interface GroupContextValue {
  groups: GroupOut[]
  activeGroup: GroupOut | null
  myRole: MemberRole | null
  isOwner: boolean
  isLoading: boolean
  setActiveGroup: (group: GroupOut) => void
  reloadGroups: () => Promise<void>
}

const GroupContext = createContext<GroupContextValue | null>(null)

export function GroupProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  const [groups, setGroups] = useState<GroupOut[]>([])
  const [activeGroup, setActiveGroupState] = useState<GroupOut | null>(null)
  const [myRole, setMyRole] = useState<MemberRole | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const { user } = useAuth()

  const loadGroups = useCallback(async () => {
    if (!isAuthenticated) {
      setGroups([])
      setActiveGroupState(null)
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    try {
      const list = await groupsApi.list()
      setGroups(list)

      const savedId = localStorage.getItem(GROUP_KEY)
      const saved = list.find((g) => g.id === savedId)
      const active = saved ?? list[0] ?? null
      setActiveGroupState(active)

      if (active && user) {
        try {
          const members = await groupsApi.members(active.id)
          const me = members.find((m) => m.user_id === user.id)
          setMyRole(me?.role ?? null)
        } catch {
          setMyRole(null)
        }
      }
    } finally {
      setIsLoading(false)
    }
  }, [isAuthenticated, user])

  useEffect(() => { loadGroups() }, [loadGroups])

  const setActiveGroup = useCallback(async (group: GroupOut) => {
    setActiveGroupState(group)
    localStorage.setItem(GROUP_KEY, group.id)
    if (user) {
      try {
        const members = await groupsApi.members(group.id)
        const me = members.find((m) => m.user_id === user.id)
        setMyRole(me?.role ?? null)
      } catch {
        setMyRole(null)
      }
    }
  }, [user])

  const isOwner = myRole === 'OWNER'

  return (
    <GroupContext.Provider value={{
      groups, activeGroup, myRole, isOwner, isLoading,
      setActiveGroup, reloadGroups: loadGroups,
    }}>
      {children}
    </GroupContext.Provider>
  )
}

export function useGroup() {
  const ctx = useContext(GroupContext)
  if (!ctx) throw new Error('useGroup must be used inside GroupProvider')
  return ctx
}
