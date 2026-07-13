import { useState, useEffect, useCallback } from 'react'
import {
  ArrowLeft, Loader2, AlertCircle, Trash2, Save, Sparkles, Bell, CheckCircle, Mail,
} from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { getAccount, updateAccount, updateAccountStage, deleteAccount, scoreAccount } from '../api'
import { STAGES, SEGMENTS, StageBadge, PriorityPill } from './Accounts'

// datetime-local wants "YYYY-MM-DDTHH:mm"; the API returns ISO strings.
const toLocalInput = (iso) => (iso ? new Date(iso).toISOString().slice(0, 16) : '')

export default function AccountDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [acc, setAcc] = useState(null)
  const [form, setForm] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null)
  const [toast, setToast] = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const load = useCallback(async () => {
    try {
      const data = await getAccount(id)
      setAcc(data)
      setForm({
        company_name: data.company_name || '',
        segment: data.segment || '',
        website: data.website || '',
        location: data.location || '',
        contact_name: data.contact_name || '',
        contact_title: data.contact_title || '',
        contact_email: data.contact_email || '',
        contact_phone: data.contact_phone || '',
        next_action: data.next_action || '',
        next_action_date: toLocalInput(data.next_action_date),
        awaiting_reply: !!data.awaiting_reply,
        pain_points: data.pain_points || '',
        entry_offer: data.entry_offer || '',
        notes: data.notes || '',
        source: data.source || '',
      })
      setError(null)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [id])

  useEffect(() => { load() }, [load])

  const set = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm({ ...form, [k]: v })
  }

  const save = async () => {
    setBusy('save')
    try {
      const payload = { ...form }
      payload.next_action_date = form.next_action_date ? new Date(form.next_action_date).toISOString() : null
      const updated = await updateAccount(id, payload)
      setAcc(updated)
      showToast('Account saved')
    } catch (e) { showToast(e.message, 'error') }
    finally { setBusy(null) }
  }

  const changeStage = async (stage) => {
    setBusy('stage')
    try {
      const updated = await updateAccountStage(id, stage)
      setAcc(updated)
      setForm(f => ({ ...f, awaiting_reply: !!updated.awaiting_reply }))
    } catch (e) { showToast(e.message, 'error') }
    finally { setBusy(null) }
  }

  const rescore = async () => {
    setBusy('score')
    try {
      const updated = await scoreAccount(id)
      setAcc(updated)
      setForm(f => ({
        ...f,
        pain_points: f.pain_points || updated.pain_points || '',
        entry_offer: f.entry_offer || updated.entry_offer || '',
      }))
      showToast('AI priority score updated')
    } catch (e) { showToast(e.message, 'error') }
    finally { setBusy(null) }
  }

  const remove = async () => {
    if (!window.confirm('Delete this account? This cannot be undone.')) return
    setBusy('delete')
    try {
      await deleteAccount(id)
      navigate('/accounts')
    } catch (e) { showToast(e.message, 'error'); setBusy(null) }
  }

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-blue-600" /></div>
  if (error) return (
    <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
      <AlertCircle className="w-4 h-4 shrink-0" />{error}
    </div>
  )
  if (!acc) return null

  return (
    <div className="space-y-5 max-w-4xl">
      {/* Back + header */}
      <button onClick={() => navigate('/accounts')} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900">
        <ArrowLeft className="w-4 h-4" />Back to Accounts
      </button>

      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-gray-900">{acc.company_name}</h1>
            <StageBadge stage={acc.stage} />
            {acc.awaiting_reply && (
              <span className="flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-700 text-xs rounded-full font-semibold">
                <Bell className="w-3 h-3" />Awaiting reply
              </span>
            )}
          </div>
          {acc.segment && <p className="text-sm text-gray-400 mt-1">{acc.segment}</p>}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={() => {
              const p = new URLSearchParams({
                tab: 'single',
                account_id: id,
                company: acc.company_name || '',
                segment: acc.segment || '',
                contact_name: acc.contact_name || '',
                contact_title: acc.contact_title || '',
                pain_points: acc.pain_points || '',
                entry_offer: acc.entry_offer || '',
              })
              navigate(`/outreach?${p.toString()}`)
            }}
            className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            <Mail className="w-4 h-4" />Draft Email
          </button>
          <button onClick={remove} disabled={busy === 'delete'}
            className="flex items-center gap-1.5 text-sm text-red-500 hover:text-red-700">
            {busy === 'delete' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}Delete
          </button>
        </div>
      </div>

      {/* Pipeline stage control */}
      <div className="card p-5">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Pipeline Stage</p>
        <div className="flex flex-wrap gap-2">
          {STAGES.map(s => (
            <button key={s} onClick={() => changeStage(s)} disabled={busy === 'stage'}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                acc.stage === s ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Priority */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">AI Priority Score</p>
          <button onClick={rescore} disabled={busy === 'score'}
            className="flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-800">
            {busy === 'score' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            {acc.priority_score == null ? 'Score with AI' : 'Re-score'}
          </button>
        </div>
        <div className="flex items-start gap-3">
          <PriorityPill score={acc.priority_score} />
          <p className="text-sm text-gray-600 flex-1">{acc.priority_reason || 'Not yet scored. Click "Score with AI" to rank this account.'}</p>
        </div>
      </div>

      {/* Editable details */}
      <div className="card p-5 space-y-4">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Company & Contact</p>
        <div className="grid grid-cols-2 gap-3">
          <Labeled label="Company Name"><input value={form.company_name} onChange={set('company_name')} className="input" /></Labeled>
          <Labeled label="Segment">
            <select value={form.segment} onChange={set('segment')} className="input">
              <option value="">Select…</option>
              {SEGMENTS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </Labeled>
          <Labeled label="Website"><input value={form.website} onChange={set('website')} className="input" /></Labeled>
          <Labeled label="Location"><input value={form.location} onChange={set('location')} className="input" /></Labeled>
          <Labeled label="Contact Name"><input value={form.contact_name} onChange={set('contact_name')} className="input" /></Labeled>
          <Labeled label="Contact Title"><input value={form.contact_title} onChange={set('contact_title')} className="input" /></Labeled>
          <Labeled label="Contact Email"><input value={form.contact_email} onChange={set('contact_email')} className="input" type="email" /></Labeled>
          <Labeled label="Contact Phone"><input value={form.contact_phone} onChange={set('contact_phone')} className="input" /></Labeled>
        </div>
      </div>

      {/* Next action */}
      <div className="card p-5 space-y-4">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Next Action</p>
        <div className="grid grid-cols-[1fr_200px] gap-3">
          <Labeled label="Next Action"><input value={form.next_action} onChange={set('next_action')} className="input" placeholder="e.g. Send intro email" /></Labeled>
          <Labeled label="Due Date"><input value={form.next_action_date} onChange={set('next_action_date')} className="input" type="datetime-local" /></Labeled>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={form.awaiting_reply} onChange={set('awaiting_reply')} className="rounded border-gray-300" />
          Awaiting reply from this contact
        </label>
      </div>

      {/* Outreach context */}
      <div className="card p-5 space-y-4">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Outreach Context</p>
        <Labeled label="Pain Points"><textarea value={form.pain_points} onChange={set('pain_points')} className="input min-h-16" rows={2} /></Labeled>
        <Labeled label="Entry Offer"><textarea value={form.entry_offer} onChange={set('entry_offer')} className="input min-h-16" rows={2} /></Labeled>
        <Labeled label="Notes"><textarea value={form.notes} onChange={set('notes')} className="input min-h-20" rows={3} /></Labeled>
      </div>

      {/* Save */}
      <div className="flex justify-end">
        <button onClick={save} disabled={busy === 'save'} className="btn-primary text-sm py-2 px-6 flex items-center gap-2">
          {busy === 'save' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}Save Changes
        </button>
      </div>

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-6 right-6 flex items-center gap-2 px-4 py-3 rounded-xl shadow-lg text-sm text-white ${toast.type === 'error' ? 'bg-red-600' : 'bg-green-600'}`}>
          {toast.type === 'error' ? <AlertCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}{toast.msg}
        </div>
      )}
    </div>
  )
}

function Labeled({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-500 mb-1">{label}</label>
      {children}
    </div>
  )
}
