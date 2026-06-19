import { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Save, Loader2, CheckCircle, Eye, EyeOff, CheckCircle2, XCircle } from 'lucide-react'
import { getSettings, updateSettings } from '../api'
import axios from 'axios'

const SETTING_GROUPS = [
  {
    title: 'AI Configuration',
    icon: '🤖',
    keys: ['ANTHROPIC_API_KEY'],
    descriptions: {
      ANTHROPIC_API_KEY: 'Your Anthropic API key for Claude AI (claude-opus-4-8)',
    },
  },
  {
    title: 'Microsoft Graph API (Recommended for Microsoft 365 / Outlook)',
    icon: '📧',
    keys: ['MS_CLIENT_ID', 'MS_CLIENT_SECRET', 'MS_TENANT_ID', 'MS_EMAIL_ADDRESS', 'MS_AUTH_MODE'],
    descriptions: {
      MS_CLIENT_ID: 'Azure App Registration → Application (client) ID',
      MS_CLIENT_SECRET: 'Azure App Registration → Certificates & secrets → Client secret value',
      MS_TENANT_ID: 'Azure App Registration → Directory (tenant) ID  |  Use "common" for personal Outlook.com',
      MS_EMAIL_ADDRESS: 'The mailbox to scan and send from (e.g. you@yourorg.com)',
      MS_AUTH_MODE: '"client_credentials" for M365 work accounts (recommended)  |  "device_code" for personal Outlook.com',
    },
  },
  {
    title: 'Email Scanning — IMAP Fallback (Gmail or if not using Graph API)',
    icon: '📥',
    keys: ['IMAP_HOST', 'IMAP_PORT', 'IMAP_USERNAME', 'IMAP_PASSWORD', 'IMAP_FOLDER', 'IMAP_SCAN_DAYS'],
    descriptions: {
      IMAP_HOST: 'e.g. imap.gmail.com — only used if MS Graph credentials are blank',
      IMAP_PORT: 'Usually 993 for SSL',
      IMAP_USERNAME: 'Your email address',
      IMAP_PASSWORD: 'App password (not your main password)',
      IMAP_FOLDER: 'Email folder to scan (default: INBOX)',
      IMAP_SCAN_DAYS: 'How many days back to scan for emails',
    },
  },
  {
    title: 'Email Delivery — SMTP Fallback (Gmail or if not using Graph API)',
    icon: '📤',
    keys: ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'SMTP_FROM_EMAIL', 'SMTP_FROM_NAME', 'NOTIFICATION_EMAIL'],
    descriptions: {
      SMTP_HOST: 'e.g. smtp.gmail.com — only used if MS Graph credentials are blank',
      SMTP_PORT: 'Usually 587 for TLS',
      SMTP_USERNAME: 'SMTP login (usually your email)',
      SMTP_PASSWORD: 'App password for SMTP',
      SMTP_FROM_EMAIL: 'Sender email address',
      SMTP_FROM_NAME: 'Sender display name',
      NOTIFICATION_EMAIL: 'Where to send completed packets (required)',
    },
  },
]

