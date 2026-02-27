import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getVMRequests,
  getVMRequest,
  createVMRequest,
  approveVMRequest,
  rejectVMRequest,
  getTShirtSizes,
  getOSTemplates,
  getWorkloadTypes,
  type CreateVMRequestPayload,
} from '../api/client'

export function useVMRequests(page = 1, size = 20) {
  return useQuery({
    queryKey: ['vm-requests', page, size],
    queryFn: () => getVMRequests(page, size),
  })
}

export function useVMRequest(id: number) {
  return useQuery({
    queryKey: ['vm-request', id],
    queryFn: () => getVMRequest(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'provisioning' || status === 'pending_approval' || status === 'approved') {
        return 5000
      }
      return false
    },
  })
}

export function useCreateVMRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateVMRequestPayload) => createVMRequest(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm-requests'] })
    },
  })
}

export function useTShirtSizes() {
  return useQuery({
    queryKey: ['tshirt-sizes'],
    queryFn: getTShirtSizes,
    staleTime: Infinity,
  })
}

export function useOSTemplates(environmentId?: number) {
  return useQuery({
    queryKey: ['os-templates', environmentId ?? 'all'],
    queryFn: () => getOSTemplates(environmentId),
    staleTime: 5 * 60 * 1000,
  })
}

export function useWorkloadTypes() {
  return useQuery({
    queryKey: ['workload-types'],
    queryFn: getWorkloadTypes,
    staleTime: Infinity,
  })
}

export function useApproveVMRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => approveVMRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm-requests'] })
    },
  })
}

export function useRejectVMRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => rejectVMRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm-requests'] })
    },
  })
}
