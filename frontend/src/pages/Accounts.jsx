import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  Search, SlidersHorizontal, ChevronRight, Loader2, AlertCircle,
  Building2, Plus, X, Clock, Bell, Upload, FileSpreadsheet, Link as LinkIcon, Users, CheckCircle2,
} from 'lucide-react'
import {
  getAccounts, createAccount,
  outreachPreviewFile, outreachPreviewGoogleSheet, outreachCommitImport,
} from '../api'

export const STAGES = [
  'Not Contacted', 'Contacted', 'Replied', 'Meeting Scheduled',
  'Proposal Sent', 'Negotiation', 'Won', 'Lost',
]

export const SEGMENTS = [
  'Government / Public Sector', 'Nonprofit', 'Healthcare',
  'Education', 'Enterprise / Mid-Market', 'Other',
]

const STAGE_STYLES = {
  'Not Contacted': 'bg-gray-100 text-gray-600',
  'Contacted': 'bg-blue-100 text-blue-800',
  'Replied': 'bg-teal-100 text-teal-800',
  'Meeting Scheduled': 'bg-indigo-100 text-indigo-800',
  'Proposal Sent': 'bg-purple-100 text-purple-800',
  'Negotiation': 'bg-amber-100 text-amber-800',
  'Won': 'bg-emerald-100 text-emerald-800',
  'Lost': 'bg-red-100 text-red-700',
}

export function StageBadge({ stage }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STAGE_STYLES[stage] || 'bg-gray-100 text-gray-600'}`}>
      {stage || 'Unknown'}
    </span>
  )
}

export function PriorityPill({ score }) {
  if (score == null) return <span className="text-gray-300 text-xs">—</span>
  const s = Math.round(score)
  const color = s >= 70 ? 'bg-green-100 text-green-700' : s >= 40 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
  return <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${color}`}>{s}</span>
}

function AddAccountModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    company_name: '', segment: '', location: '',
    contact_name: '', contact_title: '', contact_email: '', contact_phone: '',
    pain_points: '', notes: '', source: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    if (!form.company_name.trim()) { setError('Company name is required'); return }
    setSaving(true)
    try {
      const acc = await createAccount(form)
      onCreated(acc)
    } catch (err) { setError(err.message); setSaving(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-bold text-gray-900">New Target Account</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={submit} className="px-6 py-5 space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />{error}
            </div>
          )}
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Company Name *</label>
            <input value={form.company_name} onChange={set('company_name')} className="input" autoFocus />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Segment</label>
              <select value={form.segment} onChange={set('segment')} className="input">
                <option value="">Select…</option>
                {SEGMENTS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Location</label>
              <input value={form.location} onChange={set('location')} className="input" placeholder="Maryland / DC…" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Contact Name</label>
              <input value={form.contact_name} onChange={set('contact_name')} className="input" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Contact Title</label>
              <input value={form.contact_title} onChange={set('contact_title')} className="input" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Contact Email</label>
              <input value={form.contact_email} onChange={set('contact_email')} className="input" type="email" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Contact Phone</label>
              <input value={form.contact_phone} onChange={set('contact_phone')} className="input" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Known Pain Points</label>
            <textarea value={form.pain_points} onChange={set('pain_points')} className="input min-h-16" rows={2} />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Notes</label>
            <textarea value={form.notes} onChange={set('notes')} className="input min-h-16" rows={2} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary text-sm py-2 px-5 flex items-center gap-2">
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              Add Account
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function ImportAccountsModal({ onClose, onImported }) {
  const [uploadMode, setUploadMode] = useState('file') // 'file' | 'sheet'
  const [sheetUrl, setSheetUrl] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [preview, setPreview] = useState(null)
  const [sourceFilename, setSourceFilename] = useState('leads.xlsx')
  const [dedupe, setDedupe] = useState('skip')
  const [committing, setCommitting] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const fileInputRef = useRef(null)

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setSourceFilename(file.name)
    setPreviewLoading(true)
    setError(null)
    setPreview(null)
    try {
      const r = await outreachPreviewFile(file)
      setPreview(r)
    } catch (err) { setError(err.message) }
    finally { setPreviewLoading(false) }
  }

  const handleSheetPreview = async () => {
    if (!sheetUrl.trim()) return
    setPreviewLoading(true)
    setError(null)
    setSourceFilename('google_sheet.csv')
    try {
      const r = await outreachPreviewGoogleSheet(sheetUrl.trim())
      setPreview(r)
    } catch (err) { setError(err.message) }
    finally { setPreviewLoading(false) }
  }

  const handleCommit = async () => {
    if (!preview) return
    setCommitting(true)
    setError(null)
    try {
      const r = await outreachCommitImport(preview.rows, sourceFilename, dedupe)
      setResult(r)
    } catch (err) { setError(err.message) }
    finally { setCommitting(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-bold text-gray-900">Upload a Leads Spreadsheet</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>

        <div className="px-6 py-5 space-y-4">
          {result ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-sm">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                Added {result.created} new account{result.created !== 1 ? 's' : ''}
                {result.updated > 0 && `, updated ${result.updated}`}
                {result.skipped > 0 && `, skipped ${result.skipped} duplicate${result.skipped !== 1 ? 's' : ''}`}.
              </div>
              <div className="flex justify-end">
                <button onClick={() => onImported()} className="btn-primary text-sm py-2 px-5">Done</button>
              </div>
            </div>
          ) : (
            <>
              <p className="text-sm text-gray-500">
                Upload an .xlsx, .xls, or .csv file of leads — or paste a public Google Sheet link.
                Each row becomes a new Account in your pipeline. Want AI to draft cold emails for these
                leads too? Use the <strong>Outreach</strong> page's Bulk Upload tab instead — it imports the
                same way and then generates emails.
              </p>

              <div className="flex gap-2">
                <button
                  onClick={() => setUploadMode('file')}
                  className={`px-4 py-2 rounded-lg text-sm font-semibold ${uploadMode === 'file' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}
                >
                  <FileSpreadsheet className="w-4 h-4 inline mr-1.5" />Upload File
                </button>
                <button
                  onClick={() => setUploadMode('sheet')}
                  className={`px-4 py-2 rounded-lg text-sm font-semibold ${uploadMode === 'sheet' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}
                >
                  <LinkIcon className="w-4 h-4 inline mr-1.5" />Google Sheet Link
                </button>
              </div>

              {uploadMode === 'file' ? (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50/30 transition-colors"
                >
                  <Upload className="w-7 h-7 mx-auto mb-2 text-gray-400" />
                  <p className="text-sm text-gray-600">Click to upload an .xlsx, .xls, or .csv leads file</p>
                  <input ref={fileInputRef} type="file" accept=".xlsx,.xls,.csv" onChange={handleFileChange} className="hidden" />
                </div>
              ) : (
                <div className="flex gap-2">
                  <input
                    value={sheetUrl}
                    onChange={e => setSheetUrl(e.target.value)}
                    className="input flex-1"
                    placeholder="https://docs.google.com/spreadsheets/d/..."
                  />
                  <button onClick={handleSheetPreview} disabled={previewLoading || !sheetUrl.trim()} className="btn-primary text-sm px-4">
                    Preview
                  </button>
                </div>
              )}

              {error && (
                <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                  <AlertCircle className="w-4 h-4 shrink-0" />{error}
                </div>
              )}

              {previewLoading && (
                <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
              )}

              {preview && !previewLoading && (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-gray-50 rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-gray-900">{preview.row_count}</p>
                      <p className="text-xs text-gray-500">Leads found</p>
                    </div>
                    <div className="bg-amber-50 rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-amber-700">{preview.duplicate_count}</p>
                      <p className="text-xs text-amber-600">Possible duplicates</p>
                    </div>
                    <div className="bg-red-50 rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-red-600">{preview.email_missing_count}</p>
                      <p className="text-xs text-red-500">Missing email</p>
                    </div>
                  </div>

                  {preview.unmapped_columns && preview.unmapped_columns.length > 0 && (
                    <p className="text-xs text-gray-400">
                      Columns not recognized as a standard field — kept as custom fields on each lead
                      (view/edit them from the account page): <span className="text-gray-600">{preview.unmapped_columns.join(', ')}</span>
                    </p>
                  )}

                  <div className="border border-gray-200 rounded-xl overflow-x-auto max-h-56 overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          <th className="text-left px-3 py-2 font-semibold text-gray-500">Company</th>
                          <th className="text-left px-3 py-2 font-semibold text-gray-500">Contact</th>
                          <th className="text-left px-3 py-2 font-semibold text-gray-500">Email</th>
                          <th className="text-left px-3 py-2 font-semibold text-gray-500">Flags</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {preview.rows.map((r, i) => (
                          <tr key={i}>
                            <td className="px-3 py-2 font-medium text-gray-800">{r.company_name}</td>
                            <td className="px-3 py-2 text-gray-600">{r.contact_name}</td>
                            <td className="px-3 py-2 text-gray-500">
                              {r.has_email ? r.contact_email : <span className="text-red-500">needs research</span>}
                            </td>
                            <td className="px-3 py-2">
                              {r.duplicate_of_account_id && (
                                <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded text-[10px] font-semibold">DUP</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-gray-500">If a lead already exists:</span>
                      <select value={dedupe} onChange={e => setDedupe(e.target.value)} className="input py-1.5 text-sm w-auto">
                        <option value="skip">Skip it</option>
                        <option value="update">Fill in missing fields</option>
                      </select>
                    </div>
                    <button onClick={handleCommit} disabled={committing} className="btn-primary text-sm px-5 flex items-center gap-2">
                      {committing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Users className="w-4 h-4" />}
                      Import {preview.row_count} Leads
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Accounts() {
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [stage, setStage] = useState('')
  const [segment, setSegment] = useState('')
  const [sort, setSort] = useState('priority')
  const [showAdd, setShowAdd] = useState(false)
  const [showImport, setShowImport] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { sort }
      if (stage) params.stage = stage
      if (segment) params.segment = segment
      if (search) params.search = search
      const data = await getAccounts(params)
      setAccounts(data); setError(null)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [stage, segment, search, sort])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Accounts</h1>
          <p className="text-sm text-gray-400 mt-0.5">{accounts.length} target account{accounts.length !== 1 ? 's' : ''}</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowImport(true)} className="btn-secondary text-sm py-2 px-4 flex items-center gap-2">
            <Upload className="w-4 h-4" />Upload Sheet
          </button>
          <button onClick={() => setShowAdd(true)} className="btn-primary text-sm py-2 px-4 flex items-center gap-2">
            <Plus className="w-4 h-4" />Add Account
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-2 items-center bg-white border border-gray-200 rounded-xl px-4 py-3 shadow-sm">
        <SlidersHorizontal className="w-4 h-4 text-gray-400 shrink-0" />
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
          <input
            type="text" placeholder="Search company, contact, email..."
            value={search} onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && load()}
            className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select value={stage} onChange={e => setStage(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
          <option value="">All stages</option>
          {STAGES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={segment} onChange={e => setSegment(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
          <option value="">All segments</option>
          {SEGMENTS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={sort} onChange={e => setSort(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
          <option value="priority">Sort: Priority</option>
          <option value="recent">Sort: Recently added</option>
          <option value="next_action">Sort: Next action</option>
        </select>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />{error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-blue-600" /></div>
      ) : accounts.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-2xl p-14 text-center text-gray-400 shadow-sm">
          <Building2 className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No accounts yet. Click "Add Account" to start building your pipeline.</p>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
          <div className="grid grid-cols-[1fr_180px_150px_90px_44px] gap-4 px-5 py-2.5 bg-gray-50 border-b border-gray-200 text-xs font-semibold text-gray-500 uppercase tracking-wider">
            <span>Company / Contact</span>
            <span>Stage</span>
            <span>Next Action</span>
            <span>Priority</span>
            <span></span>
          </div>
          <div className="divide-y divide-gray-100">
            {accounts.map(acc => (
              <Link key={acc.id} to={`/accounts/${acc.id}`}
                className="grid grid-cols-[1fr_180px_150px_90px_44px] gap-4 items-center px-5 py-3.5 hover:bg-blue-50/30 transition-colors group">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-gray-900 truncate">{acc.company_name}</p>
                    {acc.awaiting_reply && (
                      <span className="shrink-0 flex items-center gap-0.5 px-1.5 py-0.5 bg-amber-100 text-amber-700 text-xs rounded font-semibold">
                        <Bell className="w-3 h-3" />Awaiting reply
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-400">
                    {acc.contact_name && <span className="truncate">{acc.contact_name}{acc.contact_title ? ` · ${acc.contact_title}` : ''}</span>}
                    {acc.segment && <span className="truncate">{acc.segment}</span>}
                  </div>
                </div>
                <div><StageBadge stage={acc.stage} /></div>
                <div className="text-xs text-gray-500 min-w-0">
                  {acc.next_action ? (
                    <div className="flex items-center gap-1 truncate">
                      <Clock className="w-3 h-3 shrink-0 text-gray-400" />
                      <span className="truncate">{acc.next_action}</span>
                    </div>
                  ) : <span className="text-gray-300">—</span>}
                  {acc.next_action_date && (
                    <span className="text-gray-400">{new Date(acc.next_action_date).toLocaleDateString()}</span>
                  )}
                </div>
                <div><PriorityPill score={acc.priority_score} /></div>
                <div className="flex justify-end">
                  <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-blue-500 transition-colors" />
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {showAdd && (
        <AddAccountModal
          onClose={() => setShowAdd(false)}
          onCreated={() => { setShowAdd(false); load() }}
        />
      )}

      {showImport && (
        <ImportAccountsModal
          onClose={() => setShowImport(false)}
          onImported={() => { setShowImport(false); load() }}
        />
      )}
    </div>
  )
}
