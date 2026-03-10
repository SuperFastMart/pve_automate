import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  createDecomRequest,
  getDecomRequests,
  getDecomRequest,
  approveDecomRequest,
  rejectDecomRequest,
  startDecomRequest,
  completeDecomRequest,
  cancelDecomRequest,
  deleteDecomRequest,
} from '../api/client'
import type { CreateDecomRequestPayload } from '../api/client'

export function useCreateDecomRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateDecomRequestPayload) => createDecomRequest(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decom-requests'] })
    },
  })
}

export function useDecomRequests(page = 1, size = 20) {
  return useQuery({
    queryKey: ['decom-requests', page, size],
    queryFn: () => getDecomRequests(page, size),
  })
}

export function useDecomRequest(id: number) {
  return useQuery({
    queryKey: ['decom-request', id],
    queryFn: () => getDecomRequest(id),
    enabled: !!id,
  })
}

export function useApproveDecomRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => approveDecomRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decom-requests'] })
      queryClient.invalidateQueries({ queryKey: ['decom-request'] })
    },
  })
}

export function useRejectDecomRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => rejectDecomRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decom-requests'] })
      queryClient.invalidateQueries({ queryKey: ['decom-request'] })
    },
  })
}

export function useStartDecomRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => startDecomRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decom-requests'] })
      queryClient.invalidateQueries({ queryKey: ['decom-request'] })
    },
  })
}

export function useCompleteDecomRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => completeDecomRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decom-requests'] })
      queryClient.invalidateQueries({ queryKey: ['decom-request'] })
      queryClient.invalidateQueries({ queryKey: ['vm-requests'] })
      queryClient.invalidateQueries({ queryKey: ['deployments'] })
    },
  })
}

export function useCancelDecomRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => cancelDecomRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decom-requests'] })
      queryClient.invalidateQueries({ queryKey: ['decom-request'] })
    },
  })
}

export function useDeleteDecomRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteDecomRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decom-requests'] })
    },
  })
}
