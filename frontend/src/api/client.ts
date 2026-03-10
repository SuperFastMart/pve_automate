import axios from 'axios'
import type { VMRequest, VMRequestList, TShirtSizes, OSTemplates, WorkloadType, SettingsGroup, SettingItem, ConnectionTestResult, PVETemplate, OSTemplateMapping, Subnet, Location, PVEEnvironment, PVEEnvironmentListItem, Deployment, DeploymentList, ResourceType } from '../types'

const api = axios.create({
  baseURL: '/api/v1',
})

// Token acquisition function — set by AuthProvider after MSAL initializes
let tokenAcquirer: (() => Promise<string>) | null = null

export function setTokenAcquirer(fn: () => Promise<string>) {
  tokenAcquirer = fn
}

// Inject Bearer token into every request
api.interceptors.request.use(async (config) => {
  if (tokenAcquirer) {
    try {
      const token = await tokenAcquirer()
      config.headers.Authorization = `Bearer ${token}`
    } catch {
      // Token acquisition failed — let the request go without auth
      // The backend will return 401 and MSAL will handle re-auth
    }
  }
  return config
})

// Handle error responses: extract API detail message + auto-reload on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const lastReload = sessionStorage.getItem('auth_reload')
      const now = Date.now()
      // Only reload if we haven't reloaded in the last 10 seconds
      if (!lastReload || now - Number(lastReload) > 10000) {
        sessionStorage.setItem('auth_reload', String(now))
        window.location.reload()
      }
    }
    // Extract the detail message from FastAPI error responses so callers
    // see e.g. "Environment 'prod' already exists" instead of "Request failed with status code 409"
    const detail = error.response?.data?.detail
    if (detail) {
      if (typeof detail === 'string') {
        error.message = detail
      } else if (Array.isArray(detail)) {
        // Pydantic validation errors: [{loc: [...], msg: "...", type: "..."}]
        error.message = detail
          .map((e: { loc?: string[]; msg?: string }) => {
            const field = e.loc?.filter((l: string) => l !== 'body').join('.') || 'field'
            return `${field}: ${e.msg}`
          })
          .join('; ')
      }
    }
    return Promise.reject(error)
  },
)

export interface CreateVMRequestPayload {
  vm_name: string
  description?: string
  resource_type?: ResourceType
  workload_type: string
  os_template: string
  tshirt_size: string
  subnet_id?: number
  environment_id?: number
  cpu_cores?: number
  ram_mb?: number
  disk_gb?: number
  mtu?: number
  enable_ssh_root?: boolean
  bridge?: string
  vlan_tag?: number
  root_password?: string
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

export async function getTShirtSizes(resourceType?: string): Promise<TShirtSizes> {
  const params: Record<string, string> = {}
  if (resourceType) params.resource_type = resourceType
  const { data } = await api.get<TShirtSizes>('/config/tshirt-sizes', { params })
  return data
}

export async function getOSTemplates(environmentId?: number, templateType?: string): Promise<OSTemplates> {
  const params: Record<string, unknown> = {}
  if (environmentId) params.environment_id = environmentId
  if (templateType) params.template_type = templateType
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

export async function retryVMRequest(id: number): Promise<VMRequest> {
  const { data } = await api.post<VMRequest>(`/requests/${id}/retry`)
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
export async function scanPVETemplates(environmentId?: number, templateType?: string): Promise<PVETemplate[]> {
  const params: Record<string, unknown> = {}
  if (environmentId) params.environment_id = environmentId
  if (templateType) params.template_type = templateType
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
export async function getEnvironments(locationId?: number): Promise<PVEEnvironmentListItem[]> {
  const params = locationId ? { location_id: locationId } : {}
  const { data } = await api.get<PVEEnvironmentListItem[]>('/environments', { params })
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
  mtu?: number
  enable_ssh_root?: boolean
  bridge?: string
  vlan_tag?: number
  root_password?: string
}

export interface CreateDeploymentPayload {
  name: string
  description?: string
  resource_type?: ResourceType
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

export async function retryDeployment(id: number): Promise<Deployment> {
  const { data } = await api.post<Deployment>(`/deployments/${id}/retry`)
  return data
}
