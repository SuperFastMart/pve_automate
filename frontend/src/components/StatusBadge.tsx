import type { RequestStatus } from '../types'

const statusConfig: Record<RequestStatus, { label: string; className: string }> = {
  pending_approval: { label: 'Pending Approval', className: 'bg-yellow-100 text-yellow-800' },
  approved: { label: 'Approved', className: 'bg-blue-100 text-blue-800' },
  rejected: { label: 'Rejected', className: 'bg-red-100 text-red-800' },
  provisioning: { label: 'Provisioning', className: 'bg-purple-100 text-purple-800' },
  provisioning_failed: { label: 'Failed', className: 'bg-red-100 text-red-800' },
  completed: { label: 'Completed', className: 'bg-green-100 text-green-800' },
}

export default function StatusBadge({ status }: { status: RequestStatus }) {
  const config = statusConfig[status]
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  )
}
