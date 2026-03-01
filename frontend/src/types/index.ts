export type RequestStatus =
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'provisioning'
  | 'provisioning_failed'
  | 'completed'

export interface VMRequest {
  id: number
  vm_name: string
  description: string | null
  requestor_name: string
  requestor_email: string
  workload_type: string
  os_template: string
  tshirt_size: string
  cpu_cores: number
  ram_mb: number
  disk_gb: number
  status: RequestStatus
  jira_issue_key: string | null
  jira_issue_url: string | null
  proxmox_vmid: number | null
  proxmox_node: string | null
  hypervisor_vm_id: string | null
  hypervisor_host: string | null
  ip_address: string | null
  environment_id: number | null
  environment_name: string | null
  deployment_id: number | null
  error_message: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
  completed_at: string | null
}

export type DeploymentStatus =
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'provisioning'
  | 'partially_completed'
  | 'completed'
  | 'failed'

export interface Deployment {
  id: number
  name: string
  description: string | null
  requestor_name: string
  requestor_email: string
  workload_type: string
  environment_id: number | null
  environment_name: string | null
  status: DeploymentStatus
  jira_issue_key: string | null
  jira_issue_url: string | null
  error_message: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
  completed_at: string | null
  vm_requests: VMRequest[]
}

export interface DeploymentListItem {
  id: number
  name: string
  requestor_name: string
  requestor_email: string
  workload_type: string
  environment_name: string | null
  status: DeploymentStatus
  jira_issue_key: string | null
  vm_count: number
  created_at: string
}

export interface DeploymentList {
  items: DeploymentListItem[]
  total: number
}

export type EnvironmentType = 'proxmox' | 'esxi' | 'vcenter'

export interface PVEEnvironment {
  id: number
  name: string
  display_name: string
  description: string | null
  environment_type: EnvironmentType
  location_id: number | null
  location_name: string | null
  pve_host: string | null
  pve_user: string | null
  pve_token_name: string | null
  pve_verify_ssl: boolean
  vsphere_host: string | null
  vsphere_user: string | null
  vsphere_port: number
  vsphere_verify_ssl: boolean
  vsphere_datacenter: string | null
  vsphere_cluster: string | null
  enabled: boolean
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface PVEEnvironmentListItem {
  id: number
  name: string
  display_name: string
  description: string | null
  environment_type: EnvironmentType
  location_id: number | null
  location_name: string | null
  is_default: boolean
}

export interface VMRequestList {
  items: VMRequest[]
  total: number
}

export interface TShirtSize {
  display_name: string
  cpu_cores: number
  ram_mb: number
  disk_gb: number
  description: string
}

export type TShirtSizes = Record<string, TShirtSize>

export interface OSTemplate {
  display_name: string
  vmid: number
  node: string
  cloud_init: boolean
  os_family?: string
}

export type OSTemplates = Record<string, OSTemplate>

export interface PVETemplate {
  vmid: number | null
  name: string
  node: string | null
  status: string
  disk_size: number
  memory: number
  environment_id?: number | null
  environment_name?: string | null
  template_ref?: string | null
}

export interface OSTemplateMapping {
  id: number
  key: string
  display_name: string
  vmid: number | null
  node: string | null
  template_ref: string | null
  os_family: 'linux' | 'windows'
  cloud_init: boolean
  enabled: boolean
  environment_id: number | null
  created_at: string
  updated_at: string
}

export interface WorkloadType {
  key: string
  display_name: string
}

export interface SettingItem {
  key: string
  value: string
  group: string
  display_name: string
  is_secret: boolean
  source: 'database' | 'env'
}

export interface SettingsGroup {
  group: string
  display_name: string
  settings: SettingItem[]
}

export interface ConnectionTestResult {
  success: boolean
  message: string
}

export interface Subnet {
  id: number
  subnet: string
  mask: string
  description: string
  vlanId: string | null
  sectionId: string | null
  locationId: number | null
  locationName: string | null
}

export interface Location {
  id: number
  name: string
  description: string
  address: string
}
