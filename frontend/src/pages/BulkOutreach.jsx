import { useState, useEffect, useRef } from 'react'
import {
  Upload, FileSpreadsheet, Link as LinkIcon, Loader2, AlertCircle, CheckCircle2,
  Sparkles, Mail, Send, Pencil, Check, X, ChevronRight, ChevronLeft, RefreshCw,
  Users, AlertTriangle, Clock, Search, Ban, Reply,
} from 'lucide-react'
import {
  outreachPreviewFile, outreachPreviewGoogleSheet, outreachCommitImport,
  outreachGenerate, outreachRefreshBatch,
  outreachGetEmails, outreachUpdateEmail, outreachApproveEmail, outreachUnapproveEmail,
  outreachBulkApprove, outreachSendOne, outreachSendBulk, getSettings,
  outreachGenerateFollowUps, outreachFindEmail, updateAccount,
} from '../api'

const STATUS_STYLES = {
  draft: 'bg-gray-100 text-gray-600',
  approved: 'bg-blue-100 text-blue-800',
  queued: 'bg-indigo-100 text-indigo-700',
  sending: 'bg-amber-100 text-amber-800',
  sent: 'bg-emerald-100 text-emerald-800',
  failed: 'bg-red-100 text-red-700',
  skipped: 'bg-gray-100 text-gray-500',
}

function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[status] || 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}

const STEPS = [
  { key: 'upload', label: 'Upload' },
  { key: 'generate', label: 'Generate' },
  { key: 'review', label: 'Review & Send' },
]

