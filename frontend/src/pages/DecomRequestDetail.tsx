import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useDecomRequest, useApproveDecomRequest, useRejectDecomRequest, useStartDecomRequest, useCompleteDecomRequest, useCancelDecomRequest, useDeleteDecomRequest } from '../hooks/useDecomRequests'
import { useAuth } from '../auth/AuthContext'
import StatusBadge from '../components/StatusBadge'

export default function DecomRequestDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const isAdmin = user?.isAdmin ?? false
  const { data: decom, isLoading, error } = useDecomRequest(Number(id))

  const approve = useApproveDecomRequest()
  const reject = useRejectDecomRequest()
  const start = useStartDecomRequest()
  const complete = useCompleteDecomRequest()
  const cancel = useCancelDecomRequest()
  const deleteDecom = useDeleteDecomRequest()

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showCompleteConfirm, setShowCompleteConfirm] = useState(false)

  if (isLoading) return <p className="text-gray-500">Loading...</p>
  if (error || !decom) return <p className="text-red-600">Decom request not found.</p>

  const isPending = decom.status === 'pending_approval'
  const isApproved = decom.status === 'approved'
  const isInProgress = decom.status === 'in_progress'
  const canCancel = isPending || isApproved

  return (
    <div>
      <div className="mb-6">
        <Link to="/" className="text-indigo-600 hover:text-indigo-700 text-sm">
          &larr; Back to Dashboard
        </Link>
      </div>

      <div className="flex items-center gap-4 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Decom: {decom.resource_name || `#${decom.id}`}
        </h1>
        <StatusBadge status={decom.status} />
        {isAdmin && (
          <div className="ml-auto flex items-center gap-2">
            {showDeleteConfirm ? (
              <>
                <span className="text-sm text-gray-600">Delete this record?</span>
                <button
                  onClick={() => deleteDecom.mutate(Number(id), { onSuccess: () => navigate('/') })}
                  disabled={deleteDecom.isPending}
                  className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteDecom.isPending ? 'Deleting...' : 'Confirm'}
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                >
                  Cancel
                </button>
              </>
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

      {decom.error_message && (
        <div className="rounded-md bg-red-50 p-4 mb-6">
          <p className="text-sm font-medium text-red-800">Error: {decom.error_message}</p>
        </div>
      )}

      {/* Admin Actions */}
      {isAdmin && (isPending || isApproved || isInProgress) && (
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Admin Actions</h3>
          <div className="flex flex-wrap gap-2">
            {isPending && (
              <>
                <button
                  onClick={() => approve.mutate(Number(id))}
                  disabled={approve.isPending}
                  className="px-4 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                >
                  {approve.isPending ? 'Approving...' : 'Approve'}
                </button>
                <button
                  onClick={() => reject.mutate(Number(id))}
                  disabled={reject.isPending}
                  className="px-4 py-2 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                >
                  {reject.isPending ? 'Rejecting...' : 'Reject'}
                </button>
              </>
            )}
            {isApproved && (
              <button
                onClick={() => start.mutate(Number(id))}
                disabled={start.isPending}
                className="px-4 py-2 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
              >
                {start.isPending ? 'Starting...' : 'Start Teardown'}
              </button>
            )}
            {(isApproved || isInProgress) && (
              showCompleteConfirm ? (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600">This will release IPs and mark resources as decommissioned.</span>
                  <button
                    onClick={() => complete.mutate(Number(id), { onSuccess: () => setShowCompleteConfirm(false) })}
                    disabled={complete.isPending}
                    className="px-4 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                  >
                    {complete.isPending ? 'Completing...' : 'Confirm Complete'}
                  </button>
                  <button
                    onClick={() => setShowCompleteConfirm(false)}
                    className="px-3 py-2 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowCompleteConfirm(true)}
                  className="px-4 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700"
                >
                  Mark Complete
                </button>
              )
            )}
            {canCancel && (
              <button
                onClick={() => cancel.mutate(Number(id))}
                disabled={cancel.isPending}
                className="px-4 py-2 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
              >
                {cancel.isPending ? 'Cancelling...' : 'Cancel Request'}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Non-admin cancel */}
      {!isAdmin && canCancel && decom.requestor_email === user?.email && (
        <div className="mb-6">
          <button
            onClick={() => cancel.mutate(Number(id))}
            disabled={cancel.isPending}
            className="px-4 py-2 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
          >
            {cancel.isPending ? 'Cancelling...' : 'Cancel Request'}
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Decom Details */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Decom Details</h2>
          <dl className="space-y-3">
            <div>
              <dt className="text-sm font-medium text-gray-500">Resource</dt>
              <dd className="text-sm text-gray-900">
                {decom.resource_name || '-'}
                {decom.resource_type && (
                  <span className="ml-2 text-xs text-gray-400">
                    ({decom.resource_type === 'lxc' ? 'Container' : decom.resource_type === 'vm' ? 'VM' : 'Deployment'})
                  </span>
                )}
              </dd>
            </div>
            {decom.ip_address && (
              <div>
                <dt className="text-sm font-medium text-gray-500">IP Address</dt>
                <dd className="text-sm text-gray-900 font-mono">{decom.ip_address}</dd>
              </div>
            )}
            <div>
              <dt className="text-sm font-medium text-gray-500">Requestor</dt>
              <dd className="text-sm text-gray-900">{decom.requestor_name} ({decom.requestor_email})</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Reason</dt>
              <dd className="text-sm text-gray-900">{decom.reason}</dd>
            </div>
            {decom.review_date && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Review Date</dt>
                <dd className="text-sm text-gray-900">{new Date(decom.review_date).toLocaleDateString()}</dd>
              </div>
            )}
            {decom.notes && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Admin Notes</dt>
                <dd className="text-sm text-gray-900">{decom.notes}</dd>
              </div>
            )}
          </dl>
        </div>

        {/* Integration */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Integration</h2>
          <dl className="space-y-3">
            <div>
              <dt className="text-sm font-medium text-gray-500">Jira Ticket</dt>
              <dd className="text-sm text-gray-900">
                {decom.jira_issue_url && decom.jira_issue_key ? (
                  <a href={decom.jira_issue_url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-700">
                    {decom.jira_issue_key}
                  </a>
                ) : '-'}
              </dd>
            </div>
            {decom.vm_request_id && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Linked Request</dt>
                <dd className="text-sm">
                  <Link to={`/request/${decom.vm_request_id}`} className="text-indigo-600 hover:text-indigo-700">
                    Request #{decom.vm_request_id}
                  </Link>
                </dd>
              </div>
            )}
            {decom.deployment_id && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Linked Deployment</dt>
                <dd className="text-sm">
                  <Link to={`/deployment/${decom.deployment_id}`} className="text-indigo-600 hover:text-indigo-700">
                    Deployment #{decom.deployment_id}
                  </Link>
                </dd>
              </div>
            )}
          </dl>
        </div>
      </div>

      {/* Timeline */}
      <div className="bg-white rounded-lg shadow p-6 mt-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Timeline</h2>
        <div className="flex flex-wrap gap-6 text-sm">
          <div>
            <span className="text-gray-500">Submitted:</span>{' '}
            <span className="text-gray-900">{new Date(decom.created_at).toLocaleString()}</span>
          </div>
          {decom.approved_at && (
            <div>
              <span className="text-gray-500">Approved:</span>{' '}
              <span className="text-gray-900">{new Date(decom.approved_at).toLocaleString()}</span>
            </div>
          )}
          {decom.completed_at && (
            <div>
              <span className="text-gray-500">Completed:</span>{' '}
              <span className="text-gray-900">{new Date(decom.completed_at).toLocaleString()}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
