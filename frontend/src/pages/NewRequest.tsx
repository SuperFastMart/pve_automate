import { useState } from 'react'
import VMRequestForm from '../components/VMRequestForm'
import DeploymentForm from '../components/DeploymentForm'
import type { ResourceType } from '../types'

type RequestMode = 'single' | 'deployment'

export default function NewRequest() {
  const [mode, setMode] = useState<RequestMode>('single')
  const [resourceType, setResourceType] = useState<ResourceType>('vm')

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        {mode === 'single'
          ? resourceType === 'lxc' ? 'New LXC Container Request' : 'New VM Request'
          : resourceType === 'lxc' ? 'New LXC Deployment' : 'New Deployment'}
      </h1>

      {/* Mode & Resource Type Toggle */}
      <div className="flex gap-6 mb-6">
        <div className="flex gap-2">
          <button
            onClick={() => setMode('single')}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              mode === 'single'
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Single
          </button>
          <button
            onClick={() => setMode('deployment')}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              mode === 'deployment'
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Multi-Deployment
          </button>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setResourceType('vm')}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              resourceType === 'vm'
                ? 'bg-emerald-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            VM
          </button>
          <button
            onClick={() => setResourceType('lxc')}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              resourceType === 'lxc'
                ? 'bg-emerald-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            LXC Container
          </button>
        </div>
      </div>

      {mode === 'single'
        ? <VMRequestForm resourceType={resourceType} />
        : <DeploymentForm resourceType={resourceType} />}
    </div>
  )
}
