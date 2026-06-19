import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft, Loader2, AlertCircle, FileText, Trash2, Eye,
  Package, Mail, ExternalLink, CheckCircle,
  AlertTriangle, RefreshCw
} from 'lucide-react'
import {
  getOpportunity, updateStatus, deleteOpportunity,
  uploadDocument, deleteDocument, reviewDocuments,
  buildPacket, getPacket, emailPacket
} from '../api'
import StatusBadge from '../components/StatusBadge'
import FileUpload from '../components/FileUpload'

const VALID_STATUSES = [
  'New', 'Under Review', 'Relevant', 'Possibly Relevant', 'Not Relevant',
  'EMMA Documents Needed', 'Documents Uploaded', 'Packet Building',
  'Packet Ready', 'Reviewed by User', 'Approved to Pursue', 'Declined',
]

function Field({ label, value, mono = false, link = false }) {
  if (!value) return null
  return (
    <div>
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      {link ? (
        <a href={value} target="_blank" rel="noopener noreferrer"
          className="text-sm text-blue-600 hover:underline flex items-center gap-1">
          {value} <ExternalLink className="w-3 h-3" />
        </a>
      ) : (
        <p className={`text-sm text-gray-900 whitespace-pre-wrap ${mono ? 'font-mono' : ''}`}>{value}</p>
      )}
    </div>
  )
}


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

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const load = useCallback(async () => {
    try {
      const data = await getOpportunity(id)
      setOpp(data)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [id])

  const loadPacket = useCallback(async () => {
    try {
      const p = await getPacket(id)
      setPacket(p)
    } catch {}
  }, [id])

  useEffect(() => { load() }, [load])
  useEffect(() => { if (opp?.status === 'Packet Ready' || opp?.status === 'Reviewed by User') loadPacket() }, [opp, loadPacket])

  const handleStatusChange = async (newStatus) => {
    setActionLoading('status')
    try {
      const updated = await updateStatus(id, newStatus)
      setOpp(updated)
      showToast(`Status updated to "${newStatus}"`)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Delete this opportunity and all related documents? This cannot be undone.')) return
    setActionLoading('delete')
    try {
      await deleteOpportunity(id)
      navigate('/opportunities')
    } catch (e) {
      showToast(e.message, 'error')
      setActionLoading(null)
    }
  }

  const handleDeleteDoc = async (docId) => {
    if (!confirm('Delete this document?')) return
    try {
      await deleteDocument(id, docId)
      load()
      showToast('Document deleted')
    } catch (e) {
      showToast(e.message, 'error')
    }
  }

  const handleReviewDocs = async () => {
    setActionLoading('review')
    try {
      const updated = await reviewDocuments(id)
      setOpp(updated)
      showToast('Documents reviewed and fields updated')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const handleBuildPacket = async () => {
    setActionLoading('packet')
    try {
      const p = await buildPacket(id, customInstructions)
      setPacket(p)
      const updated = await getOpportunity(id)
      setOpp(updated)
      setShowPacket(true)
      showToast('Packet built successfully!')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const handleEmailPacket = async () => {
    setActionLoading('email')
    try {
      const result = await emailPacket(id)
      showToast(`Packet emailed to ${result.to}`)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setActionLoading(null)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
    </div>
  )

  if (error) return (
    <div className="flex items-center gap-3 p-6 bg-red-50 rounded-xl text-red-700">
      <AlertCircle className="w-5 h-5" />
      <p>{error}</p>
    </div>
  )

  if (!opp) return null

  const hasPacket = !!packet || opp.status === 'Packet Ready' || opp.status === 'Reviewed by User'

  return (
    <div className="space-y-5">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium ${
          toast.type === 'error' ? 'bg-red-600 text-white' : 'bg-green-600 text-white'
        }`}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Link to="/opportunities" className="btn-secondary p-2 mt-0.5">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-gray-900 leading-tight">
              {opp.opportunity_title || opp.email_subject || 'Untitled Opportunity'}
            </h1>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <StatusBadge status={opp.status} />
              {opp.relevance_classification && (
                <StatusBadge status={opp.relevance_classification} type="classification" />
              )}
              {opp.relevance_score != null && (
                <span
                  className="text-xs text-gray-500 font-medium"
                  title={opp.score_breakdown || opp.classification_reasoning || ''}
                >
                  Score: {Math.round(opp.relevance_score)}/100
                </span>
              )}
              {opp.has_emma_link && (
                <span className="px-2 py-0.5 bg-orange-100 text-orange-700 text-xs rounded font-medium">EMMA Required</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={load} className="btn-secondary p-2" title="Refresh">
            <RefreshCw className="w-4 h-4" />
          </button>
          <button onClick={handleDelete} disabled={actionLoading === 'delete'} className="btn-danger">
            {actionLoading === 'delete' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
            Delete
          </button>
        </div>
      </div>

      {/* Status management */}
      <div className="card p-4 flex items-center gap-3 flex-wrap">
        <span className="text-sm font-medium text-gray-700">Update Status:</span>
        <div className="flex flex-wrap gap-2">
          {VALID_STATUSES.map(s => (
            <button
              key={s}
              onClick={() => handleStatusChange(s)}
              disabled={actionLoading === 'status' || opp.status === s}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                opp.status === s
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        {actionLoading === 'status' && <Loader2 className="w-4 h-4 animate-spin text-blue-600" />}
      </div>

      {/* All details card */}
      <div className="card p-5 space-y-6">

        {/* Basic Info */}
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

        {/* AI Analysis */}
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

        {/* Compliance */}
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
            <div className="sm:col-span-2"><Field label="Submission Checklist" value={opp.submission_checklist} /></div>
            <div className="sm:col-span-2"><Field label="Required Forms" value={opp.required_forms} /></div>
            <div className="sm:col-span-2"><Field label="Required Attachments" value={opp.required_attachments} /></div>
            <div className="sm:col-span-2"><Field label="Compliance Requirements" value={opp.compliance_requirements} /></div>
            <div className="sm:col-span-2"><Field label="Disqualifying Requirements" value={opp.disqualifying_requirements} /></div>
          </div>
        </div>

        <hr className="border-gray-100" />

        {/* Email source */}
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

      {/* Documents */}
      <div className="card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-900 text-sm">
            Solicitation Documents
            {opp.documents?.length > 0 && (
              <span className="ml-2 px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                {opp.documents.length}
              </span>
            )}
          </h3>
          {opp.documents?.length > 0 && (
            <button
              onClick={handleReviewDocs}
              disabled={actionLoading === 'review'}
              className="btn-secondary text-xs"
            >
              {actionLoading === 'review' ? (
                <><Loader2 className="w-3 h-3 animate-spin" /> Reviewing...</>
              ) : (
                <><Eye className="w-3 h-3" /> AI Review Documents</>
              )}
            </button>
          )}
        </div>

        {opp.documents?.length > 0 && (
          <div className="space-y-2">
            {opp.documents.map(doc => (
              <div key={doc.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <FileText className="w-5 h-5 text-blue-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{doc.original_filename}</p>
                  <p className="text-xs text-gray-500">
                    {doc.file_type?.toUpperCase()} ·{' '}
                    {doc.file_size ? `${(doc.file_size / 1024).toFixed(0)} KB` : ''}
                    {doc.reviewed && <span className="ml-2 text-green-600 font-medium">Reviewed</span>}
                  </p>
                </div>
                <button
                  onClick={() => handleDeleteDoc(doc.id)}
                  className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                  title="Delete document"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        <FileUpload opportunityId={id} onUploaded={load} />
      </div>

      {/* Packet actions */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-900 text-sm">Contract Opportunity Packet</h3>
          <div className="flex items-center gap-2">
            {hasPacket && (
              <>
                <button
                  onClick={() => setShowPacket(s => !s)}
                  className="btn-secondary text-xs"
                >
                  <Eye className="w-3 h-3" />
                  {showPacket ? 'Hide' : 'View'} Packet
                </button>
                <button
                  onClick={handleEmailPacket}
                  disabled={actionLoading === 'email'}
                  className="btn-success text-xs"
                >
                  {actionLoading === 'email' ? (
                    <><Loader2 className="w-3 h-3 animate-spin" /> Sending...</>
                  ) : (
                    <><Mail className="w-3 h-3" /> Email Packet</>
                  )}
                </button>
              </>
            )}
            <button
              onClick={handleBuildPacket}
              disabled={actionLoading === 'packet'}
              className="btn-primary text-xs"
            >
              {actionLoading === 'packet' ? (
                <><Loader2 className="w-3 h-3 animate-spin" /> Building...</>
              ) : (
                <><Package className="w-3 h-3" /> {hasPacket ? 'Rebuild' : 'Build'} Packet</>
              )}
            </button>
          </div>
        </div>

        {/* Custom instructions */}
        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Custom Instructions <span className="text-gray-400 font-normal">(optional — specific focus, tone, sections to emphasize, etc.)</span>
          </label>
          <textarea
            value={customInstructions}
            onChange={e => setCustomInstructions(e.target.value)}
            placeholder="e.g. Focus heavily on change management and training components. Emphasize Bernedette's PgMP certification. Include a teaming strategy section with specific partner types."
            rows={3}
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-800 placeholder-gray-400"
          />
        </div>

        {!hasPacket && !actionLoading && (
          <p className="text-sm text-gray-500">
            Generate a full proposal-ready packet following FaithForge's standard format —
            executive summary, scope of work, team background, and detailed budget.
          </p>
        )}

        {actionLoading === 'packet' && (
          <div className="flex items-center gap-3 p-4 bg-blue-50 rounded-lg">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
            <div>
              <p className="text-sm font-medium text-blue-900">Building packet with Claude AI...</p>
              <p className="text-xs text-blue-600 mt-0.5">This may take 1-2 minutes. Please wait.</p>
            </div>
          </div>
        )}

        {showPacket && packet?.html_content && (
          <div
            className="mt-4 p-5 bg-white border border-gray-200 rounded-xl prose prose-sm max-w-none overflow-auto"
            style={{ maxHeight: '600px' }}
            dangerouslySetInnerHTML={{ __html: packet.html_content }}
          />
        )}

        {packet && (
          <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
            <CheckCircle className="w-3.5 h-3.5 text-green-500" />
            Packet built {new Date(packet.created_at).toLocaleString()}
            {packet.emailed && ` · Emailed ${packet.emailed_at ? new Date(packet.emailed_at).toLocaleString() : ''}`}
          </div>
        )}
      </div>

      {/* Disclaimer */}
      <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800">
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
        <p>
          <strong>Important:</strong> This packet is AI-generated for internal review purposes only.
          Do not share externally without authorization. All bid/no-bid decisions require human review and approval.
          The AI does not submit proposals, sign documents, or make final decisions.
        </p>
      </div>
    </div>
  )
}
