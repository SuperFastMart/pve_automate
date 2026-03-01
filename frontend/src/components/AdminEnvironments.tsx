import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  useAllEnvironments,
  useCreateEnvironment,
  useUpdateEnvironment,
  useDeleteEnvironment,
  useTestEnvironmentConnection,
} from '../hooks/useEnvironments'
import { getLocations } from '../api/client'
import type { ConnectionTestResult, EnvironmentType } from '../types'

interface EnvFormState {
  name: string
  display_name: string
  description: string
  environment_type: EnvironmentType
  location_id: string
  // Proxmox
  pve_host: string
  pve_user: string
  pve_token_name: string
  pve_token_value: string
  pve_verify_ssl: boolean
  // vSphere
  vsphere_host: string
  vsphere_user: string
  vsphere_password: string
  vsphere_port: string
  vsphere_verify_ssl: boolean
  vsphere_datacenter: string
  vsphere_cluster: string
  // Common
  enabled: boolean
  is_default: boolean
}

const emptyForm: EnvFormState = {
  name: '',
  display_name: '',
  description: '',
  environment_type: 'proxmox',
  location_id: '',
  pve_host: '',
  pve_user: '',
  pve_token_name: '',
  pve_token_value: '',
  pve_verify_ssl: false,
  vsphere_host: '',
  vsphere_user: '',
  vsphere_password: '',
  vsphere_port: '443',
  vsphere_verify_ssl: false,
  vsphere_datacenter: '',
  vsphere_cluster: '',
  enabled: true,
  is_default: false,
}

const TYPE_LABELS: Record<EnvironmentType, string> = {
  proxmox: 'Proxmox VE',
  esxi: 'ESXi (Standalone)',
  vcenter: 'vCenter',
}

