import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PenTool, Loader2, AlertCircle, Sparkles, ExternalLink } from 'lucide-react'
import { generateStandaloneProposal } from '../api'
import { SEGMENTS } from './Accounts'

const DEFAULT_FORM = {
  title: '',
  client_name: '',
  segment: '',
  required_services: '',
  estimated_value: '',
  period_of_performance: '',
  discovery_notes: '',
  custom_instructions: '',
}

export default function ProposalBuilder() {
  const navigate = useNavigate()
  const [form, setForm] = useState(DEFAULT_FORM)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const generate = async (e) => {
    e.preventDefault()
    if (!form.title.trim() || form.discovery_notes.trim().length < 10) return
    setLoading(true)
    setError(null)
    try {
      const result = await generateStandaloneProposal(form)
      navigate(`/opportunities/${result.opportunity_id}`)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Proposal Builder</h1>
        <p className="text-sm text-gray-400 mt-0.5">Paste discovery notes, call takeaways, or RFP text — AI generates a full FaithForge proposal packet</p>
      </div>

      <form onSubmit={generate} className="space-y-5">
        {/* Core info */}
        <div className="card p-5 space-y-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Opportunity Details</p>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-xs font-semibold text-gray-500 mb-1">Proposal Title *</label>
              <input
                value={form.title}
                onChange={set('title')}
                className="input"
                placeholder="e.g. Prince George's County PMO Retainer 2026"
                autoFocus
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Client / Agency Name</label>
              <input value={form.client_name} onChange={set('client_name')} className="input" placeholder="e.g. PG County DPIE" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Segment</label>
              <select value={form.segment} onChange={set('segment')} className="input">
                <option value="">Select…</option>
                {SEGMENTS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Estimated Value</label>
              <input value={form.estimated_value} onChange={set('estimated_value')} className="input" placeholder="e.g. $150K–$250K/yr" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Period of Performance</label>
              <input value={form.period_of_performance} onChange={set('period_of_performance')} className="input" placeholder="e.g. 12 months" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-semibold text-gray-500 mb-1">Required Services / Scope</label>
              <textarea
                value={form.required_services}
                onChange={set('required_services')}
                className="input min-h-16"
                rows={2}
                placeholder="e.g. PMO setup, governance framework, executive reporting cadence, change management"
              />
            </div>
          </div>
        </div>

        {/* Discovery notes */}
        <div className="card p-5 space-y-3">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Discovery Notes *</p>
            <p className="text-xs text-gray-400 mt-0.5">Paste RFP description, call notes, website text, email content, or any context about this opportunity</p>
          </div>
          <textarea
            value={form.discovery_notes}
            onChange={set('discovery_notes')}
            className="input min-h-48 font-mono text-xs"
            rows={12}
            placeholder={`Paste everything you know about this opportunity here:\n\n• What the client said in the intro call\n• RFP or SOW text copied from their website\n• Pain points they mentioned\n• Budget or timeline details\n• Key stakeholders\n• Any special requirements or compliance notes\n\nThe more context, the better the proposal.`}
          />
        </div>

        {/* Custom instructions */}
        <div className="card p-5 space-y-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Custom Instructions <span className="font-normal text-gray-400">(optional)</span></p>
          <textarea
            value={form.custom_instructions}
            onChange={set('custom_instructions')}
            className="input min-h-16"
            rows={3}
            placeholder="e.g. Emphasize the change management workstream. Include a Phase 0 mobilization period. Reference Bernedette's healthcare experience."
          />
        </div>

        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />{error}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600 shrink-0" />
            <div>
              <p className="text-sm font-medium text-blue-900">Building proposal with AI…</p>
              <p className="text-xs text-blue-600 mt-0.5">This takes 1–2 minutes. Running 6-stage generation: plan → executive summary → scope → background → budget.</p>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between">
          <p className="text-xs text-gray-400 flex items-center gap-1">
            <ExternalLink className="w-3 h-3" />
            Result opens in Opportunities — review, rebuild, or email from there
          </p>
          <button
            type="submit"
            disabled={loading || !form.title.trim() || form.discovery_notes.trim().length < 10}
            className="btn-primary text-sm py-2.5 px-8 flex items-center gap-2"
          >
            {loading
              ? <><Loader2 className="w-4 h-4 animate-spin" />Generating…</>
              : <><Sparkles className="w-4 h-4" />Generate Proposal</>
            }
          </button>
        </div>
      </form>
    </div>
  )
}
