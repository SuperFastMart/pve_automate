import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getSettings,
  bulkUpdateSettings,
  deleteSetting,
  testProxmoxConnection,
  testJiraConnection,
  testPhpIpamConnection,
} from '../api/client'

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  })
}

export function useBulkUpdateSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ group, settings }: { group: string; settings: Record<string, string> }) =>
      bulkUpdateSettings(group, settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

export function useDeleteSetting() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (key: string) => deleteSetting(key),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

export function useTestProxmox() {
  return useMutation({
    mutationFn: testProxmoxConnection,
  })
}

export function useTestJira() {
  return useMutation({
    mutationFn: testJiraConnection,
  })
}

export function useTestPhpIpam() {
  return useMutation({
    mutationFn: testPhpIpamConnection,
  })
}
