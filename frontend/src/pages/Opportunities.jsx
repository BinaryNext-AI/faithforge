import { useState, useEffect, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search, SlidersHorizontal, ChevronRight, Loader2, AlertCircle, Building2, Calendar, DollarSign, ExternalLink } from 'lucide-react'
import { getOpportunities } from '../api'
import StatusBadge from '../components/StatusBadge'

const ALL_STATUSES = [
  'New', 'Under Review', 'Relevant', 'Possibly Relevant', 'Not Relevant',
  'EMMA Documents Needed', 'Documents Uploaded', 'Packet Building',
  'Packet Ready', 'Reviewed by User', 'Approved to Pursue', 'Declined',
]

function ScorePill({ score }) {
  if (score == null) return null
  const s = Math.round(score)
  const color = s >= 70 ? 'bg-green-100 text-green-700' : s >= 40 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
  return <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${color}`}>{s}</span>
}

export default function Opportunities() {
  const [searchParams] = useSearchParams()
  const [opps, setOpps]           = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [search, setSearch]       = useState('')
  const [status, setStatus]       = useState(searchParams.get('status') || '')
  const [classification, setClassification] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (status) params.status = status
      if (search) params.search = search
      if (classification) params.classification = classification
      const data = await getOpportunities(params)
      setOpps(data); setError(null)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [status, search, classification])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Opportunities</h1>
          <p className="text-sm text-gray-400 mt-0.5">{opps.length} result{opps.length !== 1 ? 's' : ''}</p>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-2 items-center bg-white border border-gray-200 rounded-xl px-4 py-3 shadow-sm">
        <SlidersHorizontal className="w-4 h-4 text-gray-400 shrink-0" />
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
          <input
            type="text" placeholder="Search title, agency, solicitation..."
            value={search} onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && load()}
            className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select value={status} onChange={e => setStatus(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
          <option value="">All statuses</option>
          {ALL_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={classification} onChange={e => setClassification(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
          <option value="">All classifications</option>
          <option value="relevant">Relevant</option>
          <option value="possibly_relevant">Possibly Relevant</option>
        </select>
        <button onClick={load} className="btn-primary text-sm py-1.5 px-4">Search</button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />{error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-blue-600" /></div>
      ) : opps.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-2xl p-14 text-center text-gray-400 shadow-sm">
          <Search className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No opportunities found. Try adjusting your filters.</p>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
          {/* Table header */}
          <div className="grid grid-cols-[1fr_180px_130px_100px_44px] gap-4 px-5 py-2.5 bg-gray-50 border-b border-gray-200 text-xs font-semibold text-gray-500 uppercase tracking-wider">
            <span>Opportunity</span>
            <span>Status</span>
            <span>Due Date</span>
            <span>Score</span>
            <span></span>
          </div>
          {/* Rows */}
          <div className="divide-y divide-gray-100">
            {opps.map(opp => (
              <Link key={opp.id} to={`/opportunities/${opp.id}`}
                className="grid grid-cols-[1fr_180px_130px_100px_44px] gap-4 items-center px-5 py-3.5 hover:bg-blue-50/30 transition-colors group">

                {/* Title + meta */}
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-gray-900 truncate">
                      {opp.opportunity_title || opp.email_subject || 'Untitled Opportunity'}
                    </p>
                    {opp.has_emma_link && (
                      <span className="shrink-0 px-1.5 py-0.5 bg-orange-100 text-orange-600 text-xs rounded font-semibold">EMMA</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-400">
                    {opp.agency_name && (
                      <span className="flex items-center gap-1 truncate">
                        <Building2 className="w-3 h-3 shrink-0" />{opp.agency_name}
                      </span>
                    )}
                    {opp.estimated_value && (
                      <span className="flex items-center gap-1 shrink-0">
                        <DollarSign className="w-3 h-3" />{opp.estimated_value}
                      </span>
                    )}
                  </div>
                </div>

                {/* Status */}
                <div><StatusBadge status={opp.status} /></div>

                {/* Due date */}
                <div className="text-xs text-gray-500 flex items-center gap-1">
                  {opp.due_date ? (
                    <><Calendar className="w-3 h-3 shrink-0 text-gray-400" />{new Date(opp.due_date).toLocaleDateString()}</>
                  ) : <span className="text-gray-300">—</span>}
                </div>

                {/* Score */}
                <div><ScorePill score={opp.relevance_score} /></div>

                {/* Arrow */}
                <div className="flex justify-end">
                  <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-blue-500 transition-colors" />
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
