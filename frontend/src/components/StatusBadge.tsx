import type { RequestStatus, DecomStatus } from '../types'

const statusConfig: Record<string, { label: string; className: string }> = {
  pending_approval: { label: 'Pending Approval', className: 'bg-yellow-100 text-yellow-800' },
  approved: { label: 'Approved', className: 'bg-blue-100 text-blue-800' },
  rejected: { label: 'Rejected', className: 'bg-red-100 text-red-800' },
  provisioning: { label: 'Provisioning', className: 'bg-purple-100 text-purple-800' },
  provisioning_failed: { label: 'Failed', className: 'bg-red-100 text-red-800' },
  completed: { label: 'Completed', className: 'bg-green-100 text-green-800' },
  decommissioned: { label: 'Decommissioned', className: 'bg-gray-100 text-gray-800' },
  in_progress: { label: 'In Progress', className: 'bg-purple-100 text-purple-800' },
  cancelled: { label: 'Cancelled', className: 'bg-gray-100 text-gray-500' },
}

export default function StatusBadge({ status }: { status: RequestStatus | DecomStatus }) {
  const config = statusConfig[status] ?? { label: status, className: 'bg-gray-100 text-gray-800' }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  )
}
