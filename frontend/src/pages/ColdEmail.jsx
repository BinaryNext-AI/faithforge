import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  Mail, Sparkles, Loader2, Copy, CheckCheck, AlertCircle,
  ChevronLeft, Reply, Send, Pencil, Check, X, AlertTriangle,
} from 'lucide-react'
import {
  generateColdEmail, generateColdEmailFollowUp, getSettings,
  outreachGetEmails, outreachUpdateEmail, outreachApproveEmail, outreachUnapproveEmail, outreachSendOne,
} from '../api'
import { SEGMENTS } from './Accounts'

const DEFAULT_FORM = {
  company_name: '',
  segment: '',
  contact_name: '',
  contact_title: '',
  contact_email: '',
  pain_points: '',
  entry_offer: '',
}

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

export default function ColdEmail({ embedded = false }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [form, setForm] = useState(() => ({
    ...DEFAULT_FORM,
    company_name: searchParams.get('company') || '',
    segment: searchParams.get('segment') || '',
    contact_name: searchParams.get('contact_name') || '',
    contact_title: searchParams.get('contact_title') || '',
    contact_email: searchParams.get('contact_email') || '',
    pain_points: searchParams.get('pain_points') || '',
    entry_offer: searchParams.get('entry_offer') || '',
  }))
  const [loading, setLoading] = useState(false)
  const [followUpLoading, setFollowUpLoading] = useState(false)
  const [error, setError] = useState(null)
  const [emails, setEmails] = useState([])
  const [accountId, setAccountId] = useState(searchParams.get('account_id') ? Number(searchParams.get('account_id')) : null)
  const [copied, setCopied] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState({ subject: '', body: '' })
  const [sendMode, setSendMode] = useState('dry_run')
  const [outreachFromEmail, setOutreachFromEmail] = useState('')

  const fromAccount = searchParams.get('account_id')

  useEffect(() => {
    getSettings().then(data => {
      const map = {}
      data.forEach(s => { map[s.key] = s.value })
      setSendMode(map.OUTREACH_SEND_MODE || 'dry_run')
      setOutreachFromEmail(map.OUTREACH_FROM_EMAIL || '')
    }).catch(() => {})
  }, [])

  // If arriving from an Account with existing drafts, load its history
  useEffect(() => {
    if (accountId) {
      outreachGetEmails({ account_id: accountId }).then(setEmails).catch(() => {})
    }
  }, [accountId])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const generate = async (e) => {
    e.preventDefault()
    if (!form.company_name.trim() || !form.contact_email.trim()) return
    setLoading(true)
    setError(null)
    try {
      const row = await generateColdEmail({ ...form })
      setAccountId(row.account_id)
      setEmails(prev => [row, ...prev])
      // Persist the account into the URL so a browser refresh reloads these
      // saved drafts instead of showing a blank page.
      if (row.account_id) {
        const next = new URLSearchParams(searchParams)
        next.set('account_id', String(row.account_id))
        setSearchParams(next, { replace: true })
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const generateFollowUp = async () => {
    if (!accountId) return
    setFollowUpLoading(true)
    setError(null)
    try {
      const row = await generateColdEmailFollowUp(accountId)
      setEmails(prev => [row, ...prev])
    } catch (err) {
      setError(err.message)
    } finally {
      setFollowUpLoading(false)
    }
  }

  const copy = async (text, key) => {
    await navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
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

  const sendOne = async (email) => {
    if (sendMode === 'live') {
      const confirmed = window.confirm(
        `Send a REAL email to ${form.contact_email} from ${outreachFromEmail}? This cannot be undone.`
      )
      if (!confirmed) return
    }
    try {
      await outreachSendOne(email.id)
      const refreshed = await outreachGetEmails({ account_id: accountId })
      setEmails(refreshed)
    } catch (err) {
      setError(err.message)
    }
  }

  const hasAnyDraft = emails.length > 0

  return (
    <div className="space-y-5 max-w-6xl">
      {/* Header */}
      {!embedded && (
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Cold Email Generator</h1>
            <p className="text-sm text-gray-400 mt-0.5">AI-drafted outreach — specific, executive-level, no fluff</p>
          </div>
          {fromAccount && (
            <button
              onClick={() => navigate(`/accounts/${fromAccount}`)}
              className="shrink-0 flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900"
            >
              <ChevronLeft className="w-4 h-4" />Back to Account
            </button>
          )}
        </div>
      )}
      {embedded && fromAccount && (
        <button
          onClick={() => navigate(`/accounts/${fromAccount}`)}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900"
        >
          <ChevronLeft className="w-4 h-4" />Back to Account
        </button>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-5 items-start">
        {/* Form */}
        <form onSubmit={generate} className="card p-5 space-y-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Prospect Details</p>

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Company Name *</label>
            <input
              value={form.company_name}
              onChange={set('company_name')}
              className="input"
              placeholder="e.g. Maryland Dept of Transportation"
              autoFocus={!form.company_name}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Segment</label>
            <select value={form.segment} onChange={set('segment')} className="input">
              <option value="">Select segment…</option>
              {SEGMENTS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Contact Name</label>
              <input value={form.contact_name} onChange={set('contact_name')} className="input" placeholder="Jane Smith" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Contact Title</label>
              <input value={form.contact_title} onChange={set('contact_title')} className="input" placeholder="Chief of Staff" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Contact Email *</label>
            <input value={form.contact_email} onChange={set('contact_email')} className="input" type="email" placeholder="jane@company.com" />
            <p className="text-xs text-gray-400 mt-1">Required — this is who the draft gets saved and sent to.</p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Known Pain Points</label>
            <textarea
              value={form.pain_points}
              onChange={set('pain_points')}
              className="input min-h-20"
              rows={3}
              placeholder="e.g. Stalled IT modernization, no PMO in place, missed grant deliverables last quarter…"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Entry Offer</label>
            <textarea
              value={form.entry_offer}
              onChange={set('entry_offer')}
              className="input min-h-16"
              rows={2}
              placeholder="e.g. PMO Diagnostic — 2-week targeted audit of the stalled initiative"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />{error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !form.company_name.trim() || !form.contact_email.trim()}
            className="w-full btn-primary text-sm py-2.5 flex items-center justify-center gap-2"
          >
            {loading
              ? <><Loader2 className="w-4 h-4 animate-spin" />Generating…</>
              : <><Sparkles className="w-4 h-4" />Generate Email</>
            }
          </button>

          {hasAnyDraft && (
            <button
              type="button"
              onClick={generateFollowUp}
              disabled={followUpLoading}
              className="w-full btn-secondary text-sm py-2.5 flex items-center justify-center gap-2"
            >
              {followUpLoading
                ? <><Loader2 className="w-4 h-4 animate-spin" />Generating…</>
                : <><Reply className="w-4 h-4" />Generate Follow-up</>
              }
            </button>
          )}
        </form>

        {/* Output */}
        <div className="space-y-3">
          {sendMode === 'dry_run' && hasAnyDraft && (
            <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span><strong>Dry-run mode:</strong> Send routes to a test address, not the real contact. Switch to live in Settings when ready.</span>
            </div>
          )}

          {!hasAnyDraft ? (
            <div className="card p-14 text-center text-gray-400">
              <Mail className="w-10 h-10 mx-auto mb-3 opacity-25" />
              <p className="text-sm">Fill in the prospect details (including their email) and click Generate.</p>
              <p className="text-xs mt-1 text-gray-300">One email at a time — draft, review, send, then generate a follow-up only if needed.</p>
            </div>
          ) : (
            emails.map(email => (
              <div key={email.id} className="card p-5 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {email.is_follow_up && (
                      <span className="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-[10px] font-semibold">FOLLOW-UP</span>
                    )}
                    <StatusBadge status={email.status} />
                  </div>
                  <div className="flex items-center gap-2">
                    {['draft', 'approved'].includes(email.status) && (
                      <button onClick={() => startEdit(email)} className="text-gray-400 hover:text-gray-700"><Pencil className="w-3.5 h-3.5" /></button>
                    )}
                    <button
                      onClick={() => copy(`Subject: ${email.subject}\n\n${email.body}`, email.id)}
                      className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-700"
                    >
                      {copied === email.id ? <CheckCheck className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

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
                      className="input text-sm min-h-40"
                      rows={8}
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
                    <pre className="text-sm text-gray-600 whitespace-pre-wrap font-sans leading-relaxed">{email.body}</pre>
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
                      onClick={() => sendOne(email)}
                      className="text-xs px-3 py-1.5 rounded-lg font-semibold bg-emerald-600 text-white flex items-center gap-1"
                    >
                      <Send className="w-3.5 h-3.5" />Send{sendMode === 'dry_run' ? ' (Dry Run)' : ''}
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
