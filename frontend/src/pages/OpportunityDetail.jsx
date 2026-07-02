import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft, Loader2, AlertCircle, FileText, Trash2, Eye,
  Package, Mail, ExternalLink, CheckCircle,
  AlertTriangle, RefreshCw, ThumbsUp, ThumbsDown, HelpCircle,
  ChevronDown, ChevronUp, Lock, ClipboardCheck, Send, Download,
} from 'lucide-react'
import {
  getOpportunity, updateStatus, deleteOpportunity,
  uploadDocument, deleteDocument, reviewDocuments,
  buildPacket, getPacket, emailPacket, scoreGoNoGo, exportPacket, revisePacket,
  completeDraftProposal,
} from '../api'
import StatusBadge from '../components/StatusBadge'
import FileUpload from '../components/FileUpload'

const VALID_STATUSES = [
  'New', 'Under Review', 'Relevant', 'Possibly Relevant', 'Not Relevant',
  'EMMA Documents Needed', 'Documents Uploaded', 'Packet Building',
  'Packet Ready', 'Reviewed by User', 'Approved to Pursue', 'Declined',
]

// ─── Workflow Stepper ────────────────────────────────────────────────────────

function WorkflowStepper({ steps }) {
  return (
    <div className="card px-5 py-4">
      <div className="flex items-center gap-0">
        {steps.map((step, i) => (
          <div key={i} className="flex items-center flex-1 min-w-0">
            <div className="flex flex-col items-center shrink-0">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                step.done ? 'bg-emerald-500 text-white'
                : step.active ? 'bg-blue-600 text-white ring-2 ring-blue-200'
                : 'bg-gray-100 text-gray-400'
              }`}>
                {step.done ? <CheckCircle className="w-4 h-4" /> : step.active ? <span>{i + 1}</span> : <span>{i + 1}</span>}
              </div>
              <p className={`text-xs mt-1.5 font-medium text-center leading-tight max-w-[80px] ${
                step.done ? 'text-emerald-600' : step.active ? 'text-blue-700' : 'text-gray-400'
              }`}>{step.label}</p>
              {step.sub && (
                <p className={`text-xs text-center leading-tight max-w-[80px] ${step.done ? 'text-emerald-500' : step.active ? 'text-blue-500' : 'text-gray-300'}`}>
                  {step.sub}
                </p>
              )}
            </div>
            {i < steps.length - 1 && (
              <div className={`flex-1 h-0.5 mx-2 mb-5 transition-colors ${step.done ? 'bg-emerald-300' : 'bg-gray-200'}`} />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Checklist ───────────────────────────────────────────────────────────────

function parseChecklistItems(text) {
  return (text || '').split('\n')
    .map(l => l.replace(/^\d+\.\s*/, '').replace(/^[-*•]\s*/, '').replace(/^- \[[ x]\]\s*/i, '').trim())
    .filter(l => l.length > 2)
    .map(l => {
      const onFile = /\[on file\]\s*$/i.test(l)
      return { text: l.replace(/\s*\[on file\]\s*$/i, '').trim(), onFile }
    })
}

function SubmissionChecklist({ text, opportunityId, onProgressChange }) {
  const storageKey = `ff_checklist_${opportunityId}`
  const items = parseChecklistItems(text)
  const [checked, setChecked] = useState(() => {
    let stored = {}
    try { stored = JSON.parse(localStorage.getItem(storageKey) || '{}') } catch {}
    const next = { ...stored }
    let changed = false
    items.forEach((item, i) => {
      if (item.onFile && !(i in next)) { next[i] = true; changed = true }
    })
    if (changed) localStorage.setItem(storageKey, JSON.stringify(next))
    return next
  })
  const [expanded, setExpanded] = useState(true)

  useEffect(() => {
    const done = items.filter((_, i) => checked[i]).length
    const unchecked = items.filter((_, i) => !checked[i]).map(item => item.text)
    onProgressChange?.(done, items.length, unchecked)
  }, [checked]) // eslint-disable-line

  const toggle = (i) => {
    const next = { ...checked, [i]: !checked[i] }
    setChecked(next)
    localStorage.setItem(storageKey, JSON.stringify(next))
  }

  const reset = () => { setChecked({}); localStorage.removeItem(storageKey) }

  const done = items.filter((_, i) => checked[i]).length
  const pct = items.length ? Math.round((done / items.length) * 100) : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <span className={`text-lg font-bold ${pct === 100 ? 'text-emerald-600' : 'text-blue-700'}`}>{done}/{items.length}</span>
          <span className="text-sm text-gray-500">documents gathered</span>
          {pct === 100 && <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-semibold rounded-full">Complete</span>}
        </div>
        <div className="flex items-center gap-3">
          {done > 0 && <button onClick={reset} className="text-xs text-gray-400 hover:text-red-500">Reset</button>}
          <button onClick={() => setExpanded(e => !e)} className="text-gray-400 hover:text-gray-600">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      <div className="w-full bg-gray-100 rounded-full h-2.5 mb-4">
        <div
          className={`h-2.5 rounded-full transition-all duration-500 ${pct === 100 ? 'bg-emerald-500' : 'bg-blue-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {expanded && (
        <ul className="space-y-1.5">
          {items.map((item, i) => (
            <li key={i} onClick={() => toggle(i)}
              className={`flex items-start gap-3 text-sm cursor-pointer rounded-lg px-3 py-2.5 hover:bg-gray-50 transition-colors border ${
                checked[i] ? 'border-emerald-100 bg-emerald-50/40' : 'border-transparent'
              }`}>
              <div className={`mt-0.5 w-4 h-4 shrink-0 rounded border flex items-center justify-center transition-colors ${
                checked[i] ? 'bg-emerald-500 border-emerald-500' : 'border-gray-300 bg-white'
              }`}>
                {checked[i] && <CheckCircle className="w-3 h-3 text-white" />}
              </div>
              <span className={`flex-1 leading-snug ${checked[i] ? 'line-through text-gray-400' : 'text-gray-800'}`}>
                {item.text}
                {item.onFile && <span className="ml-1.5 text-xs text-gray-400 no-underline">(on file)</span>}
              </span>
              {checked[i] && <CheckCircle className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ─── Go/No-Go ────────────────────────────────────────────────────────────────

function GoNoGoPanel({ result }) {
  const { verdict, score, factors, recommendation, conditions, next_steps, red_flags } = result
  const verdictStyles = {
    'BID': { bg: 'bg-emerald-50 border-emerald-200', badge: 'bg-emerald-600 text-white', icon: ThumbsUp },
    'BID WITH CONDITIONS': { bg: 'bg-amber-50 border-amber-200', badge: 'bg-amber-500 text-white', icon: HelpCircle },
    'NO-BID': { bg: 'bg-red-50 border-red-200', badge: 'bg-red-600 text-white', icon: ThumbsDown },
  }
  const style = verdictStyles[verdict] || verdictStyles['BID WITH CONDITIONS']
  const Icon = style.icon
  const factorRows = [
    { label: 'Service Alignment', key: 'alignment', max: 25 },
    { label: 'Eligibility & Compliance', key: 'eligibility', max: 25 },
    { label: 'Risk Level (lower = worse)', key: 'risk', max: 20 },
    { label: 'Contract Value & Scope', key: 'value', max: 15 },
    { label: 'Competitive Position', key: 'competitive', max: 15 },
  ]
  return (
    <div className={`border rounded-xl p-4 space-y-4 ${style.bg}`}>
      <div className="flex items-center gap-3">
        <span className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-bold ${style.badge}`}>
          <Icon className="w-4 h-4" />{verdict}
        </span>
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold text-gray-500">Overall Score</span>
            <span className="text-sm font-bold text-gray-800">{score}/100</span>
          </div>
          <div className="w-full bg-white rounded-full h-2 overflow-hidden border border-gray-200">
            <div className={`h-2 rounded-full ${score >= 70 ? 'bg-emerald-500' : score >= 45 ? 'bg-amber-400' : 'bg-red-500'}`} style={{ width: `${score}%` }} />
          </div>
        </div>
      </div>
      <div className="space-y-1.5">
        {factorRows.map(({ label, key, max }) => {
          const val = factors[key] ?? 0
          return (
            <div key={key} className="flex items-center gap-2 text-xs">
              <span className="w-48 text-gray-600 shrink-0">{label}</span>
              <div className="flex-1 bg-white rounded-full h-1.5 overflow-hidden border border-gray-200">
                <div className="h-1.5 bg-blue-500 rounded-full" style={{ width: `${Math.round((val / max) * 100)}%` }} />
              </div>
              <span className="w-12 text-right font-medium text-gray-700">{val}/{max}</span>
            </div>
          )
        })}
      </div>
      {recommendation && <p className="text-sm text-gray-700">{recommendation}</p>}
      {conditions?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-amber-700 mb-1">Conditions to Resolve</p>
          <ul className="space-y-1">{conditions.map((c, i) => <li key={i} className="text-xs text-amber-800 flex gap-1.5"><span>•</span>{c}</li>)}</ul>
        </div>
      )}
      {red_flags?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-red-600 mb-1">Red Flags</p>
          <ul className="space-y-1">{red_flags.map((f, i) => <li key={i} className="text-xs text-red-700 flex gap-1.5"><AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />{f}</li>)}</ul>
        </div>
      )}
      {next_steps?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-600 mb-1">Next Steps</p>
          <ol className="space-y-1 list-decimal list-inside">{next_steps.map((s, i) => <li key={i} className="text-xs text-gray-700">{s}</li>)}</ol>
        </div>
      )}
    </div>
  )
}

function Field({ label, value, mono = false, link = false }) {
  if (!value) return null
  return (
    <div>
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      {link ? (
        <a href={value} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline flex items-center gap-1">
          {value} <ExternalLink className="w-3 h-3" />
        </a>
      ) : (
        <p className={`text-sm text-gray-900 whitespace-pre-wrap ${mono ? 'font-mono' : ''}`}>{value}</p>
      )}
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function OpportunityDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [opp, setOpp] = useState(null)
  const [packet, setPacket] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionLoading, setActionLoading] = useState(null)
  const [showPacket, setShowPacket] = useState(false)
  const [toast, setToast] = useState(null)
  const [customInstructions, setCustomInstructions] = useState('')
  const [gonogo, setGonogo] = useState(null)
  const [gonogoLoading, setGonogoLoading] = useState(false)
  const [checklistProgress, setChecklistProgress] = useState({ done: 0, total: 0, unchecked: [] })
  const [bypassChecklist, setBypassChecklist] = useState(false)
  const [revisionInstruction, setRevisionInstruction] = useState('')
  const [revising, setRevising] = useState(false)
  const [lastRevision, setLastRevision] = useState(null)
  const [draftMode, setDraftMode] = useState('upload')
  const [draftDocumentId, setDraftDocumentId] = useState('')
  const [draftText, setDraftText] = useState('')
  const [draftAnalysis, setDraftAnalysis] = useState(null)
  const [uploadingDraft, setUploadingDraft] = useState(false)
  const [draftUploadError, setDraftUploadError] = useState(null)
  const draftFileInputRef = useRef(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const load = useCallback(async () => {
    try {
      const data = await getOpportunity(id)
      setOpp(data)
      setError(null)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [id])

  const loadPacket = useCallback(async () => {
    try { const p = await getPacket(id); setPacket(p) } catch {}
  }, [id])

  useEffect(() => { load() }, [load])
  useEffect(() => { if (opp?.status === 'Packet Ready' || opp?.status === 'Reviewed by User') loadPacket() }, [opp, loadPacket])

  const handleStatusChange = async (newStatus) => {
    setActionLoading('status')
    try { const updated = await updateStatus(id, newStatus); setOpp(updated); showToast(`Status updated to "${newStatus}"`) }
    catch (e) { showToast(e.message, 'error') }
    finally { setActionLoading(null) }
  }

  const handleDelete = async () => {
    if (!confirm('Delete this opportunity and all related documents? This cannot be undone.')) return
    setActionLoading('delete')
    try { await deleteOpportunity(id); navigate('/opportunities') }
    catch (e) { showToast(e.message, 'error'); setActionLoading(null) }
  }

  const handleDeleteDoc = async (docId) => {
    if (!confirm('Delete this document?')) return
    try { await deleteDocument(id, docId); load(); showToast('Document deleted') }
    catch (e) { showToast(e.message, 'error') }
  }

  const handleReviewDocs = async () => {
    setActionLoading('review')
    try { const updated = await reviewDocuments(id); setOpp(updated); showToast('AI review complete — checklist extracted') }
    catch (e) { showToast(e.message, 'error') }
    finally { setActionLoading(null) }
  }

  const handleBuildPacket = async () => {
    setActionLoading('packet')
    try {
      const p = await buildPacket(id, customInstructions)
      setPacket(p)
      const updated = await getOpportunity(id)
      setOpp(updated)
      setShowPacket(true)
      showToast('Proposal packet built successfully!')
    } catch (e) { showToast(e.message, 'error') }
    finally { setActionLoading(null) }
  }

  const handleGoNoGo = async () => {
    setGonogoLoading(true)
    try { const result = await scoreGoNoGo(id); setGonogo(result) }
    catch (e) { showToast(e.message, 'error') }
    finally { setGonogoLoading(false) }
  }

  const handleEmailPacket = async () => {
    setActionLoading('email')
    try { const result = await emailPacket(id); showToast(`Packet emailed to ${result.to}`) }
    catch (e) { showToast(e.message, 'error') }
    finally { setActionLoading(null) }
  }

  const handleExportPacket = async (format) => {
    setActionLoading(`export-${format}`)
    try { await exportPacket(id, format); showToast(`Downloaded ${format.toUpperCase()}`) }
    catch (e) { showToast(e.message, 'error') }
    finally { setActionLoading(null) }
  }

  const handleDraftFileSelected = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    const allowed = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.zip']
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!allowed.includes(ext)) {
      setDraftUploadError('Unsupported file type. Allowed: PDF, Word, Excel, ZIP')
      return
    }
    setDraftUploadError(null)
    setUploadingDraft(true)
    try {
      const doc = await uploadDocument(id, file)
      await load()
      setDraftDocumentId(String(doc.id))
      setDraftMode('document')
    } catch (err) {
      setDraftUploadError(err.message)
    } finally {
      setUploadingDraft(false)
    }
  }

  const handleCompleteDraft = async () => {
    setActionLoading('complete-draft')
    try {
      const payload = draftMode === 'paste'
        ? { draft_text: draftText, custom_instructions: customInstructions }
        : { document_id: Number(draftDocumentId), custom_instructions: customInstructions }
      const result = await completeDraftProposal(id, payload)
      setPacket(result.packet)
      setDraftAnalysis(result.analysis)
      const updated = await getOpportunity(id)
      setOpp(updated)
      setShowPacket(true)
      showToast('Draft analyzed and completed!')
    } catch (e) { showToast(e.message, 'error') }
    finally { setActionLoading(null) }
  }

  const handleRevise = async (e) => {
    e.preventDefault()
    if (!revisionInstruction.trim()) return
    setRevising(true)
    try {
      const p = await revisePacket(id, revisionInstruction.trim())
      setPacket(p)
      setLastRevision(revisionInstruction.trim())
      setRevisionInstruction('')
      showToast('Proposal revised')
    } catch (e) { showToast(e.message, 'error') }
    finally { setRevising(false) }
  }

  const buildEmailBernedetteLink = () => {
    const title = opp?.opportunity_title || opp?.email_subject || 'this opportunity'
    const agency = opp?.agency_name ? ` — ${opp.agency_name}` : ''
    const list = checklistProgress.unchecked.map(item => `  • ${item}`).join('\n')
    const body = `Hi Bernedette,\n\nI am processing the proposal for:\n${title}${agency}\n\nI need the following documents from the submission checklist to proceed:\n\n${list}\n\nPlease send these documents when you are available so I can upload them and complete the proposal.\n\nThank you,\nSaba`
    return `mailto:bernedette.atong@faithforgetech.com?subject=${encodeURIComponent(`Documents Needed: ${title}`)}&body=${encodeURIComponent(body)}`
  }

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 animate-spin text-blue-600" /></div>
  if (error) return <div className="flex items-center gap-3 p-6 bg-red-50 rounded-xl text-red-700"><AlertCircle className="w-5 h-5" /><p>{error}</p></div>
  if (!opp) return null

  const hasPacket = !!packet || opp.status === 'Packet Ready' || opp.status === 'Reviewed by User'
  const hasDocuments = (opp.documents?.length ?? 0) > 0
  const hasChecklist = !!opp.submission_checklist
  const checklistComplete = checklistProgress.total === 0 || checklistProgress.done >= checklistProgress.total
  const checklistBlocking = hasChecklist && !checklistComplete && !bypassChecklist && !hasPacket

  const workflowSteps = [
    {
      label: 'Upload RFP',
      sub: hasDocuments ? `${opp.documents.length} file${opp.documents.length !== 1 ? 's' : ''}` : 'Upload files',
      done: hasDocuments,
      active: !hasDocuments,
    },
    {
      label: 'AI Review',
      sub: hasChecklist ? 'Checklist ready' : hasDocuments ? 'Run review' : 'Pending',
      done: hasChecklist,
      active: hasDocuments && !hasChecklist,
    },
    {
      label: 'Gather Docs',
      sub: hasChecklist
        ? `${checklistProgress.done}/${checklistProgress.total} complete`
        : 'Pending',
      done: hasChecklist && checklistComplete && checklistProgress.total > 0,
      active: hasChecklist && !checklistComplete,
    },
    {
      label: 'Build Proposal',
      sub: hasPacket ? 'Ready' : 'Locked',
      done: hasPacket,
      active: hasChecklist && checklistComplete,
    },
  ]

  return (
    <div className="space-y-5">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium ${toast.type === 'error' ? 'bg-red-600 text-white' : 'bg-green-600 text-white'}`}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Link to="/opportunities" className="btn-secondary p-2 mt-0.5"><ArrowLeft className="w-4 h-4" /></Link>
          <div>
            <h1 className="text-xl font-bold text-gray-900 leading-tight">
              {opp.opportunity_title || opp.email_subject || 'Untitled Opportunity'}
            </h1>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <StatusBadge status={opp.status} />
              {opp.relevance_classification && <StatusBadge status={opp.relevance_classification} type="classification" />}
              {opp.relevance_score != null && (
                <span className="text-xs text-gray-500 font-medium" title={opp.score_breakdown || ''}>
                  Score: {Math.round(opp.relevance_score)}/100
                </span>
              )}
              {opp.has_emma_link && <span className="px-2 py-0.5 bg-orange-100 text-orange-700 text-xs rounded font-medium">EMMA Required</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={load} className="btn-secondary p-2" title="Refresh"><RefreshCw className="w-4 h-4" /></button>
          <button onClick={handleDelete} disabled={actionLoading === 'delete'} className="btn-danger">
            {actionLoading === 'delete' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}Delete
          </button>
        </div>
      </div>

      {/* Status bar */}
      <div className="card p-4 flex items-center gap-3 flex-wrap">
        <span className="text-sm font-medium text-gray-700">Status:</span>
        <div className="flex flex-wrap gap-2">
          {VALID_STATUSES.map(s => (
            <button key={s} onClick={() => handleStatusChange(s)} disabled={actionLoading === 'status' || opp.status === s}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${opp.status === s ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
              {s}
            </button>
          ))}
        </div>
        {actionLoading === 'status' && <Loader2 className="w-4 h-4 animate-spin text-blue-600" />}
      </div>

      {/* Workflow Stepper */}
      <WorkflowStepper steps={workflowSteps} />

      {/* ── STEP 1 + 2: Documents + AI Review ── */}
      <div className="card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${hasDocuments ? 'bg-emerald-500 text-white' : 'bg-blue-600 text-white'}`}>
              {hasDocuments ? <CheckCircle className="w-3.5 h-3.5" /> : '1'}
            </div>
            <h3 className="font-semibold text-gray-900 text-sm">
              Step 1 — Upload Solicitation Documents
              {hasDocuments && <span className="ml-2 px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">{opp.documents.length}</span>}
            </h3>
          </div>
          {hasDocuments && (
            <button onClick={handleReviewDocs} disabled={actionLoading === 'review'} className="btn-secondary text-xs">
              {actionLoading === 'review'
                ? <><Loader2 className="w-3 h-3 animate-spin" /> Reviewing…</>
                : <><Eye className="w-3 h-3" /> {hasChecklist ? 'Re-run AI Review' : 'Step 2 — AI Review'}</>
              }
            </button>
          )}
        </div>

        {hasDocuments && (
          <div className="space-y-2">
            {opp.documents.map(doc => (
              <div key={doc.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <FileText className="w-5 h-5 text-blue-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{doc.original_filename}</p>
                  <p className="text-xs text-gray-500">
                    {doc.file_type?.toUpperCase()} · {doc.file_size ? `${(doc.file_size / 1024).toFixed(0)} KB` : ''}
                    {doc.reviewed && <span className="ml-2 text-green-600 font-medium">Reviewed</span>}
                  </p>
                </div>
                <button onClick={() => handleDeleteDoc(doc.id)} className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {!hasDocuments && (
          <p className="text-sm text-gray-400">Upload the RFP or solicitation documents. Once uploaded, run AI Review to extract the submission checklist.</p>
        )}

        <FileUpload opportunityId={id} onUploaded={load} />
      </div>

      {/* ── STEP 3: Submission Checklist ── */}
      {hasChecklist ? (
        <div className="card p-5 space-y-4 border-2 border-blue-100">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${checklistComplete && checklistProgress.total > 0 ? 'bg-emerald-500 text-white' : 'bg-blue-600 text-white'}`}>
                {checklistComplete && checklistProgress.total > 0 ? <CheckCircle className="w-3.5 h-3.5" /> : '3'}
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm">Step 3 — Gather Required Documents</h3>
                <p className="text-xs text-gray-500 mt-0.5">Check off each item as Bernedette provides the document. Build proposal only when all items are ready.</p>
              </div>
            </div>
            {checklistProgress.unchecked.length > 0 && (
              <a
                href={buildEmailBernedetteLink()}
                className="shrink-0 flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700 transition-colors"
              >
                <Send className="w-3.5 h-3.5" />
                Email Bernedette ({checklistProgress.unchecked.length} needed)
              </a>
            )}
            {checklistComplete && checklistProgress.total > 0 && (
              <span className="shrink-0 flex items-center gap-1.5 px-3 py-2 bg-emerald-100 text-emerald-700 text-xs font-semibold rounded-lg">
                <CheckCircle className="w-3.5 h-3.5" />All documents gathered
              </span>
            )}
          </div>
          <SubmissionChecklist
            text={opp.submission_checklist}
            opportunityId={opp.id}
            onProgressChange={(done, total, unchecked) => setChecklistProgress({ done, total, unchecked })}
          />
        </div>
      ) : hasDocuments ? (
        <div className="card p-5 flex items-center gap-4 border-2 border-dashed border-blue-200 bg-blue-50/40">
          <div className="w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center shrink-0 font-bold">2</div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-blue-900">Run AI Review to extract the submission checklist</p>
            <p className="text-xs text-blue-600 mt-0.5">The AI will parse your uploaded documents and extract every required item Saba needs to gather from Bernedette.</p>
          </div>
          <button onClick={handleReviewDocs} disabled={actionLoading === 'review'} className="btn-primary text-xs shrink-0">
            {actionLoading === 'review' ? <><Loader2 className="w-3 h-3 animate-spin" />Reviewing…</> : <><Eye className="w-3 h-3" />Run AI Review</>}
          </button>
        </div>
      ) : null}

      {/* ── Opportunity Details (collapsible) ── */}
      <CollapsibleCard title="Opportunity Details & AI Analysis">
        <div className="space-y-6">
          <div>
            <h3 className="text-xs font-bold text-blue-700 uppercase tracking-wider mb-3">Opportunity Details</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Agency / Organization" value={opp.agency_name} />
              <Field label="Solicitation Number" value={opp.solicitation_number} />
              <Field label="Contract Type" value={opp.contract_type} />
              <Field label="Estimated Value" value={opp.estimated_value} />
              <Field label="Submission Due Date" value={opp.due_date ? new Date(opp.due_date).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }) : null} />
              <Field label="Questions Deadline" value={opp.questions_deadline} />
              <Field label="Pre-Bid / Conference Date" value={opp.pre_bid_date ? new Date(opp.pre_bid_date).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }) : null} />
              <Field label="Submission Method" value={opp.submission_method} />
              <Field label="Contact Person" value={opp.contact_person} />
              <Field label="Contact Email" value={opp.contact_email} />
              <Field label="Website / Portal" value={opp.website_link} link={!!opp.website_link} />
              <Field label="EMMA Link" value={opp.emma_link} link={opp.emma_link?.startsWith('http')} />
            </div>
          </div>
          <hr className="border-gray-100" />
          <div>
            <h3 className="text-xs font-bold text-blue-700 uppercase tracking-wider mb-3">AI Analysis</h3>
            <div className="grid grid-cols-1 gap-4">
              <Field label="Opportunity Summary" value={opp.opportunity_summary} />
              <Field label="Required Services" value={opp.required_services} />
              <Field label="FaithForge Alignment" value={opp.faithforge_alignment} />
              <Field label="Recommended Action" value={opp.recommended_action} />
              <Field label="Risk / Concerns" value={opp.risk_concerns} />
              <Field label="Why This Score" value={opp.classification_reasoning} />
              <Field label="Score Breakdown" value={opp.score_breakdown} />
            </div>
          </div>
          <hr className="border-gray-100" />
          <div>
            <h3 className="text-xs font-bold text-blue-700 uppercase tracking-wider mb-3">Compliance & Submission Requirements</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Eligibility Requirements" value={opp.eligibility_requirements} />
              <Field label="Required Certifications" value={opp.certifications_required} />
              <Field label="Required Qualifications" value={opp.required_qualifications} />
              <Field label="Insurance Requirements" value={opp.insurance_requirements} />
              <Field label="Pricing / Budget Format" value={opp.pricing_requirements} />
              <Field label="Proposal Format" value={opp.proposal_format} />
              <div className="sm:col-span-2"><Field label="Evaluation Criteria" value={opp.evaluation_criteria} /></div>
              <div className="sm:col-span-2"><Field label="Required Forms" value={opp.required_forms} /></div>
              <div className="sm:col-span-2"><Field label="Required Attachments" value={opp.required_attachments} /></div>
              <div className="sm:col-span-2"><Field label="Compliance Requirements" value={opp.compliance_requirements} /></div>
              <div className="sm:col-span-2"><Field label="Disqualifying Requirements" value={opp.disqualifying_requirements} /></div>
            </div>
          </div>
          <hr className="border-gray-100" />
          <div>
            <h3 className="text-xs font-bold text-blue-700 uppercase tracking-wider mb-3">Email Source</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Subject" value={opp.email_subject} />
              <Field label="From" value={opp.email_from} />
              <Field label="Date Received" value={opp.email_date ? new Date(opp.email_date).toLocaleString() : null} />
              <Field label="Message ID" value={opp.email_id} mono />
              <div className="sm:col-span-2"><Field label="Email Preview" value={opp.email_body_preview} /></div>
            </div>
          </div>
        </div>
      </CollapsibleCard>

      {/* Go/No-Go */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-900 text-sm">Go / No-Go Assessment</h3>
          <button onClick={handleGoNoGo} disabled={gonogoLoading} className="btn-secondary text-xs">
            {gonogoLoading ? <><Loader2 className="w-3 h-3 animate-spin" /> Running…</>
              : gonogo ? <><RefreshCw className="w-3 h-3" /> Re-assess</>
              : <><HelpCircle className="w-3 h-3" /> Run Assessment</>}
          </button>
        </div>
        {!gonogo && !gonogoLoading && <p className="text-sm text-gray-400">Run the AI assessment to get a structured Bid / No-Bid recommendation.</p>}
        {gonogo && <GoNoGoPanel result={gonogo} />}
      </div>

      {/* ── STEP 4: Build Proposal ── */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${hasPacket ? 'bg-emerald-500 text-white' : checklistBlocking ? 'bg-gray-200 text-gray-400' : 'bg-blue-600 text-white'}`}>
              {hasPacket ? <CheckCircle className="w-3.5 h-3.5" /> : checklistBlocking ? <Lock className="w-3 h-3" /> : '4'}
            </div>
            <h3 className="font-semibold text-gray-900 text-sm">Step 4 — Build Proposal Packet</h3>
          </div>
          <div className="flex items-center gap-2">
            {hasPacket && (
              <>
                <button onClick={() => setShowPacket(s => !s)} className="btn-secondary text-xs">
                  <Eye className="w-3 h-3" />{showPacket ? 'Hide' : 'View'} Packet
                </button>
                <button onClick={() => handleExportPacket('docx')} disabled={actionLoading === 'export-docx'} className="btn-secondary text-xs">
                  {actionLoading === 'export-docx' ? <><Loader2 className="w-3 h-3 animate-spin" />Exporting…</> : <><Download className="w-3 h-3" />Word</>}
                </button>
                <button onClick={() => handleExportPacket('pdf')} disabled={actionLoading === 'export-pdf'} className="btn-secondary text-xs">
                  {actionLoading === 'export-pdf' ? <><Loader2 className="w-3 h-3 animate-spin" />Exporting…</> : <><Download className="w-3 h-3" />PDF</>}
                </button>
                <button onClick={handleEmailPacket} disabled={actionLoading === 'email'} className="btn-success text-xs">
                  {actionLoading === 'email' ? <><Loader2 className="w-3 h-3 animate-spin" />Sending…</> : <><Mail className="w-3 h-3" />Email Packet</>}
                </button>
              </>
            )}
            <button
              onClick={handleBuildPacket}
              disabled={actionLoading === 'packet' || checklistBlocking}
              className={`text-xs px-4 py-2 rounded-lg font-medium flex items-center gap-1.5 transition-colors ${
                checklistBlocking ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                : 'btn-primary'
              }`}
            >
              {actionLoading === 'packet'
                ? <><Loader2 className="w-3 h-3 animate-spin" />Building…</>
                : checklistBlocking
                ? <><Lock className="w-3 h-3" />Checklist Incomplete</>
                : <><Package className="w-3 h-3" />{hasPacket ? 'Rebuild' : 'Build'} Packet</>
              }
            </button>
          </div>
        </div>

        {/* Checklist gate warning */}
        {checklistBlocking && (
          <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-xl">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-amber-800">
                  {checklistProgress.total - checklistProgress.done} of {checklistProgress.total} documents still needed
                </p>
                <p className="text-xs text-amber-600 mt-1">
                  Contact Bernedette and upload the missing documents before building the proposal. The proposal will be incomplete without them.
                </p>
                <div className="flex items-center gap-3 mt-3">
                  <a href={buildEmailBernedetteLink()} className="flex items-center gap-1.5 text-xs font-semibold text-blue-700 hover:text-blue-900">
                    <Send className="w-3 h-3" />Email Bernedette the list
                  </a>
                  <span className="text-gray-300">·</span>
                  <button onClick={() => setBypassChecklist(true)} className="text-xs text-gray-400 hover:text-gray-600">
                    Build anyway (not recommended)
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Custom instructions */}
        {(!checklistBlocking || hasPacket) && (
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Custom Instructions <span className="text-gray-400 font-normal">(optional — specific focus, sections to emphasize, etc.)</span>
            </label>
            <textarea
              value={customInstructions}
              onChange={e => setCustomInstructions(e.target.value)}
              placeholder="e.g. Focus heavily on change management. Emphasize Bernedette's PgMP certification. Include a teaming strategy."
              rows={3}
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-800 placeholder-gray-400"
            />
          </div>
        )}

        {/* Complete an Existing Draft */}
        {(!checklistBlocking || hasPacket) && (
          <div className="mb-4 p-4 bg-indigo-50 border border-indigo-200 rounded-xl space-y-3">
            <div>
              <p className="text-sm font-semibold text-indigo-900">Have an existing draft? Complete it instead</p>
              <p className="text-xs text-indigo-600 mt-0.5">AI compares your draft against the RFP and FaithForge's knowledge base, fills the gaps, and produces a submission-ready version.</p>
            </div>

            <div className="flex items-center gap-4 text-xs text-gray-700 flex-wrap">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input type="radio" checked={draftMode === 'upload'} onChange={() => setDraftMode('upload')} />
                Upload from my computer
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input type="radio" checked={draftMode === 'document'} onChange={() => setDraftMode('document')} />
                Pick an already-uploaded document
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input type="radio" checked={draftMode === 'paste'} onChange={() => setDraftMode('paste')} />
                Paste draft text
              </label>
            </div>

            {draftMode === 'upload' && (
              <div className="space-y-2">
                <input
                  ref={draftFileInputRef}
                  type="file"
                  className="hidden"
                  accept=".pdf,.docx,.doc,.xlsx,.xls,.zip"
                  onChange={handleDraftFileSelected}
                />
                <button
                  type="button"
                  onClick={() => draftFileInputRef.current?.click()}
                  disabled={uploadingDraft}
                  className="w-full border-2 border-dashed border-indigo-300 rounded-xl p-5 text-center hover:border-indigo-400 hover:bg-indigo-100/40 transition-colors"
                >
                  {uploadingDraft ? (
                    <span className="flex items-center justify-center gap-2 text-sm text-indigo-700"><Loader2 className="w-4 h-4 animate-spin" />Uploading…</span>
                  ) : draftDocumentId ? (
                    <span className="flex items-center justify-center gap-2 text-sm text-emerald-700">
                      <CheckCircle className="w-4 h-4" />
                      {opp.documents?.find(d => String(d.id) === String(draftDocumentId))?.original_filename || 'File uploaded'} — click to replace
                    </span>
                  ) : (
                    <span className="text-sm text-indigo-700">Click to browse your computer for the draft proposal (PDF, Word, Excel)</span>
                  )}
                </button>
                {draftUploadError && (
                  <p className="text-xs text-red-600">{draftUploadError}</p>
                )}
              </div>
            )}

            {draftMode === 'document' && (
              hasDocuments ? (
                <select value={draftDocumentId} onChange={e => setDraftDocumentId(e.target.value)} className="input text-sm">
                  <option value="">Select a document…</option>
                  {opp.documents.map(d => <option key={d.id} value={d.id}>{d.original_filename}</option>)}
                </select>
              ) : (
                <p className="text-xs text-gray-400">No documents uploaded yet — use "Upload from my computer" above, or paste its text instead.</p>
              )
            )}

            {draftMode === 'paste' && (
              <textarea
                value={draftText}
                onChange={e => setDraftText(e.target.value)}
                rows={4}
                placeholder="Paste the existing draft proposal text here…"
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 text-gray-800 placeholder-gray-400"
              />
            )}

            <button
              onClick={handleCompleteDraft}
              disabled={actionLoading === 'complete-draft' || uploadingDraft || (draftMode === 'paste' ? !draftText.trim() : !draftDocumentId)}
              className="btn-primary text-xs px-4 py-2"
            >
              {actionLoading === 'complete-draft'
                ? <><Loader2 className="w-3 h-3 animate-spin" />Analyzing & Completing…</>
                : <><ClipboardCheck className="w-3 h-3" />Analyze & Complete Draft</>}
            </button>

            {draftAnalysis && (
              <div className="mt-2 p-3 bg-white border border-indigo-100 rounded-lg space-y-2.5 text-xs">
                {draftAnalysis.strengths?.length > 0 && (
                  <div>
                    <p className="font-semibold text-emerald-700 mb-1">Strengths</p>
                    <ul className="space-y-0.5">{draftAnalysis.strengths.map((s, i) => <li key={i} className="text-gray-700">• {s}</li>)}</ul>
                  </div>
                )}
                {draftAnalysis.gaps?.length > 0 && (
                  <div>
                    <p className="font-semibold text-amber-700 mb-1">Gaps Found & Filled</p>
                    <ul className="space-y-0.5">{draftAnalysis.gaps.map((s, i) => <li key={i} className="text-gray-700">• {s}</li>)}</ul>
                  </div>
                )}
                {draftAnalysis.missing_sections?.length > 0 && (
                  <div>
                    <p className="font-semibold text-amber-700 mb-1">Missing Sections Added</p>
                    <ul className="space-y-0.5">{draftAnalysis.missing_sections.map((s, i) => <li key={i} className="text-gray-700">• {s}</li>)}</ul>
                  </div>
                )}
                {draftAnalysis.compliance_risks?.length > 0 && (
                  <div>
                    <p className="font-semibold text-red-700 mb-1">Compliance Risks</p>
                    <ul className="space-y-0.5">{draftAnalysis.compliance_risks.map((s, i) => <li key={i} className="text-gray-700">• {s}</li>)}</ul>
                  </div>
                )}
                {draftAnalysis.recommendations?.length > 0 && (
                  <div>
                    <p className="font-semibold text-blue-700 mb-1">Recommendations Applied</p>
                    <ul className="space-y-0.5">{draftAnalysis.recommendations.map((s, i) => <li key={i} className="text-gray-700">• {s}</li>)}</ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {!hasPacket && !actionLoading && !checklistBlocking && (
          <p className="text-sm text-gray-500">Generate a full proposal-ready packet — executive summary, scope of work, team background, and detailed budget.</p>
        )}

        {actionLoading === 'packet' && (
          <div className="flex items-center gap-3 p-4 bg-blue-50 rounded-lg">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
            <div>
              <p className="text-sm font-medium text-blue-900">Building proposal with AI…</p>
              <p className="text-xs text-blue-600 mt-0.5">This may take 1–2 minutes. Running 6-stage generation.</p>
            </div>
          </div>
        )}

        {showPacket && packet?.html_content && (
          <>
            <div className="mt-4 p-5 bg-white border border-gray-200 rounded-xl prose prose-sm max-w-none overflow-auto" style={{ maxHeight: '600px' }}
              dangerouslySetInnerHTML={{ __html: packet.html_content }} />

            <form onSubmit={handleRevise} className="mt-3 p-4 bg-gray-50 border border-gray-200 rounded-xl space-y-2">
              <label className="block text-xs font-semibold text-gray-600">
                Propose a change <span className="font-normal text-gray-400">(AI revises the full proposal and saves a new version)</span>
              </label>
              {lastRevision && (
                <p className="text-xs text-gray-400 italic">Last applied: "{lastRevision}"</p>
              )}
              <div className="flex items-start gap-2">
                <textarea
                  value={revisionInstruction}
                  onChange={e => setRevisionInstruction(e.target.value)}
                  placeholder="e.g. Lower the total budget by 10%. Add a one-paragraph risk-management section. Make the tone less formal."
                  rows={2}
                  disabled={revising}
                  className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-800 placeholder-gray-400 disabled:bg-gray-100"
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleRevise(e) } }}
                />
                <button type="submit" disabled={revising || !revisionInstruction.trim()} className="btn-primary text-xs px-4 py-2.5 shrink-0">
                  {revising ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />Revising…</> : <><Send className="w-3.5 h-3.5" />Apply</>}
                </button>
              </div>
            </form>
          </>
        )}

        {packet && (
          <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
            <CheckCircle className="w-3.5 h-3.5 text-green-500" />
            Packet built {new Date(packet.created_at).toLocaleString()}
            {packet.emailed && ` · Emailed ${packet.emailed_at ? new Date(packet.emailed_at).toLocaleString() : ''}`}
          </div>
        )}
      </div>

      <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800">
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
        <p><strong>Important:</strong> This packet is AI-generated for internal review only. Do not share externally without authorization. All bid/no-bid decisions require human review and approval.</p>
      </div>
    </div>
  )
}

function CollapsibleCard({ title, children }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
      >
        <span className="text-sm font-semibold text-gray-700">{title}</span>
        {open ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
      </button>
      {open && <div className="px-5 pb-5 space-y-6 border-t border-gray-100">{children}</div>}
    </div>
  )
}
