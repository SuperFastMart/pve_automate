import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useVMRequests, useApproveVMRequest, useRejectVMRequest, useRetryVMRequest } from '../hooks/useVMRequests'
import { useDeployments, useApproveDeployment, useRejectDeployment, useRetryDeployment } from '../hooks/useDeployments'
import StatusBadge from '../components/StatusBadge'
import AdminSettings from '../components/AdminSettings'
import AdminTemplates from '../components/AdminTemplates'
import AdminEnvironments from '../components/AdminEnvironments'
import type { RequestStatus, DeploymentStatus } from '../types'

const statusFilters: { label: string; value: RequestStatus | '' }[] = [
  { label: 'All', value: '' },
  { label: 'Pending', value: 'pending_approval' },
  { label: 'Approved', value: 'approved' },
  { label: 'Provisioning', value: 'provisioning' },
  { label: 'Completed', value: 'completed' },
  { label: 'Rejected', value: 'rejected' },
  { label: 'Failed', value: 'provisioning_failed' },
]

const deploymentStatusColors: Record<DeploymentStatus, string> = {
  pending_approval: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-blue-100 text-blue-800',
  rejected: 'bg-red-100 text-red-800',
  provisioning: 'bg-purple-100 text-purple-800',
  partially_completed: 'bg-amber-100 text-amber-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
}

const deploymentStatusLabels: Record<DeploymentStatus, string> = {
  pending_approval: 'Pending',
  approved: 'Approved',
  rejected: 'Rejected',
  provisioning: 'Provisioning',
  partially_completed: 'Partial',
  completed: 'Completed',
  failed: 'Failed',
}

type AdminTab = 'requests' | 'settings' | 'templates' | 'environments'
type RequestsView = 'individual' | 'deployments'

