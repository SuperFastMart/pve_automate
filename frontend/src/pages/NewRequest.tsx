import { useState } from 'react'
import VMRequestForm from '../components/VMRequestForm'
import DeploymentForm from '../components/DeploymentForm'

type RequestMode = 'single' | 'deployment'

export default function NewRequest() {
  const [mode, setMode] = useState<RequestMode>('single')

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        {mode === 'single' ? 'New VM Request' : 'New Deployment'}
      </h1>

      {/* Mode Toggle */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setMode('single')}
          className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
            mode === 'single'
              ? 'bg-indigo-600 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          Single VM
        </button>
        <button
          onClick={() => setMode('deployment')}
          className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
            mode === 'deployment'
              ? 'bg-indigo-600 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          Multi-VM Deployment
        </button>
      </div>

      {mode === 'single' ? <VMRequestForm /> : <DeploymentForm />}
    </div>
  )
}
