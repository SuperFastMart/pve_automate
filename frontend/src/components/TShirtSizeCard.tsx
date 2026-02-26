import type { TShirtSize } from '../types'

interface Props {
  sizeKey: string
  size: TShirtSize
  selected: boolean
  onSelect: (key: string) => void
}

export default function TShirtSizeCard({ sizeKey, size, selected, onSelect }: Props) {
  return (
    <button
      type="button"
      onClick={() => onSelect(sizeKey)}
      className={`relative flex flex-col items-center p-4 rounded-lg border-2 transition-all cursor-pointer ${
        selected
          ? 'border-indigo-500 bg-indigo-50 ring-2 ring-indigo-200'
          : 'border-gray-200 bg-white hover:border-gray-300'
      }`}
    >
      <span className={`text-2xl font-bold ${selected ? 'text-indigo-600' : 'text-gray-700'}`}>
        {sizeKey}
      </span>
      <span className="text-xs text-gray-500 mt-1">{size.display_name}</span>
      <div className="mt-3 space-y-1 text-sm text-gray-600 text-center">
        <div>{size.cpu_cores} vCPU</div>
        <div>{size.ram_mb >= 1024 ? `${size.ram_mb / 1024} GB` : `${size.ram_mb} MB`} RAM</div>
        <div>{size.disk_gb} GB Disk</div>
      </div>
      <p className="mt-2 text-xs text-gray-400">{size.description}</p>
    </button>
  )
}
