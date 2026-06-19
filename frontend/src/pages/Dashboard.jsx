import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  Mail, RefreshCw, FileText, ChevronRight, Loader2,
  TrendingUp, Clock, Package, CheckCircle, AlertCircle, Inbox, CalendarClock
} from 'lucide-react'
import { getDashboardStats, scanEmail, getScanStatus } from '../api'
import StatusBadge from '../components/StatusBadge'

const PIPELINE = [
  { label: 'New',            statuses: ['New'],                                      color: '#3b82f6', bg: '#eff6ff' },
  { label: 'Relevant',       statuses: ['Relevant'],                                 color: '#10b981', bg: '#ecfdf5' },
  { label: 'Possibly Rel.',  statuses: ['Possibly Relevant'],                        color: '#14b8a6', bg: '#f0fdfa' },
  { label: 'EMMA Needed',    statuses: ['EMMA Documents Needed'],                    color: '#f97316', bg: '#fff7ed' },
  { label: 'Docs Uploaded',  statuses: ['Documents Uploaded'],                       color: '#eab308', bg: '#fefce8' },
  { label: 'Under Review',   statuses: ['Under Review'],                             color: '#8b5cf6', bg: '#f5f3ff' },
  { label: 'Packet Ready',   statuses: ['Packet Building','Packet Ready','Reviewed by User'], color: '#6366f1', bg: '#eef2ff' },
  { label: 'Approved',       statuses: ['Approved to Pursue'],                       color: '#059669', bg: '#d1fae5' },
  { label: 'Declined',       statuses: ['Declined','Not Relevant'],                  color: '#9ca3af', bg: '#f9fafb' },
]

