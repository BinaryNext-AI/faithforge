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

// Audit
export const getAuditLog = (params = {}) => api.get('/audit', { params }).then(r => r.data)

// Settings
export const getSettings = () => api.get('/settings').then(r => r.data)
export const updateSettings = (data) => api.put('/settings', data).then(r => r.data)
