import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Mail, Upload, Trash2, FileText, Package, Send, Settings,
  RefreshCw, CheckCircle, Eye, ClipboardList
} from 'lucide-react'
import { getAuditLog } from '../api'
import { formatDistanceToNow, format, isToday, isYesterday } from 'date-fns'

const ACTION_META = {
  email_scan_started:   { label: 'Email Scan Started',    icon: Mail,        color: 'bg-blue-100 text-blue-600' },
  email_scanned:        { label: 'Email Screened',         icon: CheckCircle, color: 'bg-green-100 text-green-600' },
  opportunity_updated:  { label: 'Opportunity Updated',    icon: RefreshCw,   color: 'bg-yellow-100 text-yellow-600' },
  status_changed:       { label: 'Status Changed',         icon: RefreshCw,   color: 'bg-purple-100 text-purple-600' },
  opportunity_deleted:  { label: 'Opportunity Deleted',    icon: Trash2,      color: 'bg-red-100 text-red-600' },
  document_uploaded:    { label: 'Document Uploaded',      icon: Upload,      color: 'bg-blue-100 text-blue-600' },
  document_deleted:     { label: 'Document Deleted',       icon: Trash2,      color: 'bg-red-100 text-red-600' },
  documents_reviewed:   { label: 'Documents Reviewed (AI)',icon: Eye,         color: 'bg-teal-100 text-teal-600' },
  packet_built:         { label: 'Packet Built (AI)',       icon: Package,     color: 'bg-indigo-100 text-indigo-600' },
  packet_emailed:       { label: 'Packet Emailed',          icon: Send,        color: 'bg-green-100 text-green-600' },
  settings_updated:     { label: 'Settings Updated',        icon: Settings,    color: 'bg-gray-100 text-gray-500' },
}

function groupByDate(logs) {
  const groups = {}
  logs.forEach(log => {
    const d = new Date(log.timestamp)
    const key = format(d, 'yyyy-MM-dd')
    if (!groups[key]) groups[key] = { date: d, logs: [] }
    groups[key].logs.push(log)
  })
  return Object.values(groups).sort((a, b) => b.date - a.date)
}

function dateLabel(d) {
  if (isToday(d)) return 'Today'
  if (isYesterday(d)) return 'Yesterday'
  return format(d, 'EEEE, MMMM d, yyyy')
}

export default function AuditLog() {
  const [logs, setLogs]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  useEffect(() => {
    getAuditLog({ limit: 200 })
      .then(data => { setLogs(data); setError(null) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const parseDetails = (d) => { try { return JSON.parse(d) } catch { return null } }

  const groups = groupByDate(logs)

  return (
    <div className="space-y-5">

      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-slate-100 rounded-xl flex items-center justify-center">
          <ClipboardList className="w-5 h-5 text-slate-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
          <p className="text-sm text-gray-400">All system activity — {logs.length} events</p>
        </div>
      </div>

      {error && <div className="p-4 bg-red-50 text-red-700 rounded-xl text-sm">{error}</div>}

      {loading ? (
        <div className="flex justify-center py-20">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-gray-400">Loading activity...</p>
          </div>
        </div>
      ) : logs.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-2xl p-14 text-center text-gray-400 shadow-sm">
          <ClipboardList className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No audit events yet.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {groups.map(group => (
            <div key={group.date.toISOString()}>
              {/* Date divider */}
              <div className="flex items-center gap-3 mb-3">
                <span className="text-xs font-bold text-gray-400 uppercase tracking-widest whitespace-nowrap">
                  {dateLabel(group.date)}
                </span>
                <div className="flex-1 h-px bg-gray-200" />
                <span className="text-xs text-gray-300 whitespace-nowrap">{group.logs.length} event{group.logs.length !== 1 ? 's' : ''}</span>
              </div>

              {/* Events */}
              <div className="relative pl-6">
                {/* Vertical line */}
                <div className="absolute left-[11px] top-0 bottom-0 w-px bg-gray-200" />

                <div className="space-y-1">
                  {group.logs.map(log => {
                    const meta = ACTION_META[log.action] || { label: log.action, icon: FileText, color: 'bg-gray-100 text-gray-500' }
                    const Icon = meta.icon
                    const details = parseDetails(log.details)

                    return (
                      <div key={log.id} className="relative flex items-start gap-3 bg-white border border-gray-100 rounded-xl px-4 py-3 hover:border-gray-200 hover:shadow-sm transition-all">
                        {/* Dot on timeline */}
                        <div className="absolute -left-[13px] top-4 w-3.5 h-3.5 rounded-full bg-white border-2 border-gray-300 z-10" />

                        {/* Icon */}
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${meta.color}`}>
                          <Icon className="w-3.5 h-3.5" />
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-gray-800">{meta.label}</p>
                          {details && (
                            <p className="text-xs text-gray-400 mt-0.5 truncate">
                              {Object.entries(details).map(([k, v]) => `${k}: ${v}`).join(' · ')}
                            </p>
                          )}
                        </div>

                        {/* Right side */}
                        <div className="flex items-center gap-3 shrink-0">
                          {log.opportunity_id && (
                            <Link to={`/opportunities/${log.opportunity_id}`}
                              className="flex items-center gap-1 text-xs text-blue-500 hover:text-blue-700 font-medium bg-blue-50 px-2 py-0.5 rounded-md">
                              Opp #{log.opportunity_id}
                            </Link>
                          )}
                          <span className="text-xs text-gray-400 whitespace-nowrap">
                            {formatDistanceToNow(new Date(log.timestamp), { addSuffix: true })}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