export default function Dashboard() {
  const [stats, setStats]           = useState(null)
  const [scanRunning, setScanRunning] = useState(false)
  const [scanResult, setScanResult]  = useState(null)
  const [loading, setLoading]        = useState(true)
  const [error, setError]            = useState(null)
  const [daysBack, setDaysBack]      = useState(30)

  const load = useCallback(async () => {
    try { const d = await getDashboardStats(); setStats(d); setError(null) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [])

  const pollScanStatus = useCallback(async () => {
    try {
      const s = await getScanStatus()
      if (!s.running) { setScanRunning(false); if (s.last_result) { setScanResult(s.last_result); load() } }
    } catch {}
  }, [load])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (!scanRunning) return
    const t = setInterval(pollScanStatus, 3000)
    return () => clearInterval(t)
  }, [scanRunning, pollScanStatus])

  const handleScan = async () => {
    setScanResult(null); setScanRunning(true)
    try { await scanEmail(daysBack) }
    catch (e) { setScanRunning(false); setError(e.message) }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 animate-spin text-blue-600" /></div>

  const byStatus = stats?.by_status || {}
  const active = (byStatus['Relevant'] || 0) + (byStatus['Possibly Relevant'] || 0)
  const inProgress = (byStatus['Under Review'] || 0) + (byStatus['Documents Uploaded'] || 0) + (byStatus['EMMA Documents Needed'] || 0)
  const packetReady = (byStatus['Packet Building'] || 0) + (byStatus['Packet Ready'] || 0) + (byStatus['Reviewed by User'] || 0)
  const approved = byStatus['Approved to Pursue'] || 0

  return (
    <div className="space-y-6">

      {/* Top bar */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Command Center</h1>
          <p className="text-sm text-gray-500 mt-0.5">{stats?.total || 0} opportunities in pipeline</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={daysBack} onChange={e => setDaysBack(Number(e.target.value))}
            className="input w-auto text-sm" disabled={scanRunning}>
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={60}>Last 60 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button onClick={handleScan} disabled={scanRunning} className="btn-primary">
            {scanRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> Scanning...</> : <><Mail className="w-4 h-4" /> Scan Email</>}
          </button>
          <button onClick={load} className="btn-secondary" title="Refresh"><RefreshCw className="w-4 h-4" /></button>
        </div>
      </div>

      {error && <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm flex items-center gap-2"><AlertCircle className="w-4 h-4 shrink-0" />{error}</div>}
      {scanResult && (
        <div className="p-4 bg-green-50 border border-green-200 text-green-800 rounded-xl text-sm">
          <p className="font-semibold mb-0.5">Scan complete</p>
          <p>Scanned {scanResult.scanned} emails — {scanResult.new_found} new: {scanResult.relevant} relevant, {scanResult.possibly_relevant} possibly relevant, {scanResult.not_relevant} not relevant.</p>
          {scanResult.errors?.length > 0 && <p className="text-yellow-700 mt-1">{scanResult.errors.length} error(s): {scanResult.errors[0]}</p>}
        </div>
      )}

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Active Opportunities', value: active,      icon: TrendingUp,    color: 'text-green-600',  bg: 'bg-green-50'  },
          { label: 'In Progress',          value: inProgress,  icon: Clock,         color: 'text-purple-600', bg: 'bg-purple-50' },
          { label: 'Packets Ready',        value: packetReady, icon: Package,       color: 'text-indigo-600', bg: 'bg-indigo-50' },
          { label: 'Approved to Pursue',   value: approved,    icon: CheckCircle,   color: 'text-emerald-600',bg: 'bg-emerald-50'},
        ].map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} className="bg-white border border-gray-200 rounded-2xl p-5 flex items-center gap-4 shadow-sm">
            <div className={`w-12 h-12 rounded-xl ${bg} flex items-center justify-center shrink-0`}>
              <Icon className={`w-6 h-6 ${color}`} />
            </div>
            <div>
              <p className="text-3xl font-bold text-gray-900">{value}</p>
              <p className="text-xs text-gray-500 mt-0.5">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Pipeline bar */}
      <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Pipeline Breakdown</h2>
        <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-3">
          {PIPELINE.map(({ label, statuses, color, bg }) => {
            const count = statuses.reduce((s, st) => s + (byStatus[st] || 0), 0)
            return (
              <Link key={label} to={`/opportunities?status=${encodeURIComponent(statuses[0])}`}
                className="rounded-xl p-3 text-center hover:scale-105 transition-transform cursor-pointer"
                style={{ background: bg, border: `1px solid ${color}22` }}>
                <p className="text-2xl font-bold" style={{ color }}>{count}</p>
                <p className="text-xs mt-1 font-medium" style={{ color }}>{label}</p>
              </Link>
            )
          })}
        </div>
      </div>

      {/* Upcoming deadlines */}
      {stats?.upcoming?.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
          <div className="flex items-center gap-2 px-6 py-4 border-b border-gray-100 bg-amber-50">
            <CalendarClock className="w-4 h-4 text-amber-600" />
            <h2 className="font-semibold text-amber-800 text-sm">Upcoming Deadlines</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {stats.upcoming.map(opp => {
              const due = new Date(opp.due_date)
              const days = Math.ceil((due - new Date()) / 86400000)
              const urgent = days <= 7
              return (
                <Link key={opp.id} to={`/opportunities/${opp.id}`}
                  className="flex items-center gap-4 px-6 py-3.5 hover:bg-amber-50/40 transition-colors group">
                  <div className={`flex flex-col items-center justify-center w-14 shrink-0 rounded-lg py-1 ${urgent ? 'bg-red-50 text-red-600' : 'bg-blue-50 text-blue-600'}`}>
                    <span className="text-lg font-bold leading-none">{days}</span>
                    <span className="text-[10px] uppercase tracking-wide">day{days === 1 ? '' : 's'}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">
                      {opp.opportunity_title || opp.email_subject || 'Untitled'}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5 truncate">
                      {opp.agency_name || '—'} · Due {due.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </p>
                  </div>
                  <StatusBadge status={opp.status} />
                  <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-amber-400 transition-colors" />
                </Link>
              )
            })}
          </div>
        </div>
      )}

      {/* Recent opportunities */}
      <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50">
          <div className="flex items-center gap-2">
            <Inbox className="w-4 h-4 text-gray-500" />
            <h2 className="font-semibold text-gray-800 text-sm">Recent Opportunities</h2>
          </div>
          <Link to="/opportunities" className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 font-medium">
            View all <ChevronRight className="w-3 h-3" />
          </Link>
        </div>
        <div className="divide-y divide-gray-50">
          {(!stats?.recent || stats.recent.length === 0) ? (
            <div className="px-6 py-14 text-center text-gray-400">
              <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p className="text-sm">No opportunities yet. Scan your email to get started.</p>
            </div>
          ) : stats.recent.map(opp => (
            <Link key={opp.id} to={`/opportunities/${opp.id}`}
              className="flex items-center gap-4 px-6 py-3.5 hover:bg-blue-50/40 transition-colors group">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">
                  {opp.opportunity_title || opp.email_subject || 'Untitled'}
                </p>
                <p className="text-xs text-gray-400 mt-0.5 truncate">
                  {opp.agency_name || opp.email_from || '—'}
                  {opp.due_date && ` · Due ${new Date(opp.due_date).toLocaleDateString()}`}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <StatusBadge status={opp.status} />
                {opp.relevance_score != null && (
                  <span className="text-xs font-semibold text-gray-400">{Math.round(opp.relevance_score)}%</span>
                )}
                <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-blue-400 transition-colors" />
              </div>
            </Link>
          ))}
        </div>
      </div>

    </div>
  )
}
