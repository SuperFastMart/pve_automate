import { useParams, Link } from 'react-router-dom'
import { useDeployment } from '../hooks/useDeployments'
import StatusBadge from '../components/StatusBadge'
import type { DeploymentStatus } from '../types'

function DeploymentStatusBadge({ status }: { status: DeploymentStatus }) {
  const colors: Record<DeploymentStatus, string> = {
    pending_approval: 'bg-yellow-100 text-yellow-800',
    approved: 'bg-blue-100 text-blue-800',
    rejected: 'bg-red-100 text-red-800',
    provisioning: 'bg-purple-100 text-purple-800',
    partially_completed: 'bg-amber-100 text-amber-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  }

  const labels: Record<DeploymentStatus, string> = {
    pending_approval: 'Pending Approval',
    approved: 'Approved',
    rejected: 'Rejected',
    provisioning: 'Provisioning',
    partially_completed: 'Partially Completed',
    completed: 'Completed',
    failed: 'Failed',
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[status]}`}>
      {labels[status]}
    </span>
  )
}

export default function DeploymentDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: deployment, isLoading, error } = useDeployment(Number(id))

  if (isLoading) return <p className="text-gray-500">Loading...</p>
  if (error || !deployment) return <p className="text-red-600">Deployment not found.</p>

  return (
    <div>
      <div className="mb-6">
        <Link to="/" className="text-indigo-600 hover:text-indigo-700 text-sm">
          &larr; Back to Dashboard
        </Link>
      </div>

      <div className="flex items-center gap-4 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{deployment.name}</h1>
        <DeploymentStatusBadge status={deployment.status} />
      </div>

      {deployment.error_message && (
        <div className="rounded-md bg-red-50 p-4 mb-6">
          <p className="text-sm font-medium text-red-800">Error: {deployment.error_message}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Deployment Details */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Deployment Details</h2>
          <dl className="space-y-3">
            <div>
              <dt className="text-sm font-medium text-gray-500">Requestor</dt>
              <dd className="text-sm text-gray-900">{deployment.requestor_name} ({deployment.requestor_email})</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Workload Type</dt>
              <dd className="text-sm text-gray-900">{deployment.workload_type}</dd>
            </div>
            {deployment.environment_name && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Environment</dt>
                <dd className="text-sm text-gray-900">{deployment.environment_name}</dd>
              </div>
            )}
            {deployment.description && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Description</dt>
                <dd className="text-sm text-gray-900">{deployment.description}</dd>
              </div>
            )}
            <div>
              <dt className="text-sm font-medium text-gray-500">VMs</dt>
              <dd className="text-sm text-gray-900">{deployment.vm_requests.length} virtual machines</dd>
            </div>
          </dl>
        </div>

        {/* Integration */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Integration</h2>
          <dl className="space-y-3">
            <div>
              <dt className="text-sm font-medium text-gray-500">Jira Ticket</dt>
              <dd className="text-sm text-gray-900">
                {deployment.jira_issue_url && deployment.jira_issue_key ? (
                  <a href={deployment.jira_issue_url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-700">
                    {deployment.jira_issue_key}
                  </a>
                ) : (
                  '-'
                )}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* VM List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Virtual Machines</h2>
        </div>
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">VM Name</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">OS</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">VM ID</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Host</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {deployment.vm_requests.map((vm) => (
              <tr key={vm.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <Link to={`/request/${vm.id}`} className="text-indigo-600 hover:text-indigo-900 text-sm font-medium">
                    {vm.vm_name}
                  </Link>
                  {vm.description && <div className="text-xs text-gray-400">{vm.description}</div>}
                </td>
                <td className="px-4 py-3 text-sm text-gray-500">{vm.os_template}</td>
                <td className="px-4 py-3">
                  <span className="text-sm font-medium text-gray-700">{vm.tshirt_size}</span>
                  <div className="text-xs text-gray-400">
                    {vm.cpu_cores}C / {vm.ram_mb >= 1024 ? `${vm.ram_mb / 1024}G` : `${vm.ram_mb}M`} / {vm.disk_gb}G
                  </div>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={vm.status} />
                </td>
                <td className="px-4 py-3 text-sm text-gray-500">{vm.hypervisor_vm_id ?? vm.proxmox_vmid ?? '-'}</td>
                <td className="px-4 py-3 text-sm text-gray-500">{vm.hypervisor_host ?? vm.proxmox_node ?? '-'}</td>
                <td className="px-4 py-3 text-sm text-gray-500 font-mono">{vm.ip_address ?? '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Timeline */}
      <div className="bg-white rounded-lg shadow p-6 mt-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Timeline</h2>
        <div className="flex flex-wrap gap-6 text-sm">
          <div>
            <span className="text-gray-500">Created:</span>{' '}
            <span className="text-gray-900">{new Date(deployment.created_at).toLocaleString()}</span>
          </div>
          {deployment.approved_at && (
            <div>
              <span className="text-gray-500">Approved:</span>{' '}
              <span className="text-gray-900">{new Date(deployment.approved_at).toLocaleString()}</span>
            </div>
          )}
          {deployment.completed_at && (
            <div>
              <span className="text-gray-500">Completed:</span>{' '}
              <span className="text-gray-900">{new Date(deployment.completed_at).toLocaleString()}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
