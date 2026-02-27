import axios from 'axios'
import type { VMRequest, VMRequestList, TShirtSizes, OSTemplates, WorkloadType, SettingsGroup, SettingItem, ConnectionTestResult, PVETemplate, OSTemplateMapping, Subnet, Location, PVEEnvironment, PVEEnvironmentListItem, Deployment, DeploymentList } from '../types'

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
  subnet_id?: number
  environment_id?: number
  cpu_cores?: number
  ram_mb?: number
  disk_gb?: number
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

export async function getOSTemplates(environmentId?: number): Promise<OSTemplates> {
  const params = environmentId ? { environment_id: environmentId } : {}
  const { data } = await api.get<OSTemplates>('/config/os-templates', { params })
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

export async function testPhpIpamConnection(): Promise<ConnectionTestResult> {
  const { data } = await api.post<ConnectionTestResult>('/settings/phpipam/test')
  return data
}

export async function testSmtpConnection(): Promise<ConnectionTestResult> {
  const { data } = await api.post<ConnectionTestResult>('/settings/smtp/test')
  return data
}

export async function getSubnets(): Promise<Subnet[]> {
  const { data } = await api.get<Subnet[]>('/config/subnets')
  return data
}

export async function getLocations(): Promise<Location[]> {
  const { data } = await api.get<Location[]>('/config/locations')
  return data
}

// Template management API
export async function scanPVETemplates(environmentId?: number): Promise<PVETemplate[]> {
  const params = environmentId ? { environment_id: environmentId } : {}
  const { data } = await api.get<PVETemplate[]>('/settings/templates/scan', { params })
  return data
}

export async function getTemplateMappings(environmentId?: number): Promise<OSTemplateMapping[]> {
  const params = environmentId ? { environment_id: environmentId } : {}
  const { data } = await api.get<OSTemplateMapping[]>('/settings/templates', { params })
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

// Environment management API
export async function getEnvironments(): Promise<PVEEnvironmentListItem[]> {
  const { data } = await api.get<PVEEnvironmentListItem[]>('/environments')
  return data
}

export async function getAllEnvironments(): Promise<PVEEnvironment[]> {
  const { data } = await api.get<PVEEnvironment[]>('/environments/all')
  return data
}

export async function createEnvironment(payload: Omit<PVEEnvironment, 'id' | 'created_at' | 'updated_at'> & { pve_token_value: string }): Promise<PVEEnvironment> {
  const { data } = await api.post<PVEEnvironment>('/environments', payload)
  return data
}

export async function updateEnvironment(id: number, payload: Record<string, unknown>): Promise<PVEEnvironment> {
  const { data } = await api.put<PVEEnvironment>(`/environments/${id}`, payload)
  return data
}

export async function deleteEnvironment(id: number): Promise<void> {
  await api.delete(`/environments/${id}`)
}

export async function testEnvironmentConnection(id: number): Promise<ConnectionTestResult> {
  const { data } = await api.post<ConnectionTestResult>(`/environments/${id}/test`)
  return data
}

// Deployment API
export interface DeploymentVMPayload {
  vm_name: string
  description?: string
  os_template: string
  tshirt_size: string
  subnet_id?: number
  cpu_cores?: number
  ram_mb?: number
  disk_gb?: number
}

export interface CreateDeploymentPayload {
  name: string
  description?: string
  requestor_name: string
  requestor_email: string
  workload_type: string
  environment_id?: number
  vms: DeploymentVMPayload[]
}

export async function createDeployment(payload: CreateDeploymentPayload): Promise<Deployment> {
  const { data } = await api.post<Deployment>('/deployments', payload)
  return data
}

export async function getDeployments(page = 1, size = 20): Promise<DeploymentList> {
  const { data } = await api.get<DeploymentList>('/deployments', { params: { page, size } })
  return data
}

export async function getDeployment(id: number): Promise<Deployment> {
  const { data } = await api.get<Deployment>(`/deployments/${id}`)
  return data
}

export async function approveDeployment(id: number): Promise<Deployment> {
  const { data } = await api.post<Deployment>(`/deployments/${id}/approve`)
  return data
}

export async function rejectDeployment(id: number): Promise<Deployment> {
  const { data } = await api.post<Deployment>(`/deployments/${id}/reject`)
  return data
}
