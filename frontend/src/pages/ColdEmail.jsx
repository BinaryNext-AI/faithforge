import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  Mail, Sparkles, Loader2, Copy, CheckCheck, AlertCircle,
  ChevronLeft, ChevronRight, CalendarDays,
} from 'lucide-react'
import { generateColdEmail } from '../api'
import { SEGMENTS } from './Accounts'

const DEFAULT_FORM = {
  company_name: '',
  segment: '',
  contact_name: '',
  contact_title: '',
  pain_points: '',
  entry_offer: '',
  sequence_length: 3,
}

export default function ColdEmail() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [form, setForm] = useState(() => ({
    ...DEFAULT_FORM,
    company_name: searchParams.get('company') || '',
    segment: searchParams.get('segment') || '',
    contact_name: searchParams.get('contact_name') || '',
    contact_title: searchParams.get('contact_title') || '',
    pain_points: searchParams.get('pain_points') || '',
    entry_offer: searchParams.get('entry_offer') || '',
  }))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [emails, setEmails] = useState([])
  const [activeTab, setActiveTab] = useState(0)
  const [copied, setCopied] = useState(null)

  const fromAccount = searchParams.get('account_id')

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const generate = async (e) => {
    e.preventDefault()
    if (!form.company_name.trim()) return
    setLoading(true)
    setError(null)
    setEmails([])
    try {
      const result = await generateColdEmail({ ...form })
      setEmails(result.emails || [])
      setActiveTab(0)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const copy = async (text, key) => {
    await navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  const copyAll = () => {
    const all = emails.map(em =>
      `=== Email ${em.step} (Day ${em.send_day}) — ${em.purpose} ===\nSubject: ${em.subject}\n\n${em.body}`
    ).join('\n\n' + '─'.repeat(50) + '\n\n')
    copy(all, 'all')
  }

  const active = emails[activeTab]

  return (
    <div className="space-y-5 max-w-6xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Cold Email Generator</h1>
          <p className="text-sm text-gray-400 mt-0.5">AI-drafted outreach sequences — specific, executive-level, no fluff</p>
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

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-2">Emails in Sequence</label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map(n => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setForm(f => ({ ...f, sequence_length: n }))}
                  className={`w-10 h-10 rounded-lg text-sm font-semibold transition-colors ${
                    form.sequence_length === n
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />{error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !form.company_name.trim()}
            className="w-full btn-primary text-sm py-2.5 flex items-center justify-center gap-2"
          >
            {loading
              ? <><Loader2 className="w-4 h-4 animate-spin" />Generating…</>
              : <><Sparkles className="w-4 h-4" />Generate Sequence</>
            }
          </button>
        </form>

        {/* Output */}
        <div className="space-y-3">
          {emails.length === 0 ? (
            <div className="card p-14 text-center text-gray-400">
              <Mail className="w-10 h-10 mx-auto mb-3 opacity-25" />
              <p className="text-sm">Fill in the prospect details and click Generate.</p>
              <p className="text-xs mt-1 text-gray-300">AI writes sharp, executive-level outreach — not templates.</p>
            </div>
          ) : (
            <>
              {/* Tab bar + Copy All */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex gap-1.5 flex-wrap">
                  {emails.map((em, i) => (
                    <button
                      key={i}
                      onClick={() => setActiveTab(i)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                        activeTab === i
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      Email {em.step}
                    </button>
                  ))}
                </div>
                <button
                  onClick={copyAll}
                  className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-800 px-3 py-1.5 rounded-lg border border-gray-200 hover:border-gray-300 transition-colors"
                >
                  {copied === 'all' ? <CheckCheck className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied === 'all' ? 'Copied!' : 'Copy All'}
                </button>
              </div>

              {active && (
                <div className="card p-5 space-y-4">
                  {/* Meta */}
                  <div className="flex items-center gap-3 text-xs text-gray-400">
                    <span className="flex items-center gap-1">
                      <CalendarDays className="w-3.5 h-3.5" />
                      Send day {active.send_day}
                    </span>
                    <span className="text-gray-300">·</span>
                    <span>{active.purpose}</span>
                  </div>

                  {/* Subject */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Subject Line</label>
                      <button
                        onClick={() => copy(active.subject, `subject-${active.step}`)}
                        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-700"
                      >
                        {copied === `subject-${active.step}` ? <CheckCheck className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                        {copied === `subject-${active.step}` ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <div className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-800">
                      {active.subject}
                    </div>
                  </div>

                  {/* Body */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Email Body</label>
                      <button
                        onClick={() => copy(active.body, `body-${active.step}`)}
                        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-700"
                      >
                        {copied === `body-${active.step}` ? <CheckCheck className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                        {copied === `body-${active.step}` ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <pre className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 text-sm text-gray-800 whitespace-pre-wrap font-sans leading-relaxed min-h-48">
                      {active.body}
                    </pre>
                  </div>

                  {/* Nav arrows */}
                  <div className="flex justify-between pt-1">
                    <button
                      onClick={() => setActiveTab(t => Math.max(0, t - 1))}
                      disabled={activeTab === 0}
                      className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-700 disabled:opacity-30"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />Previous
                    </button>
                    <button
                      onClick={() => setActiveTab(t => Math.min(emails.length - 1, t + 1))}
                      disabled={activeTab === emails.length - 1}
                      className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-700 disabled:opacity-30"
                    >
                      Next<ChevronRight className="w-3.5 h-3.5" />
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
