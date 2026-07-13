import axios from 'axios'

const TOKEN_KEY = 'ff_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

const api = axios.create({
  baseURL: (import.meta.env.VITE_API_URL || '') + '/api',
  timeout: 300000, // 5 min for AI operations
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      clearToken()
      window.location.href = '/login'
    }
    const msg = err.response?.data?.detail || err.message || 'Request failed'
    return Promise.reject(new Error(msg))
  }
)

// Auth
export const login = (email, password) =>
  api.post('/auth/login', { email, password }).then(r => { setToken(r.data.token); return r.data })
export const register = (name, email, password) =>
  api.post('/auth/register', { name, email, password }).then(r => { setToken(r.data.token); return r.data })
export const logout = () =>
  api.post('/auth/logout').finally(() => { clearToken(); window.location.href = '/login' })

// Dashboard
export const getDashboardStats = () => api.get('/dashboard/stats').then(r => r.data)

// Opportunities
export const getOpportunities = (params = {}) => api.get('/opportunities', { params }).then(r => r.data)
export const createOpportunity = (data) => api.post('/opportunities', data).then(r => r.data)
export const getOpportunity = (id) => api.get(`/opportunities/${id}`).then(r => r.data)
export const updateOpportunity = (id, data) => api.put(`/opportunities/${id}`, data).then(r => r.data)
export const updateStatus = (id, status) => api.put(`/opportunities/${id}/status`, { status }).then(r => r.data)
export const deleteOpportunity = (id) => api.delete(`/opportunities/${id}`).then(r => r.data)

// Email scan
export const scanEmail = (days_back = 30) => api.post('/scan/email', null, { params: { days_back } }).then(r => r.data)
export const getScanStatus = () => api.get('/scan/status').then(r => r.data)

// Documents
export const uploadDocument = (opportunityId, file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post(`/opportunities/${opportunityId}/documents`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}
export const getDocuments = (opportunityId) => api.get(`/opportunities/${opportunityId}/documents`).then(r => r.data)
export const deleteDocument = (opportunityId, docId) => api.delete(`/opportunities/${opportunityId}/documents/${docId}`).then(r => r.data)
export const reviewDocuments = (opportunityId) => api.post(`/opportunities/${opportunityId}/documents/review`).then(r => r.data)

// Packets — multi-pass generation via OpenAI can take several minutes
export const buildPacket = (opportunityId, customInstructions = '') =>
  api.post(`/opportunities/${opportunityId}/packet`, { custom_instructions: customInstructions }, { timeout: 600000 }).then(r => r.data)
export const getPacket = (opportunityId) => api.get(`/opportunities/${opportunityId}/packet`).then(r => r.data)
export const emailPacket = (opportunityId) => api.post(`/opportunities/${opportunityId}/packet/email`).then(r => r.data)
export const exportPacket = async (opportunityId, format = 'docx') => {
  const res = await api.get(`/opportunities/${opportunityId}/packet/export`, {
    params: { format },
    responseType: 'blob',
  })
  const disposition = res.headers['content-disposition'] || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const filename = match ? match[1] : `proposal.${format}`
  const url = window.URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}
export const completeDraftProposal = (opportunityId, { document_id, draft_text, custom_instructions } = {}) =>
  api.post(`/opportunities/${opportunityId}/proposal/complete-draft`,
    { document_id, draft_text, custom_instructions }, { timeout: 600000 }).then(r => r.data)
export const revisePacket = (opportunityId, instruction) =>
  api.post(`/opportunities/${opportunityId}/packet/revise`, { instruction }, { timeout: 600000 }).then(r => r.data)

// CRM Accounts
export const getCrmStats = () => api.get('/crm/stats').then(r => r.data)
export const getAccounts = (params = {}) => api.get('/accounts', { params }).then(r => r.data)
export const getAccount = (id) => api.get(`/accounts/${id}`).then(r => r.data)
export const createAccount = (data) => api.post('/accounts', data).then(r => r.data)
export const updateAccount = (id, data) => api.put(`/accounts/${id}`, data).then(r => r.data)
export const updateAccountStage = (id, stage) => api.put(`/accounts/${id}/stage`, { stage }).then(r => r.data)
export const deleteAccount = (id) => api.delete(`/accounts/${id}`).then(r => r.data)
export const scoreAccount = (id) => api.post(`/accounts/${id}/score`).then(r => r.data)

// Cold Email Generator
export const generateColdEmail = (data) => api.post('/cold-email/generate', data).then(r => r.data)

// Bulk Outreach
export const outreachPreviewFile = (file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/outreach/import/preview', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}
export const outreachPreviewGoogleSheet = (googleSheetUrl) => {
  const form = new FormData()
  form.append('google_sheet_url', googleSheetUrl)
  return api.post('/outreach/import/preview', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}
export const outreachCommitImport = (rows, sourceFilename, dedupe = 'skip') =>
  api.post('/outreach/import/commit', { rows, source_filename: sourceFilename, dedupe }).then(r => r.data)
export const outreachGenerate = (accountIds, method = 'sync', model = null) =>
  api.post('/outreach/generate', { account_ids: accountIds, method, model }, { timeout: 600000 }).then(r => r.data)
export const outreachGetBatches = () => api.get('/outreach/batches').then(r => r.data)
export const outreachGetBatch = (id) => api.get(`/outreach/batches/${id}`).then(r => r.data)
export const outreachRefreshBatch = (id) => api.post(`/outreach/batches/${id}/refresh`).then(r => r.data)
export const outreachGetEmails = (params = {}) => api.get('/outreach/emails', { params }).then(r => r.data)
export const outreachUpdateEmail = (id, data) => api.patch(`/outreach/emails/${id}`, data).then(r => r.data)
export const outreachApproveEmail = (id) => api.post(`/outreach/emails/${id}/approve`).then(r => r.data)
export const outreachUnapproveEmail = (id) => api.post(`/outreach/emails/${id}/unapprove`).then(r => r.data)
export const outreachBulkApprove = (ids) => api.post('/outreach/emails/bulk-approve', { ids }).then(r => r.data)
export const outreachSendOne = (id) => api.post(`/outreach/emails/${id}/send`).then(r => r.data)
export const outreachSendBulk = (ids) => api.post('/outreach/send', { ids }, { timeout: 300000 }).then(r => r.data)

// Go/No-Go Assessment
export const scoreGoNoGo = (id) => api.post(`/opportunities/${id}/gonogo`).then(r => r.data)

// Audit
export const getAuditLog = (params = {}) => api.get('/audit', { params }).then(r => r.data)

// Settings
export const getSettings = () => api.get('/settings').then(r => r.data)
export const updateSettings = (data) => api.put('/settings', data).then(r => r.data)
