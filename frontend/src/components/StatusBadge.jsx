const STATUS_STYLES = {
  'New': 'bg-blue-100 text-blue-800',
  'Under Review': 'bg-yellow-100 text-yellow-800',
  'Relevant': 'bg-green-100 text-green-800',
  'Possibly Relevant': 'bg-teal-100 text-teal-800',
  'Not Relevant': 'bg-gray-100 text-gray-600',
  'EMMA Documents Needed': 'bg-orange-100 text-orange-800',
  'Documents Uploaded': 'bg-purple-100 text-purple-800',
  'Packet Building': 'bg-indigo-100 text-indigo-800',
  'Packet Ready': 'bg-cyan-100 text-cyan-800',
  'Reviewed by User': 'bg-sky-100 text-sky-800',
  'Approved to Pursue': 'bg-emerald-100 text-emerald-800',
  'Declined': 'bg-red-100 text-red-700',
}

const CLASSIFICATION_STYLES = {
  'relevant': 'bg-green-100 text-green-800',
  'possibly_relevant': 'bg-yellow-100 text-yellow-800',
  'not_relevant': 'bg-gray-100 text-gray-600',
}

export default function StatusBadge({ status, type = 'status', className = '' }) {
  const styles = type === 'classification' ? CLASSIFICATION_STYLES : STATUS_STYLES
  const label = type === 'classification'
    ? (status || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    : status
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-100 text-gray-600'} ${className}`}>
      {label || 'Unknown'}
    </span>
  )
}
