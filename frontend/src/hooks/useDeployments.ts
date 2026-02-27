import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  createDeployment,
  getDeployments,
  getDeployment,
  approveDeployment,
  rejectDeployment,
} from '../api/client'
import type { CreateDeploymentPayload } from '../api/client'

export function useCreateDeployment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateDeploymentPayload) => createDeployment(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deployments'] })
    },
  })
}

export function useDeployments(page = 1, size = 20) {
  return useQuery({
    queryKey: ['deployments', page, size],
    queryFn: () => getDeployments(page, size),
  })
}

export function useDeployment(id: number) {
  return useQuery({
    queryKey: ['deployment', id],
    queryFn: () => getDeployment(id),
    enabled: !!id,
  })
}

export function useApproveDeployment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => approveDeployment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deployments'] })
      queryClient.invalidateQueries({ queryKey: ['deployment'] })
    },
  })
}

export function useRejectDeployment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => rejectDeployment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deployments'] })
      queryClient.invalidateQueries({ queryKey: ['deployment'] })
    },
  })
}
