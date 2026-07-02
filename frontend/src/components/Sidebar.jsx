import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, FileSearch, Building2, Mail, Settings, ClipboardList, Shield, LogOut
} from 'lucide-react'
import { logout } from '../api'

const nav = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/opportunities', label: 'Opportunities', icon: FileSearch },
  { to: '/accounts', label: 'Accounts', icon: Building2 },
  { to: '/cold-email', label: 'Cold Email', icon: Mail },
  { to: '/audit', label: 'Audit Log', icon: ClipboardList },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function Sidebar() {
  return (
    <aside className="w-60 bg-slate-900 text-white flex flex-col shrink-0">
      <div className="px-5 py-6 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Shield className="w-6 h-6 text-blue-400" />
          <div>
            <p className="font-bold text-sm leading-tight">FaithForge AI</p>
            <p className="text-slate-400 text-xs">Contract Screener</p>
          </div>
        </div>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }`
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-slate-700 space-y-3">
        <p className="text-slate-500 text-xs">
          AI does not submit or approve.
          <br />All decisions require human review.
        </p>
        <button
          onClick={logout}
          className="flex items-center gap-2 text-slate-400 hover:text-white text-xs transition-colors w-full"
        >
          <LogOut className="w-3.5 h-3.5" />
          Sign out
        </button>
      </div>
    </aside>
  )
}