export default function Admin() {
  const [activeTab, setActiveTab] = useState<AdminTab>('requests')
  const [requestsView, setRequestsView] = useState<RequestsView>('individual')
  const [activeFilter, setActiveFilter] = useState<string>('')
  const { data, isLoading, error } = useVMRequests(1, 100)
  const approve = useApproveVMRequest()
  const reject = useRejectVMRequest()
  const retry = useRetryVMRequest()

  const { data: deploymentData, isLoading: deploymentsLoading } = useDeployments(1, 100)
  const approveDeployment = useApproveDeployment()
  const rejectDeployment = useRejectDeployment()
  const retryDeployment = useRetryDeployment()

  const filteredItems = data?.items.filter(
    (req) => !activeFilter || req.status === activeFilter
  ) ?? []

  const statusCounts = data?.items.reduce<Record<string, number>>((acc, req) => {
    acc[req.status] = (acc[req.status] || 0) + 1
    return acc
  }, {}) ?? {}

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Admin Console</h1>
        <p className="text-sm text-gray-500 mt-1">Manage VM provisioning requests and settings</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('requests')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            activeTab === 'requests'
              ? 'border-indigo-500 text-indigo-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          Requests
        </button>
        <button
          onClick={() => setActiveTab('settings')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            activeTab === 'settings'
              ? 'border-indigo-500 text-indigo-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          Settings
        </button>
        <button
          onClick={() => setActiveTab('templates')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            activeTab === 'templates'
              ? 'border-indigo-500 text-indigo-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          Templates
        </button>
        <button
          onClick={() => setActiveTab('environments')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            activeTab === 'environments'
              ? 'border-indigo-500 text-indigo-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          Environments
        </button>
      </div>

      {activeTab === 'settings' && <AdminSettings />}
      {activeTab === 'templates' && <AdminTemplates />}
      {activeTab === 'environments' && <AdminEnvironments />}

      {activeTab === 'requests' && (
        <>
          {/* Sub-toggle: Individual / Deployments */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setRequestsView('individual')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                requestsView === 'individual'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              Individual VMs
            </button>
            <button
              onClick={() => setRequestsView('deployments')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                requestsView === 'deployments'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              Deployments
              {deploymentData && deploymentData.total > 0 && (
                <span className="ml-1.5 px-1.5 py-0.5 text-xs bg-white/20 rounded-full">{deploymentData.total}</span>
              )}
            </button>
          </div>

          {requestsView === 'individual' && (
            <>
              {/* Stats Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                <div className="bg-white rounded-lg shadow p-4">
                  <p className="text-sm text-gray-500">Total Requests</p>
                  <p className="text-2xl font-bold text-gray-900">{data?.total ?? 0}</p>
                </div>
                <div className="bg-yellow-50 rounded-lg shadow p-4">
                  <p className="text-sm text-yellow-700">Pending Approval</p>
                  <p className="text-2xl font-bold text-yellow-800">{statusCounts['pending_approval'] ?? 0}</p>
                </div>
                <div className="bg-purple-50 rounded-lg shadow p-4">
                  <p className="text-sm text-purple-700">Provisioning</p>
                  <p className="text-2xl font-bold text-purple-800">{statusCounts['provisioning'] ?? 0}</p>
                </div>
                <div className="bg-green-50 rounded-lg shadow p-4">
                  <p className="text-sm text-green-700">Completed</p>
                  <p className="text-2xl font-bold text-green-800">{statusCounts['completed'] ?? 0}</p>
                </div>
              </div>

              {/* Filters */}
              <div className="flex gap-2 mb-4 flex-wrap">
                {statusFilters.map((filter) => (
                  <button
                    key={filter.value}
                    onClick={() => setActiveFilter(filter.value)}
                    className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                      activeFilter === filter.value
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {filter.label}
                    {filter.value && statusCounts[filter.value] ? ` (${statusCounts[filter.value]})` : ''}
                  </button>
                ))}
              </div>

              {isLoading && <p className="text-gray-500">Loading...</p>}
              {error && <p className="text-red-600">Failed to load requests.</p>}

              {filteredItems.length === 0 && !isLoading && (
                <div className="text-center py-12 bg-white rounded-lg shadow">
                  <p className="text-gray-500">No requests match the current filter.</p>
                </div>
              )}

              {filteredItems.length > 0 && (
                <div className="bg-white rounded-lg shadow overflow-hidden">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">VM Name</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Requestor</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Workload</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">OS</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {filteredItems.map((req) => (
                        <tr key={req.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm text-gray-500">#{req.id}</td>
                          <td className="px-4 py-3">
                            <Link
                              to={`/request/${req.id}`}
                              className="text-indigo-600 hover:text-indigo-900 text-sm font-medium"
                            >
                              {req.vm_name}
                            </Link>
                            {req.deployment_id && (
                              <Link to={`/deployment/${req.deployment_id}`} className="ml-1 text-xs text-gray-400 hover:text-indigo-500">
                                (deployment)
                              </Link>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <div className="text-sm text-gray-900">{req.requestor_name}</div>
                            <div className="text-xs text-gray-500">{req.requestor_email}</div>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500">{req.workload_type}</td>
                          <td className="px-4 py-3 text-sm text-gray-500">{req.os_template}</td>
                          <td className="px-4 py-3">
                            <span className="text-sm font-medium text-gray-700">{req.tshirt_size}</span>
                            <div className="text-xs text-gray-400">
                              {req.cpu_cores}C / {req.ram_mb >= 1024 ? `${req.ram_mb / 1024}G` : `${req.ram_mb}M`} / {req.disk_gb}G
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadge status={req.status} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500 font-mono">
                            {req.ip_address ?? '-'}
                          </td>
                          <td className="px-4 py-3 text-xs text-gray-500">
                            {new Date(req.created_at).toLocaleString()}
                          </td>
                          <td className="px-4 py-3">
                            {req.status === 'pending_approval' && !req.deployment_id && (
                              <div className="flex gap-2">
                                <button
                                  onClick={() => approve.mutate(req.id)}
                                  disabled={approve.isPending}
                                  className="px-2 py-1 text-xs font-medium text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50"
                                >
                                  Approve
                                </button>
                                <button
                                  onClick={() => reject.mutate(req.id)}
                                  disabled={reject.isPending}
                                  className="px-2 py-1 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50"
                                >
                                  Reject
                                </button>
                              </div>
                            )}
                            {req.status === 'provisioning_failed' && !req.deployment_id && (
                              <button
                                onClick={() => retry.mutate(req.id)}
                                disabled={retry.isPending}
                                className="px-2 py-1 text-xs font-medium text-white bg-amber-600 rounded hover:bg-amber-700 disabled:opacity-50"
                              >
                                {retry.isPending ? 'Retrying...' : 'Retry'}
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {requestsView === 'deployments' && (
            <>
              {deploymentsLoading && <p className="text-gray-500">Loading...</p>}

              {deploymentData && deploymentData.items.length === 0 && !deploymentsLoading && (
                <div className="text-center py-12 bg-white rounded-lg shadow">
                  <p className="text-gray-500">No deployments yet.</p>
                </div>
              )}

              {deploymentData && deploymentData.items.length > 0 && (
                <div className="bg-white rounded-lg shadow overflow-hidden">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Requestor</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Workload</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Environment</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">VMs</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Jira</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {deploymentData.items.map((dep) => (
                        <tr key={dep.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm text-gray-500">#{dep.id}</td>
                          <td className="px-4 py-3">
                            <Link
                              to={`/deployment/${dep.id}`}
                              className="text-indigo-600 hover:text-indigo-900 text-sm font-medium"
                            >
                              {dep.name}
                            </Link>
                          </td>
                          <td className="px-4 py-3">
                            <div className="text-sm text-gray-900">{dep.requestor_name}</div>
                            <div className="text-xs text-gray-500">{dep.requestor_email}</div>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500">{dep.workload_type}</td>
                          <td className="px-4 py-3 text-sm text-gray-500">{dep.environment_name ?? '-'}</td>
                          <td className="px-4 py-3 text-sm font-medium text-gray-700">{dep.vm_count}</td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${deploymentStatusColors[dep.status]}`}>
                              {deploymentStatusLabels[dep.status]}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500">{dep.jira_issue_key ?? '-'}</td>
                          <td className="px-4 py-3 text-xs text-gray-500">
                            {new Date(dep.created_at).toLocaleString()}
                          </td>
                          <td className="px-4 py-3">
                            {dep.status === 'pending_approval' && (
                              <div className="flex gap-2">
                                <button
                                  onClick={() => approveDeployment.mutate(dep.id)}
                                  disabled={approveDeployment.isPending}
                                  className="px-2 py-1 text-xs font-medium text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50"
                                >
                                  Approve
                                </button>
                                <button
                                  onClick={() => rejectDeployment.mutate(dep.id)}
                                  disabled={rejectDeployment.isPending}
                                  className="px-2 py-1 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50"
                                >
                                  Reject
                                </button>
                              </div>
                            )}
                            {(dep.status === 'failed' || dep.status === 'partially_completed') && (
                              <button
                                onClick={() => retryDeployment.mutate(dep.id)}
                                disabled={retryDeployment.isPending}
                                className="px-2 py-1 text-xs font-medium text-white bg-amber-600 rounded hover:bg-amber-700 disabled:opacity-50"
                              >
                                {retryDeployment.isPending ? 'Retrying...' : 'Retry Failed'}
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