export default function BulkOutreach() {
  const [step, setStep] = useState('upload')
  const [error, setError] = useState(null)

  // Upload state
  const [uploadMode, setUploadMode] = useState('file') // 'file' | 'sheet'
  const [sheetUrl, setSheetUrl] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [preview, setPreview] = useState(null)
  const [sourceFilename, setSourceFilename] = useState('leads.xlsx')
  const [dedupe, setDedupe] = useState('skip')
  const [committing, setCommitting] = useState(false)
  const fileInputRef = useRef(null)

  // Generate state
  const [committedAccountIds, setCommittedAccountIds] = useState([])
  const [generateMethod, setGenerateMethod] = useState('sync')
  const [generateModel, setGenerateModel] = useState('')
  const [generating, setGenerating] = useState(false)
  const [currentBatch, setCurrentBatch] = useState(null)

  // Review state
  const [emails, setEmails] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState({ subject: '', body: '' })
  const [loadingEmails, setLoadingEmails] = useState(false)

  // Send state
  const [sendMode, setSendMode] = useState('dry_run')
  const [outreachFromEmail, setOutreachFromEmail] = useState('')
  const [sending, setSending] = useState(false)
  const [sendResults, setSendResults] = useState(null)

  // Extras
  const [genNotice, setGenNotice] = useState(null)          // "N already-contacted leads skipped"
  const [followUpLoading, setFollowUpLoading] = useState(false)
  const [followUpNotice, setFollowUpNotice] = useState(null)
  const [findState, setFindState] = useState({})            // emailId -> {loading, email, email_status, message, error}

  useEffect(() => {
    getSettings().then(data => {
      const map = {}
      data.forEach(s => { map[s.key] = s.value })
      setSendMode(map.OUTREACH_SEND_MODE || 'dry_run')
      setOutreachFromEmail(map.OUTREACH_FROM_EMAIL || '')
    }).catch(() => {})
  }, [])

  // ── Upload ──────────────────────────────────────────────────────────────

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setSourceFilename(file.name)
    setPreviewLoading(true)
    setError(null)
    setPreview(null)
    try {
      const result = await outreachPreviewFile(file)
      setPreview(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleSheetPreview = async () => {
    if (!sheetUrl.trim()) return
    setPreviewLoading(true)
    setError(null)
    setSourceFilename('google_sheet.csv')
    try {
      const result = await outreachPreviewGoogleSheet(sheetUrl.trim())
      setPreview(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleCommitImport = async () => {
    if (!preview) return
    setCommitting(true)
    setError(null)
    try {
      const result = await outreachCommitImport(preview.rows, sourceFilename, dedupe)
      setCommittedAccountIds(result.account_ids)
      setStep('generate')
    } catch (err) {
      setError(err.message)
    } finally {
      setCommitting(false)
    }
  }

  // ── Generate ────────────────────────────────────────────────────────────

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    setGenNotice(null)
    try {
      const result = await outreachGenerate(committedAccountIds, generateMethod, generateModel || null)
      setCurrentBatch(result.batch)
      const skipped = (result.skipped_contacted || 0) + (result.skipped_do_not_contact || 0)
      if (skipped > 0) {
        setGenNotice(`${skipped} lead(s) were skipped — already contacted or opted out — so nobody gets a duplicate intro.`)
      }
      if (generateMethod === 'sync') {
        setEmails(result.emails || [])
        setStep('review')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerating(false)
    }
  }

  const handleGenerateFollowUps = async () => {
    setFollowUpLoading(true)
    setError(null)
    setFollowUpNotice(null)
    try {
      const result = await outreachGenerateFollowUps()
      if (!result.batch) {
        setFollowUpNotice(result.message || 'No leads need a follow-up right now.')
        return
      }
      setCurrentBatch(result.batch)
      setEmails(result.emails || [])
      setStatusFilter('')
      setStep('review')
    } catch (err) {
      setError(err.message)
    } finally {
      setFollowUpLoading(false)
    }
  }

  const handlePollBatch = async () => {
    if (!currentBatch) return
    setGenerating(true)
    setError(null)
    try {
      const result = await outreachRefreshBatch(currentBatch.id)
      setCurrentBatch(result.batch)
      if (result.batch.status === 'ready') {
        const emailsResult = await outreachGetEmails({ batch_id: currentBatch.id })
        setEmails(emailsResult)
        setStep('review')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerating(false)
    }
  }

  // ── Review ──────────────────────────────────────────────────────────────

  const refreshEmails = async () => {
    if (!currentBatch) return
    setLoadingEmails(true)
    try {
      const params = { batch_id: currentBatch.id }
      if (statusFilter) params.status = statusFilter
      const result = await outreachGetEmails(params)
      setEmails(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingEmails(false)
    }
  }

  useEffect(() => {
    if (step === 'review' && currentBatch) refreshEmails()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, step])

  // Auto-poll a queued Batch API job so the user never has to click "Check Now"
  useEffect(() => {
    if (!currentBatch || currentBatch.method !== 'batch_api') return
    if (['ready', 'failed'].includes(currentBatch.status)) return
    const t = setInterval(() => { handlePollBatch() }, 20000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentBatch])

  // While the background send queue is draining, keep the list fresh
  const hasActiveSends = emails.some(e => ['queued', 'sending'].includes(e.status))
  useEffect(() => {
    if (step !== 'review' || !hasActiveSends) return
    const t = setInterval(() => { refreshEmails() }, 5000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, hasActiveSends])

  // ── Find a missing email via Apollo ────────────────────────────────────────

  const handleFindEmail = async (email) => {
    setFindState(s => ({ ...s, [email.id]: { loading: true } }))
    try {
      const r = await outreachFindEmail(email.account_id)
      setFindState(s => ({ ...s, [email.id]: { loading: false, ...r } }))
    } catch (err) {
      setFindState(s => ({ ...s, [email.id]: { loading: false, error: err.message } }))
    }
  }

  const handleUseFoundEmail = async (email) => {
    const cand = findState[email.id]
    if (!cand?.email) return
    try {
      await updateAccount(email.account_id, { contact_email: cand.email })
      setFindState(s => { const c = { ...s }; delete c[email.id]; return c })
      await refreshEmails()
    } catch (err) {
      setError(err.message)
    }
  }

  const startEdit = (email) => {
    setEditingId(email.id)
    setEditForm({ subject: email.subject || '', body: email.body || '' })
  }

  const saveEdit = async (id) => {
    try {
      const updated = await outreachUpdateEmail(id, editForm)
      setEmails(prev => prev.map(e => e.id === id ? updated : e))
      setEditingId(null)
    } catch (err) {
      setError(err.message)
    }
  }

  const toggleApprove = async (email) => {
    try {
      const updated = email.status === 'approved'
        ? await outreachUnapproveEmail(email.id)
        : await outreachApproveEmail(email.id)
      setEmails(prev => prev.map(e => e.id === email.id ? updated : e))
    } catch (err) {
      setError(err.message)
    }
  }

  const handleBulkApprove = async () => {
    const draftIds = emails.filter(e => e.status === 'draft').map(e => e.id)
    if (draftIds.length === 0) return
    try {
      const updated = await outreachBulkApprove(draftIds)
      const byId = new Map(updated.map(e => [e.id, e]))
      setEmails(prev => prev.map(e => byId.get(e.id) || e))
    } catch (err) {
      setError(err.message)
    }
  }

  // ── Send ────────────────────────────────────────────────────────────────

  const handleSendOne = async (id) => {
    try {
      const result = await outreachSendOne(id)
      await refreshEmails()
      setSendResults({ single: result })
    } catch (err) {
      setError(err.message)
    }
  }

  const isSendable = (e) => e.status === 'approved' && e.account_has_email && !e.account_do_not_contact

  const handleSendApproved = async () => {
    const approvedIds = emails.filter(isSendable).map(e => e.id)
    if (approvedIds.length === 0) return
    if (sendMode === 'live') {
      const confirmed = window.confirm(
        `You are about to send ${approvedIds.length} REAL email(s) to real prospects from ${outreachFromEmail}, spaced out in the background. This cannot be undone. Continue?`
      )
      if (!confirmed) return
    }
    setSending(true)
    setError(null)
    try {
      const result = await outreachSendBulk(approvedIds)
      setSendResults(result)
      await refreshEmails()
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  const approvedCount = emails.filter(e => e.status === 'approved').length
  const sendableApprovedCount = emails.filter(isSendable).length
  const draftCount = emails.filter(e => e.status === 'draft').length
  const sentCount = emails.filter(e => e.status === 'sent').length
  const emailMissingCount = emails.filter(e => !e.account_has_email).length

  return (
    <div className="space-y-5 max-w-6xl">
      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {STEPS.map((s, i) => (
          <div key={s.key} className="flex items-center gap-2">
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold ${
              step === s.key ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-500'
            }`}>
              {i + 1}. {s.label}
            </div>
            {i < STEPS.length - 1 && <ChevronRight className="w-3.5 h-3.5 text-gray-300" />}
          </div>
        ))}
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />{error}
        </div>
      )}

      {sendMode === 'dry_run' && step === 'review' && (
        <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span><strong>Dry-run mode:</strong> sends route to a test address, not real prospects. Switch to live mode in Settings when ready.</span>
        </div>
      )}

      {/* STEP: Upload */}
      {step === 'upload' && (
        <div className="card p-6 space-y-5">
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
              className="border-2 border-dashed border-gray-300 rounded-xl p-10 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50/30 transition-colors"
            >
              <Upload className="w-8 h-8 mx-auto mb-2 text-gray-400" />
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
                  <p className="text-xs text-red-500">Missing email (unsendable)</p>
                </div>
              </div>

              <div className="border border-gray-200 rounded-xl overflow-x-auto max-h-80 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="text-left px-3 py-2 font-semibold text-gray-500">Company</th>
                      <th className="text-left px-3 py-2 font-semibold text-gray-500">Contact</th>
                      <th className="text-left px-3 py-2 font-semibold text-gray-500">Title</th>
                      <th className="text-left px-3 py-2 font-semibold text-gray-500">Email</th>
                      <th className="text-left px-3 py-2 font-semibold text-gray-500">Flags</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {preview.rows.map((r, i) => (
                      <tr key={i}>
                        <td className="px-3 py-2 font-medium text-gray-800">{r.company_name}</td>
                        <td className="px-3 py-2 text-gray-600">{r.contact_name}</td>
                        <td className="px-3 py-2 text-gray-500">{r.contact_title}</td>
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
                <button onClick={handleCommitImport} disabled={committing} className="btn-primary text-sm px-5 flex items-center gap-2">
                  {committing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Users className="w-4 h-4" />}
                  Import {preview.row_count} Leads
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Follow-ups — separate from uploading new leads */}
      {step === 'upload' && (
        <div className="card p-5 flex items-center justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-gray-900 flex items-center gap-1.5">
              <Reply className="w-4 h-4 text-blue-600" />Already sent intros?
            </p>
            <p className="text-xs text-gray-500 mt-0.5">
              Drafts a short, friendly follow-up for every lead you emailed 4+ days ago who hasn't replied.
              You still review and approve each one before anything is sent.
            </p>
            {followUpNotice && <p className="text-xs text-amber-600 mt-1.5">{followUpNotice}</p>}
          </div>
          <button onClick={handleGenerateFollowUps} disabled={followUpLoading}
            className="btn-primary text-sm px-4 flex items-center gap-2 shrink-0">
            {followUpLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Reply className="w-4 h-4" />}
            Generate Follow-ups
          </button>
        </div>
      )}

      {/* STEP: Generate */}
      {step === 'generate' && (
        <div className="card p-6 space-y-5">
          <p className="text-sm text-gray-600">{committedAccountIds.length} leads imported. Choose how to generate their cold emails.</p>

          <div className="grid grid-cols-2 gap-4">
            <button
              onClick={() => setGenerateMethod('sync')}
              className={`text-left p-4 rounded-xl border-2 transition-colors ${
                generateMethod === 'sync' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <p className="font-semibold text-sm text-gray-900 flex items-center gap-1.5"><Sparkles className="w-4 h-4" />Generate Now</p>
              <p className="text-xs text-gray-500 mt-1">Immediate results, a few chunked API calls. Best for smaller lists or when you need drafts right away.</p>
            </button>
            <button
              onClick={() => setGenerateMethod('batch_api')}
              className={`text-left p-4 rounded-xl border-2 transition-colors ${
                generateMethod === 'batch_api' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <p className="font-semibold text-sm text-gray-900 flex items-center gap-1.5"><Clock className="w-4 h-4" />Queue Cheaply</p>
              <p className="text-xs text-gray-500 mt-1">~50% cheaper via OpenAI's Batch API. Results arrive within minutes to a few hours — best for large lists.</p>
            </button>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Model (optional)</label>
            <input
              value={generateModel}
              onChange={e => setGenerateModel(e.target.value)}
              className="input"
              placeholder="Default: gpt-4o (try gpt-4o-mini for ~15x cheaper)"
            />
          </div>

          {genNotice && (
            <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm">
              <AlertTriangle className="w-4 h-4 shrink-0" />{genNotice}
            </div>
          )}

          {currentBatch && currentBatch.method === 'batch_api' && currentBatch.status !== 'ready' && (
            <div className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
              <Loader2 className="w-4 h-4 animate-spin" />
              Batch job {currentBatch.status} — checking automatically every 20 seconds, no need to do anything.
              <button onClick={handlePollBatch} disabled={generating} className="btn-secondary text-xs ml-auto flex items-center gap-1">
                <RefreshCw className="w-3 h-3" />Check Now
              </button>
            </div>
          )}

          <div className="flex justify-between">
            <button onClick={() => setStep('upload')} className="text-sm text-gray-500 hover:text-gray-800 flex items-center gap-1">
              <ChevronLeft className="w-4 h-4" />Back
            </button>
            <button onClick={handleGenerate} disabled={generating} className="btn-primary text-sm px-5 flex items-center gap-2">
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              {generateMethod === 'sync' ? 'Generate Emails' : 'Queue Batch Job'}
            </button>
          </div>
        </div>
      )}

      {/* STEP: Review & Send */}
      {step === 'review' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex gap-2 flex-wrap">
              {['', 'draft', 'approved', 'queued', 'sent', 'failed', 'skipped'].map(s => (
                <button
                  key={s || 'all'}
                  onClick={() => setStatusFilter(s)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold ${
                    statusFilter === s ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {s || `All (${emails.length})`}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2">
              {emailMissingCount > 0 && (
                <span className="text-xs text-red-500 flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5" />{emailMissingCount} need an email address
                </span>
              )}
              <button onClick={refreshEmails} disabled={loadingEmails} className="btn-secondary text-xs flex items-center gap-1.5">
                <RefreshCw className={`w-3.5 h-3.5 ${loadingEmails ? 'animate-spin' : ''}`} />Refresh
              </button>
              {draftCount > 0 && (
                <button onClick={handleBulkApprove} className="btn-primary text-xs px-3 flex items-center gap-1.5">
                  <Check className="w-3.5 h-3.5" />Approve All Drafts ({draftCount})
                </button>
              )}
            </div>
          </div>

          <div className="space-y-3">
            {emails.length === 0 ? (
              <div className="card p-10 text-center text-gray-400">
                <Mail className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">No emails match this filter.</p>
              </div>
            ) : emails.map(email => (
              <div key={email.id} className="card p-4 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <p className="font-semibold text-sm text-gray-900 truncate">{email.account_company}</p>
                    <span className="text-xs text-gray-400 truncate">{email.account_contact}</span>
                    {email.is_follow_up && (
                      <span className="shrink-0 px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-[10px] font-semibold">FOLLOW-UP</span>
                    )}
                    {email.account_do_not_contact && (
                      <span className="shrink-0 px-1.5 py-0.5 bg-gray-800 text-white rounded text-[10px] font-semibold flex items-center gap-1">
                        <Ban className="w-2.5 h-2.5" />OPTED OUT
                      </span>
                    )}
                    {!email.account_has_email && !email.account_do_not_contact && (
                      <>
                        <span className="shrink-0 px-1.5 py-0.5 bg-red-100 text-red-600 rounded text-[10px] font-semibold">EMAIL NEEDED</span>
                        <button
                          onClick={() => handleFindEmail(email)}
                          disabled={findState[email.id]?.loading}
                          className="shrink-0 flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-violet-100 text-violet-700 hover:bg-violet-200"
                        >
                          {findState[email.id]?.loading
                            ? <Loader2 className="w-3 h-3 animate-spin" />
                            : <Search className="w-3 h-3" />}
                          Find email
                        </button>
                      </>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <StatusBadge status={email.status} />
                    {['draft', 'approved'].includes(email.status) && (
                      <button onClick={() => startEdit(email)} className="text-gray-400 hover:text-gray-700"><Pencil className="w-3.5 h-3.5" /></button>
                    )}
                  </div>
                </div>

                {findState[email.id] && !findState[email.id].loading && (
                  <div className="flex items-center gap-2 flex-wrap p-2.5 bg-violet-50 border border-violet-200 rounded-lg text-xs">
                    {findState[email.id].email ? (
                      <>
                        <span className="text-violet-900">
                          Apollo found: <strong>{findState[email.id].email}</strong>
                          {findState[email.id].email_status && <span className="text-violet-500"> ({findState[email.id].email_status})</span>}
                        </span>
                        <button onClick={() => handleUseFoundEmail(email)}
                          className="px-2.5 py-1 rounded bg-violet-600 text-white font-semibold hover:bg-violet-700">
                          Use this email
                        </button>
                        <button onClick={() => setFindState(s => { const c = { ...s }; delete c[email.id]; return c })}
                          className="text-violet-400 hover:text-violet-700">Dismiss</button>
                      </>
                    ) : (
                      <span className="text-violet-800">
                        {findState[email.id].error || findState[email.id].message || 'No email found for this lead.'}
                      </span>
                    )}
                  </div>
                )}

                {editingId === email.id ? (
                  <div className="space-y-2">
                    <input
                      value={editForm.subject}
                      onChange={e => setEditForm(f => ({ ...f, subject: e.target.value }))}
                      className="input text-sm"
                      placeholder="Subject"
                    />
                    <textarea
                      value={editForm.body}
                      onChange={e => setEditForm(f => ({ ...f, body: e.target.value }))}
                      className="input text-sm min-h-32"
                      rows={5}
                    />
                    <div className="flex justify-end gap-2">
                      <button onClick={() => setEditingId(null)} className="text-xs text-gray-500 hover:text-gray-800 px-3 py-1.5">Cancel</button>
                      <button onClick={() => saveEdit(email.id)} className="btn-primary text-xs px-3 py-1.5">Save</button>
                    </div>
                  </div>
                ) : (
                  <>
                    {email.error && (
                      <p className="text-xs text-red-600 flex items-center gap-1"><AlertCircle className="w-3.5 h-3.5" />{email.error}</p>
                    )}
                    <p className="text-sm font-medium text-gray-800">{email.subject}</p>
                    <p className="text-sm text-gray-600 whitespace-pre-wrap">{email.body}</p>
                  </>
                )}

                <div className="flex justify-end gap-2 pt-1">
                  {['draft', 'approved'].includes(email.status) && (
                    <button
                      onClick={() => toggleApprove(email)}
                      className={`text-xs px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1 ${
                        email.status === 'approved' ? 'bg-gray-100 text-gray-600' : 'bg-blue-600 text-white'
                      }`}
                    >
                      {email.status === 'approved' ? <><X className="w-3.5 h-3.5" />Unapprove</> : <><Check className="w-3.5 h-3.5" />Approve</>}
                    </button>
                  )}
                  {email.status === 'approved' && (
                    <button
                      onClick={() => handleSendOne(email.id)}
                      disabled={!email.account_has_email || email.account_do_not_contact}
                      className="text-xs px-3 py-1.5 rounded-lg font-semibold bg-emerald-600 text-white flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <Send className="w-3.5 h-3.5" />Send
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-between items-center card p-4">
            <div className="text-sm text-gray-500">
              {approvedCount} approved ({sendableApprovedCount} sendable) · {sentCount} sent
            </div>
            <button
              onClick={handleSendApproved}
              disabled={sending || sendableApprovedCount === 0}
              className="btn-primary text-sm px-5 flex items-center gap-2"
            >
              {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Send {sendableApprovedCount} Approved {sendMode === 'dry_run' ? '(Dry Run)' : ''}
            </button>
          </div>

          {sendResults && (
            <div className="card p-4">
              <p className="text-sm font-semibold text-gray-900 mb-2">Send Results</p>
              {sendResults.queued > 0 ? (
                <div className="text-xs flex items-center gap-2 text-indigo-700">
                  {hasActiveSends ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
                  {hasActiveSends
                    ? (sendResults.message || `${sendResults.queued} email(s) queued — sending in the background.`)
                    : 'Background sending finished — statuses above are final.'}
                </div>
              ) : sendResults.results && sendResults.results.length > 0 ? (
                <div className="space-y-1">
                  {sendResults.results.map(r => (
                    <div key={r.id} className={`text-xs flex items-center gap-2 ${r.ok ? 'text-emerald-600' : 'text-red-500'}`}>
                      {r.ok ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                      #{r.id} {r.ok ? (r.dry_run ? `dry-run → ${r.sent_to}` : `sent to ${r.sent_to}`) : r.error}
                    </div>
                  ))}
                </div>
              ) : sendResults.single && (
                <div className={`text-xs flex items-center gap-2 ${sendResults.single.ok ? 'text-emerald-600' : 'text-red-500'}`}>
                  {sendResults.single.ok ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                  {sendResults.single.ok ? (sendResults.single.dry_run ? `Dry-run → ${sendResults.single.sent_to}` : `Sent to ${sendResults.single.sent_to}`) : sendResults.single.error}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
