import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '../api'
import { Loader2, Mail, Lock, User, ArrowRight } from 'lucide-react'

export default function Login() {
  const [mode, setMode]           = useState('login') // 'login' | 'register'
  const [name, setName]           = useState('')
  const [email, setEmail]         = useState('')
  const [password, setPassword]   = useState('')
  const [confirm, setConfirm]     = useState('')
  const [error, setError]         = useState('')
  const [loading, setLoading]     = useState(false)
  const navigate = useNavigate()

  const switchMode = (m) => { setMode(m); setError('') }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (mode === 'register') {
      if (password !== confirm) { setError('Passwords do not match'); return }
      if (password.length < 6) { setError('Password must be at least 6 characters'); return }
    }
    setLoading(true)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await register(name, email, password)
      }
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err.message || (mode === 'login' ? 'Invalid email or password' : 'Registration failed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-950 via-blue-900 to-indigo-900 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white/10 backdrop-blur rounded-2xl mb-4 ring-1 ring-white/20">
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">FaithForge AI</h1>
          <p className="text-blue-300 text-sm mt-1">Contract Opportunity Screener</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-2xl overflow-hidden">

          {/* Tab switcher */}
          <div className="flex border-b border-gray-100">
            <button
              onClick={() => switchMode('login')}
              className={`flex-1 py-3.5 text-sm font-semibold transition-colors ${
                mode === 'login' ? 'text-blue-700 border-b-2 border-blue-600 bg-blue-50/50' : 'text-gray-400 hover:text-gray-600'
              }`}
            >Sign In</button>
            <button
              onClick={() => switchMode('register')}
              className={`flex-1 py-3.5 text-sm font-semibold transition-colors ${
                mode === 'register' ? 'text-blue-700 border-b-2 border-blue-600 bg-blue-50/50' : 'text-gray-400 hover:text-gray-600'
              }`}
            >Create Account</button>
          </div>

          <form onSubmit={handleSubmit} className="p-6 space-y-4">

            {mode === 'register' && (
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5 uppercase tracking-wide">Full Name</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="text" value={name} onChange={e => setName(e.target.value)}
                    placeholder="Bernedette Atong"
                    className="input w-full pl-9" required autoFocus
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1.5 uppercase tracking-wide">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="email" value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="you@faithforgetech.com"
                  className="input w-full pl-9" required autoFocus={mode === 'login'}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1.5 uppercase tracking-wide">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="password" value={password} onChange={e => setPassword(e.target.value)}
                  placeholder={mode === 'register' ? 'Min. 6 characters' : '••••••••'}
                  className="input w-full pl-9" required
                />
              </div>
            </div>

            {mode === 'register' && (
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5 uppercase tracking-wide">Confirm Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
                    placeholder="Re-enter password"
                    className="input w-full pl-9" required
                  />
                </div>
              </div>
            )}

            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full justify-center mt-2">
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> {mode === 'login' ? 'Signing in...' : 'Creating account...'}</>
              ) : (
                <>{mode === 'login' ? 'Sign In' : 'Create Account'} <ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-blue-400 text-xs mt-6">
          FaithForge Technologies & Consulting LLC
        </p>
      </div>
    </div>
  )
}
