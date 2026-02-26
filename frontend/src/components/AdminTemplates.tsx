import { useState } from 'react'
import {
  useScanPVETemplates,
  useTemplateMappings,
  useCreateTemplateMapping,
  useUpdateTemplateMapping,
  useDeleteTemplateMapping,
} from '../hooks/useTemplates'
import type { PVETemplate } from '../types'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const gb = bytes / (1024 * 1024 * 1024)
  if (gb >= 1) return `${gb.toFixed(1)} GB`
  const mb = bytes / (1024 * 1024)
  return `${mb.toFixed(0)} MB`
}

interface AddFormState {
  vmid: number
  node: string
  pve_name: string
  key: string
  display_name: string
  os_family: 'linux' | 'windows'
  cloud_init: boolean
}

export default function AdminTemplates() {
  const scan = useScanPVETemplates()
  const { data: mappings, isLoading } = useTemplateMappings()
  const createMapping = useCreateTemplateMapping()
  const updateMapping = useUpdateTemplateMapping()
  const deleteMapping = useDeleteTemplateMapping()

  const [addForm, setAddForm] = useState<AddFormState | null>(null)

  const handleAddFromScan = (tmpl: PVETemplate) => {
    const suggestedKey = tmpl.name.toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/-+/g, '-')
    setAddForm({
      vmid: tmpl.vmid,
      node: tmpl.node,
      pve_name: tmpl.name,
      key: suggestedKey,
      display_name: tmpl.name,
      os_family: 'linux',
      cloud_init: true,
    })
  }

  const handleAddManual = () => {
    setAddForm({
      vmid: 0,
      node: '',
      pve_name: '',
      key: '',
      display_name: '',
      os_family: 'linux',
      cloud_init: true,
    })
  }

  const handleSubmitAdd = () => {
    if (!addForm || !addForm.key || !addForm.display_name) return
    createMapping.mutate(
      {
        key: addForm.key,
        display_name: addForm.display_name,
        vmid: addForm.vmid,
        node: addForm.node,
        os_family: addForm.os_family,
        cloud_init: addForm.cloud_init,
        enabled: true,
      },
      { onSuccess: () => setAddForm(null) }
    )
  }

  const alreadyMappedVmids = new Set(mappings?.map((m) => m.vmid) ?? [])

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-gray-500">
          Scan Proxmox for template VMs, then map them to OS options shown in the request form.
        </p>
      </div>

      {/* Scan Section */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">Proxmox Templates</h3>
          <div className="flex gap-2">
            <button
              onClick={handleAddManual}
              className="px-3 py-1.5 text-sm font-medium text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Add Manual
            </button>
            <button
              onClick={() => scan.mutate()}
              disabled={scan.isPending}
              className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {scan.isPending ? 'Scanning...' : 'Scan Proxmox'}
            </button>
          </div>
        </div>

        {scan.isError && (
          <div className="mx-6 mt-4 px-4 py-3 rounded-md text-sm bg-red-50 text-red-800 border border-red-200">
            Failed to scan: {scan.error?.message ?? 'Unknown error'}
          </div>
        )}

        {scan.data && scan.data.length === 0 && (
          <div className="p-6 text-center text-gray-500 text-sm">
            No template VMs found in Proxmox. Create a VM and convert it to a template first.
          </div>
        )}

        {scan.data && scan.data.length > 0 && (
          <div className="p-6">
            <div className="grid gap-3">
              {scan.data.map((tmpl) => (
                <div
                  key={`${tmpl.node}-${tmpl.vmid}`}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900">{tmpl.name || `VM ${tmpl.vmid}`}</span>
                      <span className="text-xs px-1.5 py-0.5 bg-gray-200 text-gray-600 rounded">
                        VMID {tmpl.vmid}
                      </span>
                      <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">
                        {tmpl.node}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      Disk: {formatBytes(tmpl.disk_size)} | RAM: {formatBytes(tmpl.memory)}
                    </div>
                  </div>
                  {alreadyMappedVmids.has(tmpl.vmid) ? (
                    <span className="text-xs text-green-600 font-medium">Mapped</span>
                  ) : (
                    <button
                      onClick={() => handleAddFromScan(tmpl)}
                      className="px-3 py-1 text-xs font-medium text-indigo-600 border border-indigo-300 rounded hover:bg-indigo-50"
                    >
                      Add
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Add Form */}
      {addForm && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            {addForm.pve_name ? `Add Template: ${addForm.pve_name}` : 'Add Template Manually'}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Key</label>
              <input
                type="text"
                value={addForm.key}
                onChange={(e) => setAddForm({ ...addForm, key: e.target.value })}
                placeholder="ubuntu-2204"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
              <p className="mt-0.5 text-xs text-gray-400">Lowercase, hyphens only. Used internally.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
              <input
                type="text"
                value={addForm.display_name}
                onChange={(e) => setAddForm({ ...addForm, display_name: e.target.value })}
                placeholder="Ubuntu 22.04 LTS"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">VMID</label>
              <input
                type="number"
                value={addForm.vmid || ''}
                onChange={(e) => setAddForm({ ...addForm, vmid: parseInt(e.target.value) || 0 })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Node</label>
              <input
                type="text"
                value={addForm.node}
                onChange={(e) => setAddForm({ ...addForm, node: e.target.value })}
                placeholder="pve-node-01"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">OS Family</label>
              <select
                value={addForm.os_family}
                onChange={(e) => setAddForm({ ...addForm, os_family: e.target.value as 'linux' | 'windows' })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="linux">Linux</option>
                <option value="windows">Windows</option>
              </select>
            </div>
            <div className="flex items-center gap-2 pt-6">
              <input
                type="checkbox"
                id="cloud-init"
                checked={addForm.cloud_init}
                onChange={(e) => setAddForm({ ...addForm, cloud_init: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <label htmlFor="cloud-init" className="text-sm text-gray-700">Cloud-Init Enabled</label>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleSubmitAdd}
              disabled={!addForm.key || !addForm.display_name || !addForm.vmid || !addForm.node || createMapping.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {createMapping.isPending ? 'Saving...' : 'Save Mapping'}
            </button>
            <button
              onClick={() => setAddForm(null)}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
          {createMapping.isError && (
            <p className="mt-2 text-sm text-red-600">
              Failed to save: {(createMapping.error as Error)?.message ?? 'Unknown error'}
            </p>
          )}
        </div>
      )}

      {/* Saved Mappings */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Saved Mappings</h3>
          <p className="text-xs text-gray-500 mt-1">These templates appear in the request form OS dropdown</p>
        </div>

        {isLoading && <p className="p-6 text-gray-500">Loading...</p>}

        {mappings && mappings.length === 0 && (
          <div className="p-6 text-center text-gray-500 text-sm">
            No template mappings yet. Scan Proxmox and add templates above.
          </div>
        )}

        {mappings && mappings.length > 0 && (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Key</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Display Name</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">VMID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Node</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">OS Family</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cloud-Init</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Enabled</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {mappings.map((m) => (
                <tr key={m.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-mono text-gray-700">{m.key}</td>
                  <td className="px-4 py-3 text-sm text-gray-900">{m.display_name}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{m.vmid}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{m.node}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        m.os_family === 'linux'
                          ? 'bg-orange-100 text-orange-700'
                          : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      {m.os_family}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{m.cloud_init ? 'Yes' : 'No'}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() =>
                        updateMapping.mutate({ id: m.id, enabled: !m.enabled })
                      }
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                        m.enabled ? 'bg-indigo-600' : 'bg-gray-200'
                      }`}
                    >
                      <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                          m.enabled ? 'translate-x-4.5' : 'translate-x-0.5'
                        }`}
                      />
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => {
                        if (confirm(`Delete mapping "${m.display_name}"?`)) {
                          deleteMapping.mutate(m.id)
                        }
                      }}
                      className="text-red-500 hover:text-red-700 text-xs font-medium"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