export default function AdminEnvironments() {
  const { data: environments, isLoading } = useAllEnvironments()
  const { data: locations } = useQuery({ queryKey: ['locations'], queryFn: getLocations })
  const createEnv = useCreateEnvironment()
  const updateEnv = useUpdateEnvironment()
  const deleteEnv = useDeleteEnvironment()
  const testConn = useTestEnvironmentConnection()

  const [addForm, setAddForm] = useState<EnvFormState | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<EnvFormState | null>(null)
  const [testResults, setTestResults] = useState<Record<number, ConnectionTestResult>>({})

  const handleAdd = () => setAddForm({ ...emptyForm })

  const buildPayload = (form: EnvFormState, isEdit: boolean) => {
    const payload: Record<string, unknown> = {
      name: form.name,
      display_name: form.display_name,
      description: form.description,
      environment_type: form.environment_type,
      location_id: form.location_id ? Number(form.location_id) : null,
      location_name: form.location_id && locations
        ? locations.find((l) => String(l.id) === form.location_id)?.name ?? null
        : null,
      enabled: form.enabled,
      is_default: form.is_default,
    }

    if (form.environment_type === 'proxmox') {
      payload.pve_host = form.pve_host
      payload.pve_user = form.pve_user
      payload.pve_token_name = form.pve_token_name
      if (form.pve_token_value || !isEdit) payload.pve_token_value = form.pve_token_value
      payload.pve_verify_ssl = form.pve_verify_ssl
    } else {
      payload.vsphere_host = form.vsphere_host
      payload.vsphere_user = form.vsphere_user
      if (form.vsphere_password || !isEdit) payload.vsphere_password = form.vsphere_password
      payload.vsphere_port = Number(form.vsphere_port) || 443
      payload.vsphere_verify_ssl = form.vsphere_verify_ssl
      if (form.environment_type === 'vcenter') {
        payload.vsphere_datacenter = form.vsphere_datacenter
        payload.vsphere_cluster = form.vsphere_cluster
      }
    }

    return payload
  }

  const handleSubmitAdd = () => {
    if (!addForm || !addForm.name || !addForm.display_name) return
    createEnv.mutate(buildPayload(addForm, false) as any, {
      onSuccess: () => setAddForm(null),
    })
  }

  const handleEdit = (env: any) => {
    setEditingId(env.id)
    setEditForm({
      name: env.name,
      display_name: env.display_name,
      description: env.description || '',
      environment_type: env.environment_type || 'proxmox',
      location_id: env.location_id ? String(env.location_id) : '',
      pve_host: env.pve_host || '',
      pve_user: env.pve_user || '',
      pve_token_name: env.pve_token_name || '',
      pve_token_value: '',
      pve_verify_ssl: env.pve_verify_ssl ?? false,
      vsphere_host: env.vsphere_host || '',
      vsphere_user: env.vsphere_user || '',
      vsphere_password: '',
      vsphere_port: String(env.vsphere_port ?? 443),
      vsphere_verify_ssl: env.vsphere_verify_ssl ?? false,
      vsphere_datacenter: env.vsphere_datacenter || '',
      vsphere_cluster: env.vsphere_cluster || '',
      enabled: env.enabled,
      is_default: env.is_default,
    })
  }

  const handleSubmitEdit = () => {
    if (!editForm || editingId === null) return
    const payload = { id: editingId, ...buildPayload(editForm, true) }
    updateEnv.mutate(payload as any, {
      onSuccess: () => {
        setEditingId(null)
        setEditForm(null)
      },
    })
  }

  const handleTest = (id: number) => {
    testConn.mutate(id, {
      onSuccess: (result) => setTestResults((prev) => ({ ...prev, [id]: result })),
      onError: (err) => setTestResults((prev) => ({ ...prev, [id]: { success: false, message: (err as Error).message } })),
    })
  }

  const inputCls = "w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"

  const renderForm = (form: EnvFormState, setForm: (f: EnvFormState) => void) => (
    <div className="space-y-4">
      {/* Common fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Name (slug)</label>
          <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="prod" className={inputCls} />
          <p className="mt-0.5 text-xs text-gray-400">Lowercase identifier (e.g. dev, prod)</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
          <input type="text" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="Production" className={inputCls} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Environment Type</label>
          <select value={form.environment_type} onChange={(e) => setForm({ ...form, environment_type: e.target.value as EnvironmentType })} className={inputCls}>
            <option value="proxmox">Proxmox VE</option>
            <option value="esxi">ESXi (Standalone)</option>
            <option value="vcenter">vCenter</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
          <select value={form.location_id} onChange={(e) => setForm({ ...form, location_id: e.target.value })} className={inputCls}>
            <option value="">No location</option>
            {locations?.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.name}{loc.description ? ` — ${loc.description}` : ''}
              </option>
            ))}
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <input type="text" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Production cluster" className={inputCls} />
        </div>
      </div>

      {/* Proxmox credentials */}
      {form.environment_type === 'proxmox' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <h4 className="md:col-span-2 text-sm font-semibold text-blue-800">Proxmox Credentials</h4>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Host</label>
            <input type="text" value={form.pve_host} onChange={(e) => setForm({ ...form, pve_host: e.target.value })} placeholder="pve.example.com:8006" className={inputCls} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">User</label>
            <input type="text" value={form.pve_user} onChange={(e) => setForm({ ...form, pve_user: e.target.value })} placeholder="root@pam" className={inputCls} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">API Token Name</label>
            <input type="text" value={form.pve_token_name} onChange={(e) => setForm({ ...form, pve_token_name: e.target.value })} placeholder="peevinator" className={inputCls} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              API Token Value {editingId !== null && <span className="text-xs text-gray-400">(leave blank to keep existing)</span>}
            </label>
            <input type="password" value={form.pve_token_value} onChange={(e) => setForm({ ...form, pve_token_value: e.target.value })} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" className={inputCls} />
          </div>
          <div className="md:col-span-2">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.pve_verify_ssl} onChange={(e) => setForm({ ...form, pve_verify_ssl: e.target.checked })} className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" />
              <span className="text-sm text-gray-700">Verify SSL</span>
            </label>
          </div>
        </div>
      )}

      {/* vSphere credentials */}
      {(form.environment_type === 'esxi' || form.environment_type === 'vcenter') && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-green-50 rounded-lg border border-green-200">
          <h4 className="md:col-span-2 text-sm font-semibold text-green-800">
            {form.environment_type === 'vcenter' ? 'vCenter' : 'ESXi'} Credentials
          </h4>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Host</label>
            <input type="text" value={form.vsphere_host} onChange={(e) => setForm({ ...form, vsphere_host: e.target.value })} placeholder="vcenter.example.com" className={inputCls} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input type="text" value={form.vsphere_user} onChange={(e) => setForm({ ...form, vsphere_user: e.target.value })} placeholder="administrator@vsphere.local" className={inputCls} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Password {editingId !== null && <span className="text-xs text-gray-400">(leave blank to keep existing)</span>}
            </label>
            <input type="password" value={form.vsphere_password} onChange={(e) => setForm({ ...form, vsphere_password: e.target.value })} placeholder="********" className={inputCls} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Port</label>
            <input type="number" value={form.vsphere_port} onChange={(e) => setForm({ ...form, vsphere_port: e.target.value })} className={inputCls} />
          </div>
          {form.environment_type === 'vcenter' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Datacenter</label>
                <input type="text" value={form.vsphere_datacenter} onChange={(e) => setForm({ ...form, vsphere_datacenter: e.target.value })} placeholder="DC1" className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Cluster (optional)</label>
                <input type="text" value={form.vsphere_cluster} onChange={(e) => setForm({ ...form, vsphere_cluster: e.target.value })} placeholder="Cluster1" className={inputCls} />
              </div>
            </>
          )}
          <div className="md:col-span-2">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.vsphere_verify_ssl} onChange={(e) => setForm({ ...form, vsphere_verify_ssl: e.target.checked })} className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" />
              <span className="text-sm text-gray-700">Verify SSL</span>
            </label>
          </div>
        </div>
      )}

      {/* Flags */}
      <div className="flex items-center gap-6">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" />
          <span className="text-sm text-gray-700">Enabled</span>
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" />
          <span className="text-sm text-gray-700">Default</span>
        </label>
      </div>
    </div>
  )

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-gray-500">
          Configure hypervisor environments (Proxmox, ESXi, vCenter). Users select an environment when submitting VM requests.
        </p>
      </div>

      {/* Add Button */}
      {!addForm && (
        <div className="flex justify-end">
          <button
            onClick={handleAdd}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700"
          >
            Add Environment
          </button>
        </div>
      )}

      {/* Add Form */}
      {addForm && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">New Environment</h3>
          {renderForm(addForm, setAddForm)}
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleSubmitAdd}
              disabled={!addForm.name || !addForm.display_name || createEnv.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {createEnv.isPending ? 'Saving...' : 'Save'}
            </button>
            <button
              onClick={() => setAddForm(null)}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
          {createEnv.isError && (
            <p className="mt-2 text-sm text-red-600">
              Failed to save: {(createEnv.error as Error)?.message ?? 'Unknown error'}
            </p>
          )}
        </div>
      )}

      {/* Edit Form */}
      {editForm && editingId !== null && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Edit Environment</h3>
          {renderForm(editForm, setEditForm)}
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleSubmitEdit}
              disabled={updateEnv.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {updateEnv.isPending ? 'Saving...' : 'Save Changes'}
            </button>
            <button
              onClick={() => { setEditingId(null); setEditForm(null) }}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
          {updateEnv.isError && (
            <p className="mt-2 text-sm text-red-600">
              Failed to update: {(updateEnv.error as Error)?.message ?? 'Unknown error'}
            </p>
          )}
        </div>
      )}

      {/* Environments Table */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Environments</h3>
        </div>

        {isLoading && <p className="p-6 text-gray-500">Loading...</p>}

        {environments && environments.length === 0 && (
          <div className="p-6 text-center text-gray-500 text-sm">
            No environments configured. Add one to get started.
          </div>
        )}

        {environments && environments.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Host</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Location</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Default</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Enabled</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {environments.map((env) => (
                  <tr key={env.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="text-sm font-mono text-gray-700">{env.name}</div>
                      <div className="text-xs text-gray-400">{env.display_name}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        env.environment_type === 'proxmox' ? 'bg-blue-100 text-blue-700' :
                        env.environment_type === 'vcenter' ? 'bg-green-100 text-green-700' :
                        'bg-purple-100 text-purple-700'
                      }`}>
                        {TYPE_LABELS[env.environment_type] ?? env.environment_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {env.environment_type === 'proxmox' ? env.pve_host : env.vsphere_host}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {env.location_name || '—'}
                    </td>
                    <td className="px-4 py-3">
                      {env.is_default && (
                        <span className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full font-medium">
                          Default
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => updateEnv.mutate({ id: env.id, enabled: !env.enabled })}
                        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                          env.enabled ? 'bg-indigo-600' : 'bg-gray-200'
                        }`}
                      >
                        <span
                          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                            env.enabled ? 'translate-x-4.5' : 'translate-x-0.5'
                          }`}
                        />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleTest(env.id)}
                          disabled={testConn.isPending}
                          className="text-indigo-600 hover:text-indigo-800 text-xs font-medium"
                        >
                          Test
                        </button>
                        <button
                          onClick={() => handleEdit(env)}
                          className="text-gray-600 hover:text-gray-800 text-xs font-medium"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => {
                            if (confirm(`Delete environment "${env.display_name}"?`)) {
                              deleteEnv.mutate(env.id)
                            }
                          }}
                          className="text-red-500 hover:text-red-700 text-xs font-medium"
                        >
                          Delete
                        </button>
                      </div>
                      {testResults[env.id] && (
                        <div className={`mt-1 text-xs ${testResults[env.id].success ? 'text-green-600' : 'text-red-600'}`}>
                          {testResults[env.id].message}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {deleteEnv.isError && (
          <div className="mx-6 mb-4 px-4 py-3 rounded-md text-sm bg-red-50 text-red-800 border border-red-200">
            {(deleteEnv.error as Error)?.message ?? 'Failed to delete environment'}
          </div>
        )}
      </div>
    </div>
  )
}
