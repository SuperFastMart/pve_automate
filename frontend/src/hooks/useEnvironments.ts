import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getEnvironments,
  getAllEnvironments,
  createEnvironment,
  updateEnvironment,
  deleteEnvironment,
  testEnvironmentConnection,
} from '../api/client'

export function useEnvironments() {
  return useQuery({
    queryKey: ['environments'],
    queryFn: getEnvironments,
  })
}

export function useAllEnvironments() {
  return useQuery({
    queryKey: ['environments-all'],
    queryFn: getAllEnvironments,
  })
}

export function useCreateEnvironment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createEnvironment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environments'] })
      queryClient.invalidateQueries({ queryKey: ['environments-all'] })
    },
  })
}

export function useUpdateEnvironment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: number } & Record<string, unknown>) =>
      updateEnvironment(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environments'] })
      queryClient.invalidateQueries({ queryKey: ['environments-all'] })
    },
  })
}

export function useDeleteEnvironment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteEnvironment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environments'] })
      queryClient.invalidateQueries({ queryKey: ['environments-all'] })
    },
  })
}

export function useTestEnvironmentConnection() {
  return useMutation({
    mutationFn: (id: number) => testEnvironmentConnection(id),
  })
}
