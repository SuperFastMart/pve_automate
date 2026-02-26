import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  scanPVETemplates,
  getTemplateMappings,
  createTemplateMapping,
  updateTemplateMapping,
  deleteTemplateMapping,
} from '../api/client'
import type { OSTemplateMapping } from '../types'

export function useScanPVETemplates() {
  return useMutation({
    mutationFn: scanPVETemplates,
  })
}

export function useTemplateMappings() {
  return useQuery({
    queryKey: ['template-mappings'],
    queryFn: getTemplateMappings,
  })
}

export function useCreateTemplateMapping() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Omit<OSTemplateMapping, 'id' | 'created_at' | 'updated_at'>) =>
      createTemplateMapping(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['template-mappings'] })
      queryClient.invalidateQueries({ queryKey: ['os-templates'] })
    },
  })
}

export function useUpdateTemplateMapping() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: number } & Partial<Omit<OSTemplateMapping, 'id' | 'created_at' | 'updated_at'>>) =>
      updateTemplateMapping(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['template-mappings'] })
      queryClient.invalidateQueries({ queryKey: ['os-templates'] })
    },
  })
}

export function useDeleteTemplateMapping() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteTemplateMapping(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['template-mappings'] })
      queryClient.invalidateQueries({ queryKey: ['os-templates'] })
    },
  })
}
