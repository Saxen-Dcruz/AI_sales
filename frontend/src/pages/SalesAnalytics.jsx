import { useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart2, Linkedin, Mail, MessageCircle, Phone } from 'lucide-react'
import GmailAnalytics from './GmailAnalytics'
import CallAnalytics from './CallAnalytics'
import LinkedInAnalytics from './LinkedInAnalytics'

const OUTER_TABS = [
  { key: 'email',     label: 'Email',     icon: Mail },
  { key: 'whatsapp',  label: 'WhatsApp',  icon: MessageCircle },
  { key: 'call',      label: 'AI Call',   icon: Phone },
  { key: 'linkedin',  label: 'LinkedIn',  icon: Linkedin },
]

function PlaceholderTab({ icon: Icon, label, color }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4 text-gray-300">
      <div className="w-16 h-16 rounded-2xl flex items-center justify-center" style={{ background: `${color}15` }}>
        <Icon size={32} style={{ color }} />
      </div>
      <div className="text-center">
        <p className="text-base font-bold text-gray-400">{label} Analytics</p>
        <p className="text-sm text-gray-300 mt-1">Integration not yet connected</p>
        <p className="text-xs text-gray-300 mt-0.5">Set up {label} to start seeing data here</p>
      </div>
    </div>
  )
}

export default function SalesAnalytics() {
  const [activeTab, setActiveTab] = useState('email')

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      {/* Page header */}
      <div className="bg-white border-b border-gray-100 px-6 py-5">
        <div className="max-w-[1400px] mx-auto">
          <div className="flex items-center gap-3 mb-5">
            <div className="p-2 rounded-xl bg-indigo-50">
              <BarChart2 size={20} className="text-indigo-600" />
            </div>
            <div>
              <h1 className="text-xl font-black text-gray-900 tracking-tight">Sales Analytics</h1>
              <p className="text-xs text-gray-400 mt-0.5">Unified analytics across all channels</p>
            </div>
          </div>

          {/* Outer channel tabs */}
          <div className="flex gap-1 border-b border-gray-100 -mb-px">
            {OUTER_TABS.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`relative flex items-center gap-2 px-5 py-2.5 text-sm font-semibold transition-all rounded-t-lg ${
                  activeTab === key
                    ? 'text-indigo-600 bg-indigo-50/60'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                <Icon size={15} />
                {label}
                {activeTab === key && (
                  <motion.div
                    layoutId="salesAnalyticsTabUnderline"
                    className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-600 rounded-full"
                  />
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tab content */}
      {activeTab === 'email' && (
        <GmailAnalytics hideHeader={true} />
      )}

      {activeTab === 'whatsapp' && (
        <div className="max-w-[1400px] mx-auto px-6 py-6">
          <PlaceholderTab icon={MessageCircle} label="WhatsApp" color="#25D366" />
        </div>
      )}

      {activeTab === 'call' && (
        <div className="max-w-[1400px] mx-auto px-6 py-6">
          <CallAnalytics />
        </div>
      )}

      {activeTab === 'linkedin' && (
        <LinkedInAnalytics hideHeader={true} />
      )}
    </div>
  )
}
