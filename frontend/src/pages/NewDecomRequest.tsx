import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getVMRequests, getDeployments } from '../api/client'
import { useCreateDecomRequest } from '../hooks/useDecomRequests'

export default function NewDecomRequest() {
  const navigate = useNavigate()
  const createDecom = useCreateDecomRequest()
  const [targetType, setTargetType] = useState<'vm' | 'deployment'>('vm')
  const [targetId, setTargetId] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')

  // Fetch completed VMs/CTs (large page to get all)
  const { data: vmData } = useQuery({
    queryKey: ['vm-requests', 1, 100],
    queryFn: () => getVMRequests(1, 100),
  })
  const { data: depData } = useQuery({
    queryKey: ['deployments', 1, 100],
    queryFn: () => getDeployments(1, 100),
  })

  // Filter to only completed/failed resources (decomm-able)
  const eligibleVMs = vmData?.items.filter(
    (r) => r.status === 'completed' || r.status === 'provisioning_failed'
  ) ?? []
  const eligibleDeployments = depData?.items.filter(
    (d) => d.status === 'completed' || d.status === 'partially_completed' || d.status === 'failed'
  ) ?? []

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!targetId) {
      setError('Please select a resource to decommission')
      return
    }
    if (!reason.trim()) {
      setError('Please provide a reason')
      return
    }

    createDecom.mutate(
      {
        ...(targetType === 'vm'
          ? { vm_request_id: Number(targetId) }
          : { deployment_id: Number(targetId) }),
        reason: reason.trim(),
      },
      {
        onSuccess: (data) => navigate(`/decom/${data.id}`),
        onError: (err) => setError(err.message || 'Failed to create decom request'),
      }
    )
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Decom Request</h1>
      <p className="text-sm text-gray-500 mb-6">
        Request decommissioning of a VM, container, or deployment. This will create a Jira ticket for approval.
        Once approved and completed, resources are destroyed automatically.
      </p>

      <form onSubmit={handleSubmit} className="space-y-5">
        {error && (
          <div className="rounded-md bg-red-50 p-3">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Target type selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Resource Type</label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="targetType"
                value="vm"
                checked={targetType === 'vm'}
                onChange={() => { setTargetType('vm'); setTargetId('') }}
                className="text-indigo-600"
              />
              Individual VM / CT
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="targetType"
                value="deployment"
                checked={targetType === 'deployment'}
                onChange={() => { setTargetType('deployment'); setTargetId('') }}
                className="text-indigo-600"
              />
              Deployment
            </label>
          </div>
        </div>

        {/* Resource selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {targetType === 'vm' ? 'Select VM / Container' : 'Select Deployment'}
          </label>
          <select
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">-- Select --</option>
            {targetType === 'vm'
              ? eligibleVMs.map((vm) => (
                  <option key={vm.id} value={vm.id}>
                    {vm.vm_name} ({vm.resource_type === 'lxc' ? 'CT' : 'VM'})
                    {vm.ip_address ? ` — ${vm.ip_address}` : ''}
                  </option>
                ))
              : eligibleDeployments.map((dep) => (
                  <option key={dep.id} value={dep.id}>
                    {dep.name} ({dep.vm_count} VMs)
                  </option>
                ))}
          </select>
          {targetType === 'vm' && eligibleVMs.length === 0 && (
            <p className="mt-1 text-xs text-gray-400">No completed VMs/CTs available for decommissioning</p>
          )}
          {targetType === 'deployment' && eligibleDeployments.length === 0 && (
            <p className="mt-1 text-xs text-gray-400">No completed deployments available for decommissioning</p>
          )}
        </div>

        {/* Reason */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            placeholder="Why is this resource being decommissioned?"
          />
        </div>

        <button
          type="submit"
          disabled={createDecom.isPending}
          className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {createDecom.isPending ? 'Submitting...' : 'Submit Decom Request'}
        </button>
      </form>
    </div>
  )
}
