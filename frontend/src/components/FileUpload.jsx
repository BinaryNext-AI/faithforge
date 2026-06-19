import { useRef, useState } from 'react'
import { Upload, X, FileText, File, FileSpreadsheet } from 'lucide-react'
import { uploadDocument } from '../api'

const ICONS = {
  pdf: FileText,
  docx: FileText,
  doc: FileText,
  xlsx: FileSpreadsheet,
  xls: FileSpreadsheet,
  zip: File,
}

function FileIcon({ ext }) {
  const Icon = ICONS[ext?.toLowerCase()] || File
  return <Icon className="w-5 h-5 text-blue-500" />
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

export default function FileUpload({ opportunityId, onUploaded }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)

  const handleFiles = async (files) => {
    const allowed = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.zip']
    const valid = Array.from(files).filter(f => {
      const ext = '.' + f.name.split('.').pop().toLowerCase()
      return allowed.includes(ext)
    })
    if (!valid.length) {
      setError('No valid files. Allowed: PDF, Word, Excel, ZIP')
      return
    }
    setError(null)
    setUploading(true)
    try {
      for (const file of valid) {
        await uploadDocument(opportunityId, file)
      }
      onUploaded?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setUploading(false)
    }
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div className="space-y-3">
      <div
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
        }`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        <p className="text-sm font-medium text-gray-700">
          {uploading ? 'Uploading...' : 'Drop files here or click to browse'}
        </p>
        <p className="text-xs text-gray-500 mt-1">PDF, Word (.docx), Excel (.xlsx), ZIP — max 50 MB</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          accept=".pdf,.docx,.doc,.xlsx,.xls,.zip"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
          <X className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}
    </div>
  )
}
