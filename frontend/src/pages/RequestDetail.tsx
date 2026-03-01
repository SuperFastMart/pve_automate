import { useParams, Link } from 'react-router-dom'
import { useVMRequest } from '../hooks/useVMRequests'
import StatusBadge from '../components/StatusBadge'

export default function RequestDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: req, isLoading, error } = useVMRequest(Number(id))

  if (isLoading) return <p className="text-gray-500">Loading...</p>
  if (error || !req) return <p className="text-red-600">Request not found.</p>

  const details = [
    { label: 'VM Name', value: req.vm_name },
    { label: 'Description', value: req.description || '-' },
    { label: 'Requestor', value: `${req.requestor_name} (${req.requestor_email})` },
    { label: 'Workload Type', value: req.workload_type },
    { label: 'Operating System', value: req.os_template },
    { label: 'Size', value: `${req.tshirt_size} (${req.cpu_cores} vCPU, ${req.ram_mb >= 1024 ? `${req.ram_mb / 1024} GB` : `${req.ram_mb} MB`} RAM, ${req.disk_gb} GB disk)` },
    ...(req.environment_name ? [{ label: 'Environment', value: req.environment_name }] : []),
  ]

  const provisioningDetails = [
    { label: 'Jira Ticket', value: req.jira_issue_key, link: req.jira_issue_url },
    { label: 'VM ID', value: req.hypervisor_vm_id ?? req.proxmox_vmid },
    { label: 'Host', value: req.hypervisor_host ?? req.proxmox_node },
    { label: 'IP Address', value: req.ip_address },
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
