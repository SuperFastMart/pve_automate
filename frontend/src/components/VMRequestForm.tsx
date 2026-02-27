import { useState, useRef, useEffect } from 'react'
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
  tshirt_size: z.string().regex(/^(XS|S|M|L|XL|Custom)$/, 'Please select a size'),
  cpu_cores: z.coerce.number().int().min(1).max(128).optional(),
  ram_mb: z.coerce.number().int().min(512).max(524288).optional(),
  disk_gb: z.coerce.number().int().min(8).max(4096).optional(),
}).refine(
  (data) => {
    if (data.tshirt_size === 'Custom') {
      return data.cpu_cores != null && data.ram_mb != null && data.disk_gb != null
    }
    return true
  },
  { message: 'Custom size requires CPU, RAM, and Disk values', path: ['cpu_cores'] }
)

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
  const [subnetSearch, setSubnetSearch] = useState('')
  const [subnetDropdownOpen, setSubnetDropdownOpen] = useState(false)
  const subnetRef = useRef<HTMLDivElement>(null)

  // Filter subnets by selected location
  const locationFiltered = subnets?.filter((s) => {
    if (!selectedLocation) return true
    return s.locationId !== null && String(s.locationId) === selectedLocation
  })

  // Further filter by search text
  const filteredSubnets = locationFiltered?.filter((s) => {
    if (!subnetSearch) return true
    const label = s.description
      ? `${s.description} ${s.subnet}/${s.mask}`
      : `${s.subnet}/${s.mask}`
    return label.toLowerCase().includes(subnetSearch.toLowerCase())
  })

  // Get display label for a subnet
  const subnetLabel = (s: { description: string; subnet: string; mask: string }) =>
    s.description ? `${s.description} (${s.subnet}/${s.mask})` : `${s.subnet}/${s.mask}`

  // Selected subnet display text
  const selectedSubnetObj = subnets?.find((s) => String(s.id) === selectedSubnet)

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (subnetRef.current && !subnetRef.current.contains(e.target as Node)) {
        setSubnetDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

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
    const { cpu_cores, ram_mb, disk_gb, ...rest } = data
    const payload = {
      ...rest,
      ...(selectedSubnet ? { subnet_id: Number(selectedSubnet) } : {}),
      ...(data.tshirt_size === 'Custom' ? { cpu_cores, ram_mb, disk_gb } : {}),
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
                      setSubnetSearch('')
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
              <div ref={subnetRef} className="relative">
                <label className="block text-sm font-medium text-gray-700 mb-1">Network / Subnet</label>
                <div
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500 cursor-text flex items-center gap-2"
                  onClick={() => setSubnetDropdownOpen(true)}
                >
                  {selectedSubnet && !subnetDropdownOpen ? (
                    <div className="flex items-center justify-between w-full">
                      <span className="truncate">{selectedSubnetObj ? subnetLabel(selectedSubnetObj) : ''}</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedSubnet('')
                          setSubnetSearch('')
                        }}
                        className="text-gray-400 hover:text-gray-600 ml-2 flex-shrink-0"
                      >
                        &times;
                      </button>
                    </div>
                  ) : (
                    <input
                      type="text"
                      value={subnetSearch}
                      onChange={(e) => {
                        setSubnetSearch(e.target.value)
                        setSubnetDropdownOpen(true)
                      }}
                      onFocus={() => setSubnetDropdownOpen(true)}
                      placeholder={selectedSubnet ? '' : 'Search subnets or select below...'}
                      className="w-full outline-none bg-transparent"
                    />
                  )}
                </div>
                {subnetDropdownOpen && (
                  <ul className="absolute z-10 mt-1 w-full bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
                    <li
                      className={`px-3 py-2 text-sm cursor-pointer hover:bg-indigo-50 ${
                        !selectedSubnet ? 'bg-indigo-50 font-medium' : ''
                      }`}
                      onClick={() => {
                        setSelectedSubnet('')
                        setSubnetSearch('')
                        setSubnetDropdownOpen(false)
                      }}
                    >
                      No subnet (manual IP assignment)
                    </li>
                    {filteredSubnets?.map((s) => (
                      <li
                        key={s.id}
                        className={`px-3 py-2 text-sm cursor-pointer hover:bg-indigo-50 ${
                          String(s.id) === selectedSubnet ? 'bg-indigo-50 font-medium' : ''
                        }`}
                        onClick={() => {
                          setSelectedSubnet(String(s.id))
                          setSubnetSearch('')
                          setSubnetDropdownOpen(false)
                        }}
                      >
                        {subnetLabel(s)}
                      </li>
                    ))}
                    {filteredSubnets?.length === 0 && (
                      <li className="px-3 py-2 text-sm text-gray-400">No matching subnets</li>
                    )}
                  </ul>
                )}
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
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
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
          {/* Custom size card */}
          <button
            type="button"
            onClick={() => setValue('tshirt_size', 'Custom', { shouldValidate: true })}
            className={`relative flex flex-col items-center p-4 rounded-lg border-2 transition-all cursor-pointer ${
              selectedSize === 'Custom'
                ? 'border-indigo-500 bg-indigo-50 ring-2 ring-indigo-200'
                : 'border-gray-200 bg-white hover:border-gray-300'
            }`}
          >
            <svg className={`w-8 h-8 ${selectedSize === 'Custom' ? 'text-indigo-600' : 'text-gray-700'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="text-xs text-gray-500 mt-1">Specify your own</span>
            <div className="mt-3 text-sm text-gray-600 text-center">
              <div>Custom specs</div>
            </div>
            <p className="mt-2 text-xs text-gray-400">Define CPU, RAM & disk</p>
          </button>
        </div>
        {errors.tshirt_size && (
          <p className="mt-2 text-sm text-red-600">{errors.tshirt_size.message}</p>
        )}

        {/* Custom size inputs */}
        {selectedSize === 'Custom' && (
          <div className="mt-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Custom Specifications</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">CPU Cores</label>
                <input
                  type="number"
                  {...register('cpu_cores')}
                  min={1}
                  max={128}
                  placeholder="e.g. 4"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">RAM (MB)</label>
                <input
                  type="number"
                  {...register('ram_mb')}
                  min={512}
                  max={524288}
                  step={512}
                  placeholder="e.g. 8192"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">Disk (GB)</label>
                <input
                  type="number"
                  {...register('disk_gb')}
                  min={8}
                  max={4096}
                  placeholder="e.g. 256"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500"
                />
              </div>
            </div>
            {errors.cpu_cores && (
              <p className="mt-2 text-sm text-red-600">{errors.cpu_cores.message}</p>
            )}
          </div>
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
