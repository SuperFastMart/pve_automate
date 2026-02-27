import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useCreateDeployment } from '../hooks/useDeployments'
import { useOSTemplates, useWorkloadTypes, useTShirtSizes } from '../hooks/useVMRequests'
import { getSubnets, getEnvironments } from '../api/client'
import type { DeploymentVMPayload } from '../api/client'

interface VMEntry {
  vm_name: string
  description: string
  os_template: string
  tshirt_size: string
  subnet_id: string
  cpu_cores: string
  ram_mb: string
  disk_gb: string
}

const emptyVM: VMEntry = {
  vm_name: '',
  description: '',
  os_template: '',
  tshirt_size: '',
  subnet_id: '',
  cpu_cores: '',
  ram_mb: '',
  disk_gb: '',
}

export default function DeploymentForm() {
  const navigate = useNavigate()
  const createDeployment = useCreateDeployment()
  const { data: workloadTypes, isLoading: workloadsLoading } = useWorkloadTypes()
  const { data: sizes, isLoading: sizesLoading } = useTShirtSizes()
  const { data: subnets } = useQuery({ queryKey: ['subnets'], queryFn: getSubnets })
  const { data: environments } = useQuery({ queryKey: ['environments'], queryFn: getEnvironments })

  // Top-level fields
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [requestorName, setRequestorName] = useState('')
  const [requestorEmail, setRequestorEmail] = useState('')
  const [workloadType, setWorkloadType] = useState('')
  const [selectedEnvironment, setSelectedEnvironment] = useState('')
  const environmentId = selectedEnvironment ? Number(selectedEnvironment) : undefined
  const { data: templates, isLoading: templatesLoading } = useOSTemplates(environmentId)

  // VM list
  const [vms, setVms] = useState<VMEntry[]>([{ ...emptyVM }])
  const [errors, setErrors] = useState<string[]>([])

  // Auto-select default environment
  useEffect(() => {
    if (environments && environments.length > 0 && !selectedEnvironment) {
      const defaultEnv = environments.find((e) => e.is_default)
      if (defaultEnv) {
        setSelectedEnvironment(String(defaultEnv.id))
      } else if (environments.length === 1) {
        setSelectedEnvironment(String(environments[0].id))
      }
    }
  }, [environments, selectedEnvironment])

  const addVM = () => {
    if (vms.length < 20) {
      setVms([...vms, { ...emptyVM }])
    }
  }

  const removeVM = (index: number) => {
    if (vms.length > 1) {
      setVms(vms.filter((_, i) => i !== index))
    }
  }

  const updateVM = (index: number, field: keyof VMEntry, value: string) => {
    const updated = [...vms]
    updated[index] = { ...updated[index], [field]: value }
    setVms(updated)
  }

  const sizeOptions = sizes ? ['', ...Object.keys(sizes), 'Custom'] : ['']

  const validate = (): string[] => {
    const errs: string[] = []
    if (!name.trim()) errs.push('Deployment name is required')
    if (!requestorName.trim()) errs.push('Your name is required')
    if (!requestorEmail.trim()) errs.push('Your email is required')
    if (!workloadType) errs.push('Workload type is required')

    vms.forEach((vm, i) => {
      const label = `VM ${i + 1}`
      if (!vm.vm_name.trim()) errs.push(`${label}: VM name is required`)
      if (!vm.os_template) errs.push(`${label}: OS template is required`)
      if (!vm.tshirt_size) errs.push(`${label}: Size is required`)
      if (vm.tshirt_size === 'Custom') {
        if (!vm.cpu_cores) errs.push(`${label}: CPU cores required for custom size`)
        if (!vm.ram_mb) errs.push(`${label}: RAM required for custom size`)
        if (!vm.disk_gb) errs.push(`${label}: Disk required for custom size`)
      }
    })

    return errs
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errs = validate()
    if (errs.length > 0) {
      setErrors(errs)
      return
    }
    setErrors([])

    const vmPayloads: DeploymentVMPayload[] = vms.map((vm) => ({
      vm_name: vm.vm_name,
      ...(vm.description ? { description: vm.description } : {}),
      os_template: vm.os_template,
      tshirt_size: vm.tshirt_size,
      ...(vm.subnet_id ? { subnet_id: Number(vm.subnet_id) } : {}),
      ...(vm.tshirt_size === 'Custom'
        ? {
            cpu_cores: Number(vm.cpu_cores),
            ram_mb: Number(vm.ram_mb),
            disk_gb: Number(vm.disk_gb),
          }
        : {}),
    }))

    const result = await createDeployment.mutateAsync({
      name,
      ...(description ? { description } : {}),
      requestor_name: requestorName,
      requestor_email: requestorEmail,
      workload_type: workloadType,
      ...(selectedEnvironment ? { environment_id: Number(selectedEnvironment) } : {}),
      vms: vmPayloads,
    })

    navigate(`/deployment/${result.id}`)
  }

  if (templatesLoading || workloadsLoading || sizesLoading) {
    return <div className="text-center py-12 text-gray-500">Loading configuration...</div>
  }

  const templateEntries = templates ? Object.entries(templates) : []

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      {/* Requestor Info */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Your Details</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input
              value={requestorName}
              onChange={(e) => setRequestorName(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
              placeholder="John Smith"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={requestorEmail}
              onChange={(e) => setRequestorEmail(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
              placeholder="john.smith@company.com"
            />
          </div>
        </div>
      </div>

      {/* Deployment Info */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Deployment Details</h2>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Deployment Name</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                placeholder="VBR Infrastructure"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Workload Type</label>
              <select
                value={workloadType}
                onChange={(e) => setWorkloadType(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
              >
                <option value="">Select workload type...</option>
                {workloadTypes?.map((wt) => (
                  <option key={wt.key} value={wt.key}>{wt.display_name}</option>
                ))}
              </select>
            </div>
          </div>

          {environments && environments.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Environment</label>
              <select
                value={selectedEnvironment}
                onChange={(e) => {
                  setSelectedEnvironment(e.target.value)
                  setVms(vms.map((vm) => ({ ...vm, os_template: '' })))
                }}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
              >
                {environments.length > 1 && <option value="">Select environment...</option>}
                {environments.map((env) => (
                  <option key={env.id} value={env.id}>
                    {env.display_name}{env.description ? ` — ${env.description}` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
              placeholder="What is this deployment for?"
            />
          </div>
        </div>
      </div>

      {/* VM List */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Virtual Machines ({vms.length})
          </h2>
          <button
            type="button"
            onClick={addVM}
            disabled={vms.length >= 20}
            className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            + Add VM
          </button>
        </div>

        <div className="space-y-4">
          {vms.map((vm, index) => (
            <div key={index} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-700">VM {index + 1}</h3>
                {vms.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeVM(index)}
                    className="text-red-500 hover:text-red-700 text-xs font-medium"
                  >
                    Remove
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">VM Name</label>
                  <input
                    value={vm.vm_name}
                    onChange={(e) => updateVM(index, 'vm_name', e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                    placeholder="app-server-01"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Operating System</label>
                  <select
                    value={vm.os_template}
                    onChange={(e) => updateVM(index, 'os_template', e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                  >
                    <option value="">Select OS...</option>
                    {templateEntries.map(([key, tmpl]) => (
                      <option key={key} value={key}>{tmpl.display_name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Size</label>
                  <select
                    value={vm.tshirt_size}
                    onChange={(e) => updateVM(index, 'tshirt_size', e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                  >
                    {sizeOptions.map((key) => (
                      <option key={key} value={key}>
                        {key === '' ? 'Select size...' : key === 'Custom' ? 'Custom' : `${key} — ${sizes![key].description}`}
                      </option>
                    ))}
                  </select>
                </div>

                {subnets && subnets.length > 0 && (
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Subnet</label>
                    <select
                      value={vm.subnet_id}
                      onChange={(e) => updateVM(index, 'subnet_id', e.target.value)}
                      className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                    >
                      <option value="">No subnet</option>
                      {subnets.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.description ? `${s.description} (${s.subnet}/${s.mask})` : `${s.subnet}/${s.mask}`}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {/* Custom size inputs */}
              {vm.tshirt_size === 'Custom' && (
                <div className="grid grid-cols-3 gap-3 mt-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">CPU Cores</label>
                    <input
                      type="number"
                      value={vm.cpu_cores}
                      onChange={(e) => updateVM(index, 'cpu_cores', e.target.value)}
                      min={1} max={128}
                      className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                      placeholder="4"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">RAM (MB)</label>
                    <input
                      type="number"
                      value={vm.ram_mb}
                      onChange={(e) => updateVM(index, 'ram_mb', e.target.value)}
                      min={512} max={524288} step={512}
                      className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                      placeholder="8192"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Disk (GB)</label>
                    <input
                      type="number"
                      value={vm.disk_gb}
                      onChange={(e) => updateVM(index, 'disk_gb', e.target.value)}
                      min={8} max={4096}
                      className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                      placeholder="256"
                    />
                  </div>
                </div>
              )}

              {/* Optional description */}
              <div className="mt-3">
                <label className="block text-xs font-medium text-gray-600 mb-1">Description (optional)</label>
                <input
                  value={vm.description}
                  onChange={(e) => updateVM(index, 'description', e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                  placeholder="Application server"
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Errors */}
      {errors.length > 0 && (
        <div className="rounded-md bg-red-50 p-4">
          <ul className="text-sm text-red-700 list-disc list-inside space-y-1">
            {errors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Submit */}
      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={createDeployment.isPending}
          className="px-6 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {createDeployment.isPending ? 'Submitting...' : `Submit Deployment (${vms.length} VM${vms.length > 1 ? 's' : ''})`}
        </button>
      </div>

      {createDeployment.isError && (
        <div className="rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-700">
            Failed to submit deployment. Please try again.
          </p>
        </div>
      )}
    </form>
  )
}
