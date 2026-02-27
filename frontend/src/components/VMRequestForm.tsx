import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useCreateVMRequest, useTShirtSizes, useOSTemplates, useWorkloadTypes } from '../hooks/useVMRequests'
import { getSubnets, getLocations } from '../api/client'
import TShirtSizeCard from './TShirtSizeCard'

const schema = z.object({
  vm_name: z
    .string()
    .min(1, 'VM name is required')
    .max(63, 'VM name must be 63 characters or less')
    .regex(/^[a-zA-Z0-9][a-zA-Z0-9-]*$/, 'Must start with a letter/number, only letters, numbers and hyphens allowed'),
  description: z.string().optional(),
  requestor_name: z.string().min(1, 'Your name is required'),
  requestor_email: z.string().email('Valid email is required'),
  workload_type: z.string().min(1, 'Workload type is required'),
  os_template: z.string().min(1, 'OS template is required'),
  tshirt_size: z.string().regex(/^(XS|S|M|L|XL)$/, 'Please select a size'),
})

type FormData = z.infer<typeof schema>

export default function VMRequestForm() {
  const navigate = useNavigate()
  const createRequest = useCreateVMRequest()
  const { data: sizes, isLoading: sizesLoading } = useTShirtSizes()
  const { data: templates, isLoading: templatesLoading } = useOSTemplates()
  const { data: workloadTypes, isLoading: workloadsLoading } = useWorkloadTypes()
  const { data: subnets } = useQuery({ queryKey: ['subnets'], queryFn: getSubnets })
  const { data: locations } = useQuery({ queryKey: ['locations'], queryFn: getLocations })
  const [selectedLocation, setSelectedLocation] = useState<string>('')
  const [selectedSubnet, setSelectedSubnet] = useState<string>('')

  // Filter subnets by selected location
  const filteredSubnets = subnets?.filter((s) => {
    if (!selectedLocation) return true
    return s.locationId !== null && String(s.locationId) === selectedLocation
  })

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { tshirt_size: '' },
  })

  const selectedSize = watch('tshirt_size')

  const onSubmit = async (data: FormData) => {
    const payload = {
      ...data,
      ...(selectedSubnet ? { subnet_id: Number(selectedSubnet) } : {}),
    }
    const result = await createRequest.mutateAsync(payload)
    navigate(`/request/${result.id}`)
  }

  if (sizesLoading || templatesLoading || workloadsLoading) {
    return <div className="text-center py-12 text-gray-500">Loading configuration...</div>
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
      {/* Requestor Info */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Your Details</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input
              {...register('requestor_name')}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
              placeholder="John Smith"
            />
            {errors.requestor_name && (
              <p className="mt-1 text-sm text-red-600">{errors.requestor_name.message}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              {...register('requestor_email')}
              type="email"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
              placeholder="john.smith@company.com"
            />
            {errors.requestor_email && (
              <p className="mt-1 text-sm text-red-600">{errors.requestor_email.message}</p>
            )}
          </div>
        </div>
      </div>

      {/* VM Details */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">VM Details</h2>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">VM Name</label>
              <input
                {...register('vm_name')}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                placeholder="app-server-01"
              />
              {errors.vm_name && (
                <p className="mt-1 text-sm text-red-600">{errors.vm_name.message}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Workload Type</label>
              <select
                {...register('workload_type')}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
              >
                <option value="">Select workload type...</option>
                {workloadTypes?.map((wt) => (
                  <option key={wt.key} value={wt.key}>
                    {wt.display_name}
                  </option>
                ))}
              </select>
              {errors.workload_type && (
                <p className="mt-1 text-sm text-red-600">{errors.workload_type.message}</p>
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Operating System</label>
            <select
              {...register('os_template')}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
            >
              <option value="">Select operating system...</option>
              {templates && (() => {
                const entries = Object.entries(templates)
                const hasOsFamily = entries.some(([, t]) => t.os_family)
                if (hasOsFamily) {
                  const linux = entries.filter(([, t]) => t.os_family === 'linux')
                  const windows = entries.filter(([, t]) => t.os_family === 'windows')
                  const other = entries.filter(([, t]) => !t.os_family)
                  return (
                    <>
                      {linux.length > 0 && (
                        <optgroup label="Linux">
                          {linux.map(([key, tmpl]) => (
                            <option key={key} value={key}>{tmpl.display_name}</option>
                          ))}
                        </optgroup>
                      )}
                      {windows.length > 0 && (
                        <optgroup label="Windows">
                          {windows.map(([key, tmpl]) => (
                            <option key={key} value={key}>{tmpl.display_name}</option>
                          ))}
                        </optgroup>
                      )}
                      {other.map(([key, tmpl]) => (
                        <option key={key} value={key}>{tmpl.display_name}</option>
                      ))}
                    </>
                  )
                }
                return entries.map(([key, tmpl]) => (
                  <option key={key} value={key}>{tmpl.display_name}</option>
                ))
              })()}
            </select>
            {errors.os_template && (
              <p className="mt-1 text-sm text-red-600">{errors.os_template.message}</p>
            )}
          </div>

          {subnets && subnets.length > 0 && (
            <>
              {locations && locations.length > 1 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
                  <select
                    value={selectedLocation}
                    onChange={(e) => {
                      setSelectedLocation(e.target.value)
                      setSelectedSubnet('')
                    }}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                  >
                    <option value="">All locations</option>
                    {locations.map((loc) => (
                      <option key={loc.id} value={loc.id}>
                        {loc.name}{loc.description ? ` — ${loc.description}` : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Network / Subnet</label>
                <select
                  value={selectedSubnet}
                  onChange={(e) => setSelectedSubnet(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                >
                  <option value="">No subnet (manual IP assignment)</option>
                  {filteredSubnets?.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.description ? `${s.description} (${s.subnet}/${s.mask})` : `${s.subnet}/${s.mask}`}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-400">
                  Select a subnet to auto-allocate an IP address from phpIPAM
                </p>
              </div>
            </>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              {...register('description')}
              rows={3}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
              placeholder="What will this VM be used for?"
            />
          </div>
        </div>
      </div>

      {/* T-Shirt Size Selector */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">VM Size</h2>
        <input type="hidden" {...register('tshirt_size')} />
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
          {sizes &&
            Object.entries(sizes).map(([key, size]) => (
              <TShirtSizeCard
                key={key}
                sizeKey={key}
                size={size}
                selected={selectedSize === key}
                onSelect={(k) => setValue('tshirt_size', k, { shouldValidate: true })}
              />
            ))}
        </div>
        {errors.tshirt_size && (
          <p className="mt-2 text-sm text-red-600">{errors.tshirt_size.message}</p>
        )}
      </div>

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
          disabled={createRequest.isPending}
          className="px-6 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {createRequest.isPending ? 'Submitting...' : 'Submit Request'}
        </button>
      </div>

      {createRequest.isError && (
        <div className="rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-700">
            Failed to submit request. Please try again.
          </p>
        </div>
      )}
    </form>
  )
}