function SettingInput({ settingKey, value, onChange, isSecret, description }) {
  const [show, setShow] = useState(false)
  const type = isSecret && !show ? 'password' : 'text'

  return (
    <div>
      <label className="label">
        {settingKey.replace(/_/g, ' ')}
      </label>
      {description && <p className="text-xs text-gray-500 mb-1">{description}</p>}
      <div className="relative">
        <input
          type={type}
          value={value || ''}
          onChange={e => onChange(settingKey, e.target.value)}
          className="input pr-10"
          placeholder={isSecret ? '••••••••' : ''}
        />
        {isSecret && (
          <button
            type="button"
            onClick={() => setShow(s => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
    </div>
  )
}

export default function Settings() {
  const [settingsData, setSettingsData] = useState({})
  const [secretKeys, setSecretKeys] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)
  const [msStatus, setMsStatus] = useState(null)
  const [msChecking, setMsChecking] = useState(false)

  useEffect(() => {
    getSettings()
      .then(data => {
        const map = {}
        const secrets = new Set()
        data.forEach(s => {
          map[s.key] = s.value === '••••••••' ? '' : (s.value || '')
          if (s.is_secret) secrets.add(s.key)
        })
        setSettingsData(map)
        setSecretKeys(secrets)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const handleChange = (key, value) => {
    setSettingsData(prev => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  const checkMsStatus = async () => {
    setMsChecking(true)
    try {
      const res = await axios.get('/api/auth/microsoft/status')
      setMsStatus(res.data)
    } catch (e) {
      setMsStatus({ configured: false, message: e.message })
    } finally {
      setMsChecking(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const toSend = {}
      for (const [k, v] of Object.entries(settingsData)) {
        if (v) toSend[k] = v
      }
      await updateSettings(toSend)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return (
    <div className="flex justify-center py-16">
      <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
    </div>
  )

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <SettingsIcon className="w-6 h-6 text-gray-700" />
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="btn-primary"
        >
          {saving ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</>
          ) : saved ? (
            <><CheckCircle className="w-4 h-4" /> Saved!</>
          ) : (
            <><Save className="w-4 h-4" /> Save Settings</>
          )}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-800">
        <strong>Security note:</strong> Settings are stored in the application database.
        Never share your API keys or email credentials. Use app-specific passwords for email access.
      </div>

      {/* MS Graph status */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-gray-900 flex items-center gap-2">
            📧 Microsoft Graph API Status
          </h2>
          <button onClick={checkMsStatus} disabled={msChecking} className="btn-secondary text-xs">
            {msChecking ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Test Connection'}
          </button>
        </div>
        {msStatus ? (
          <div className={`flex items-start gap-2 text-sm p-3 rounded-lg ${
            msStatus.authenticated ? 'bg-green-50 text-green-800' : 'bg-gray-50 text-gray-700'
          }`}>
            {msStatus.authenticated
              ? <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5 shrink-0" />
              : <XCircle className="w-4 h-4 text-gray-400 mt-0.5 shrink-0" />}
            <div>
              <p>{msStatus.message || (msStatus.authenticated ? `Connected as ${msStatus.email}` : 'Not connected')}</p>
              {msStatus.auth_mode && <p className="text-xs mt-0.5 opacity-70">Mode: {msStatus.auth_mode}</p>}
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500">Fill in the MS Graph fields below and click "Test Connection" to verify.</p>
        )}
      </div>

      {SETTING_GROUPS.map(group => (
        <div key={group.title} className="card p-5 space-y-4">
          <h2 className="font-semibold text-gray-900 flex items-center gap-2">
            <span>{group.icon}</span>
            {group.title}
          </h2>
          <div className="grid grid-cols-1 gap-4">
            {group.keys.map(key => (
              <SettingInput
                key={key}
                settingKey={key}
                value={settingsData[key]}
                onChange={handleChange}
                isSecret={secretKeys.has(key)}
                description={group.descriptions?.[key]}
              />
            ))}
          </div>
        </div>
      ))}

      <div className="card p-5">
        <h2 className="font-semibold text-gray-900 mb-3">Gmail / Google Workspace Setup</h2>
        <div className="text-sm text-gray-600 space-y-2">
          <p>For Gmail, you need an <strong>App Password</strong> (not your regular password):</p>
          <ol className="list-decimal list-inside space-y-1 text-sm">
            <li>Go to Google Account → Security → 2-Step Verification</li>
            <li>Scroll to "App passwords" → Select "Mail" and "Other"</li>
            <li>Generate and copy the 16-character password</li>
            <li>Use <strong>imap.gmail.com</strong> (port 993) for IMAP</li>
            <li>Use <strong>smtp.gmail.com</strong> (port 587) for SMTP</li>
          </ol>
        </div>
      </div>

      <div className="card p-5">
        <h2 className="font-semibold text-gray-900 mb-3">Microsoft 365 / Outlook Setup</h2>
        <div className="text-sm text-gray-600 space-y-1">
          <p>Use <strong>outlook.office365.com</strong> (port 993) for IMAP</p>
          <p>Use <strong>smtp.office365.com</strong> (port 587) for SMTP</p>
          <p>Enable IMAP in Outlook settings if it's not already active.</p>
        </div>
      </div>
    </div>
  )
}
