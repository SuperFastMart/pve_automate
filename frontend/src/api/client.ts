import axios from 'axios'
import type { VMRequest, VMRequestList, TShirtSizes, OSTemplates, WorkloadType, SettingsGroup, SettingItem, ConnectionTestResult, PVETemplate, OSTemplateMapping } from '../types'

const api = axios.create({
  baseURL: '/api/v1',
})

export interface CreateVMRequestPayload {
  vm_name: string
  description?: string
  requestor_name: string
  requestor_email: string
  workload_type: string
  os_template: string
  tshirt_size: string
}

export async function createVMRequest(payload: CreateVMRequestPayload): Promise<VMRequest> {
  const { data } = await api.post<VMRequest>('/requests', payload)
  return data
}

export async function getVMRequests(page = 1, size = 20): Promise<VMRequestList> {
  const { data } = await api.get<VMRequestList>('/requests', { params: { page, size } })
  return data
}

export async function getVMRequest(id: number): Promise<VMRequest> {
  const { data } = await api.get<VMRequest>(`/requests/${id}`)
  return data
}

export async function getTShirtSizes(): Promise<TShirtSizes> {
  const { data } = await api.get<TShirtSizes>('/config/tshirt-sizes')
  return data
}

export async function getOSTemplates(): Promise<OSTemplates> {
  const { data } = await api.get<OSTemplates>('/config/os-templates')
  return data
}

export async function getWorkloadTypes(): Promise<WorkloadType[]> {
  const { data } = await api.get<WorkloadType[]>('/config/workload-types')
  return data
}

export async function approveVMRequest(id: number): Promise<VMRequest> {
  const { data } = await api.post<VMRequest>(`/requests/${id}/approve`)
  return data
}

export async function rejectVMRequest(id: number): Promise<VMRequest> {
  const { data } = await api.post<VMRequest>(`/requests/${id}/reject`)
  return data
}

// Settings API
export async function getSettings(): Promise<SettingsGroup[]> {
  const { data } = await api.get<SettingsGroup[]>('/settings')
  return data
}

export async function getGroupSettings(group: string): Promise<SettingsGroup> {
  const { data } = await api.get<SettingsGroup>(`/settings/${group}`)
  return data
}

export async function updateSetting(key: string, value: string): Promise<SettingItem> {
  const { data } = await api.put<SettingItem>(`/settings/${key}`, { value })
  return data
}

export async function bulkUpdateSettings(group: string, settings: Record<string, string>): Promise<SettingItem[]> {
  const { data } = await api.put<SettingItem[]>(`/settings/${group}/bulk`, { settings })
  return data
}

export async function deleteSetting(key: string): Promise<SettingItem> {
  const { data } = await api.delete<SettingItem>(`/settings/${key}`)
  return data
}

export async function testProxmoxConnection(): Promise<ConnectionTestResult> {
  const { data } = await api.post<ConnectionTestResult>('/settings/proxmox/test')
  return data
}

export async function testJiraConnection(): Promise<ConnectionTestResult> {
  const { data } = await api.post<ConnectionTestResult>('/settings/jira/test')
  return data
}

// Template management API
export async function scanPVETemplates(): Promise<PVETemplate[]> {
  const { data } = await api.get<PVETemplate[]>('/settings/templates/scan')
  return data
}

export async function getTemplateMappings(): Promise<OSTemplateMapping[]> {
  const { data } = await api.get<OSTemplateMapping[]>('/settings/templates')
  return data
}

export async function createTemplateMapping(payload: Omit<OSTemplateMapping, 'id' | 'created_at' | 'updated_at'>): Promise<OSTemplateMapping> {
  const { data } = await api.post<OSTemplateMapping>('/settings/templates', payload)
  return data
}

export async function updateTemplateMapping(id: number, payload: Partial<Omit<OSTemplateMapping, 'id' | 'created_at' | 'updated_at'>>): Promise<OSTemplateMapping> {
  const { data } = await api.put<OSTemplateMapping>(`/settings/templates/${id}`, payload)
  return data
}

export async function deleteTemplateMapping(id: number): Promise<void> {
  await api.delete(`/settings/templates/${id}`)
}
