import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { getToken } from './api'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Opportunities from './pages/Opportunities'
import OpportunityDetail from './pages/OpportunityDetail'
import Accounts from './pages/Accounts'
import AccountDetail from './pages/AccountDetail'
import Outreach from './pages/Outreach'
import Settings from './pages/Settings'
import AuditLog from './pages/AuditLog'

function RequireAuth({ children }) {
  return getToken() ? children : <Navigate to="/login" replace />
}

function RedirectToOutreach({ tab }) {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  if (tab) params.set('tab', tab)
  return <Navigate to={`/outreach?${params.toString()}`} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<RequireAuth><Layout /></RequireAuth>}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="opportunities" element={<Opportunities />} />
          <Route path="opportunities/:id" element={<OpportunityDetail />} />
          <Route path="accounts" element={<Accounts />} />
          <Route path="accounts/:id" element={<AccountDetail />} />
          <Route path="outreach" element={<Outreach />} />
          <Route path="cold-email" element={<RedirectToOutreach tab="single" />} />
          <Route path="bulk-outreach" element={<RedirectToOutreach tab="bulk" />} />
          <Route path="audit" element={<AuditLog />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
