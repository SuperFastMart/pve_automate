import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useVMRequest, useDeleteVMRequest } from '../hooks/useVMRequests'
import { useAuth } from '../auth/AuthContext'
import StatusBadge from '../components/StatusBadge'

export default function RequestDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const isAdmin = user?.isAdmin ?? false
  const { data: req, isLoading, error } = useVMRequest(Number(id))
  const deleteRequest = useDeleteVMRequest()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  if (isLoading) return <p className="text-gray-500">Loading...</p>
  if (error || !req) return <p className="text-red-600">Request not found.</p>

  const isLXC = req.resource_type === 'lxc'

  const details = [
    { label: isLXC ? 'Container Name' : 'VM Name', value: req.vm_name },
    { label: 'Resource Type', value: isLXC ? 'LXC Container' : 'Virtual Machine' },
    { label: 'Description', value: req.description || '-' },
    { label: 'Requestor', value: `${req.requestor_name} (${req.requestor_email})` },
    { label: 'Workload Type', value: req.workload_type },
    { label: isLXC ? 'CT Template' : 'Operating System', value: req.os_template },
    { label: 'Size', value: `${req.tshirt_size} (${req.cpu_cores} vCPU, ${req.ram_mb >= 1024 ? `${req.ram_mb / 1024} GB` : `${req.ram_mb} MB`} RAM, ${req.disk_gb} GB disk)` },
    ...(req.environment_name ? [{ label: 'Environment', value: req.environment_name }] : []),
    ...(isLXC && req.bridge ? [{ label: 'Bridge', value: req.bridge }] : []),
    ...(isLXC && req.vlan_tag ? [{ label: 'VLAN Tag', value: String(req.vlan_tag) }] : []),
    ...(isLXC && req.mtu ? [{ label: 'MTU', value: String(req.mtu) }] : []),
    ...(isLXC ? [{ label: 'Root SSH Login', value: req.enable_ssh_root ? 'Enabled' : 'Disabled' }] : []),
    ...(isLXC && req.root_password ? [{ label: 'Root Password', value: req.root_password }] : []),
  ]

  const provisioningDetails = [
    { label: 'Jira Ticket', value: req.jira_issue_key, link: req.jira_issue_url },
    { label: 'VM ID', value: req.hypervisor_vm_id ?? req.proxmox_vmid },
    { label: 'Host', value: req.hypervisor_host ?? req.proxmox_node },
    { label: 'IP Address', value: req.ip_address },
    ...(req.ip_gateway ? [{ label: 'Gateway', value: req.ip_gateway }] : []),
    ...(req.nameserver ? [{ label: 'Nameserver', value: req.nameserver }] : []),
  ]

  return (
    <div>
      <div className="mb-6">
        <Link to="/" className="text-indigo-600 hover:text-indigo-700 text-sm">
          &larr; Back to Dashboard
        </Link>
      </div>

      <div className="flex items-center gap-4 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{req.vm_name}</h1>
        <StatusBadge status={req.status} />
        {isAdmin && (
          <div className="ml-auto">
            {showDeleteConfirm ? (
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-600">Delete this request?</span>
                <button
                  onClick={() => {
                    deleteRequest.mutate(Number(id), {
                      onSuccess: () => navigate('/'),
                    })
                  }}
                  disabled={deleteRequest.isPending}
                  className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteRequest.isPending ? 'Deleting...' : 'Confirm'}
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200"
              >
                Delete
              </button>
            )}
          </div>
        )}
      </div>

      {req.error_message && (
        <div className="rounded-md bg-red-50 p-4 mb-6">
          <p className="text-sm font-medium text-red-800">Error: {req.error_message}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Request Details */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Request Details</h2>
          <dl className="space-y-3">
            {details.map(({ label, value }) => (
              <div key={label}>
                <dt className="text-sm font-medium text-gray-500">{label}</dt>
                <dd className="text-sm text-gray-900">{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        {/* Provisioning Details */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Provisioning Details</h2>
          <dl className="space-y-3">
            {provisioningDetails.map(({ label, value, link }) => (
              <div key={label}>
                <dt className="text-sm font-medium text-gray-500">{label}</dt>
                <dd className="text-sm text-gray-900">
                  {link && value ? (
                    <a href={link} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-700">
                      {String(value)}
                    </a>
                  ) : (
                    String(value ?? '-')
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {/* Timestamps */}
      <div className="bg-white rounded-lg shadow p-6 mt-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Timeline</h2>
        <div className="flex flex-wrap gap-6 text-sm">
          <div>
            <span className="text-gray-500">Created:</span>{' '}
            <span className="text-gray-900">{new Date(req.created_at).toLocaleString()}</span>
          </div>
          {req.approved_at && (
            <div>
              <span className="text-gray-500">Approved:</span>{' '}
              <span className="text-gray-900">{new Date(req.approved_at).toLocaleString()}</span>
            </div>
          )}
          {req.completed_at && (
            <div>
              <span className="text-gray-500">Completed:</span>{' '}
              <span className="text-gray-900">{new Date(req.completed_at).toLocaleString()}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
