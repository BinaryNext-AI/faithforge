import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { UserRound, Users2 } from 'lucide-react'
import ColdEmail from './ColdEmail'
import BulkOutreach from './BulkOutreach'

const TABS = [
  {
    key: 'single',
    label: 'One Prospect',
    icon: UserRound,
    blurb: "You know one specific company or person you want to email. Type in their details and AI drafts a short email sequence for you to copy and send yourself.",
  },
  {
    key: 'bulk',
    label: 'Many Prospects (Spreadsheet)',
    icon: Users2,
    blurb: "You have a spreadsheet of many leads. Upload it, AI drafts one email per lead, you approve them, and the system sends them automatically.",
  },
]

export default function Outreach() {
  const [searchParams] = useSearchParams()
  const [tab, setTab] = useState(searchParams.get('tab') === 'bulk' ? 'bulk' : 'single')
  const active = TABS.find(t => t.key === tab)

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Outreach</h1>
        <p className="text-sm text-gray-400 mt-0.5">Two ways to reach out — pick the one that matches what you're doing right now.</p>
      </div>

      <div className="flex gap-2">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors ${
              tab === t.key ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <t.icon className="w-4 h-4" />
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-200 text-blue-900 rounded-lg text-sm">
        <span>{active.blurb}</span>
      </div>

      {tab === 'single' ? <ColdEmail embedded /> : <BulkOutreach />}
    </div>
  )
}
