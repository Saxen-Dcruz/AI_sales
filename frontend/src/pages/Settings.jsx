import { motion } from 'framer-motion'
import { Bell, Shield, Cpu, Globe, Key, Save } from 'lucide-react'

const sections = [
  {
    icon: Cpu,
    title: 'AI Configuration',
    color: '#6172f3',
    fields: [
      { label: 'AI Model', type: 'select', options: ['GPT-4o', 'Claude 3.5 Sonnet', 'Gemini Pro'], value: 'GPT-4o' },
      { label: 'Max Calls Per Hour', type: 'number', value: '120' },
      { label: 'AI Tone', type: 'select', options: ['Professional', 'Friendly', 'Formal'], value: 'Professional' },
      { label: 'Auto-retry Failed Calls', type: 'toggle', value: true },
    ]
  },
  {
    icon: Globe,
    title: 'LinkedIn Integration',
    color: '#0077b5',
    fields: [
      { label: 'API Key', type: 'password', value: 'sk-xxxx-yyyy-zzzz' },
      { label: 'Scrape Rate Limit (per hour)', type: 'number', value: '200' },
      { label: 'Auto-connect Requests', type: 'toggle', value: false },
      { label: 'Post Generation', type: 'toggle', value: true },
    ]
  },
  {
    icon: Bell,
    title: 'Notifications',
    color: '#f59e0b',
    fields: [
      { label: 'Email Alerts', type: 'toggle', value: true },
      { label: 'Slack Webhook URL', type: 'text', value: 'https://hooks.slack.com/...' },
      { label: 'New Lead Alert', type: 'toggle', value: true },
      { label: 'Call Summary Digest', type: 'select', options: ['Daily', 'Weekly', 'Off'], value: 'Daily' },
    ]
  },
  {
    icon: Shield,
    title: 'Security',
    color: '#10b981',
    fields: [
      { label: 'Two-Factor Auth', type: 'toggle', value: true },
      { label: 'Session Timeout (minutes)', type: 'number', value: '60' },
      { label: 'API Rate Limiting', type: 'toggle', value: true },
      { label: 'Data Encryption', type: 'toggle', value: true },
    ]
  },
]

function Toggle({ value }) {
  return (
    <div className={`relative w-10 h-5 rounded-full transition-all cursor-pointer ${value ? 'bg-primary-600' : 'bg-gray-200'}`}>
      <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${value ? 'left-5' : 'left-0.5'}`} />
    </div>
  )
}

export default function Settings() {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5 max-w-4xl">
      {sections.map((section, si) => (
        <motion.div key={si} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: si * 0.08 }}
          className="glass-card p-6">
          <div className="flex items-center gap-3 mb-5 pb-4 border-b border-gray-200">
            <div className="p-2 rounded-xl" style={{ background: `${section.color}20` }}>
              <section.icon size={16} style={{ color: section.color }} />
            </div>
            <h3 className="text-sm font-semibold text-gray-900">{section.title}</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {section.fields.map((field, fi) => (
              <div key={fi} className="flex items-center justify-between p-3.5 rounded-xl bg-gray-50 border border-gray-200">
                <label className="text-xs text-gray-600 font-medium">{field.label}</label>
                {field.type === 'toggle' ? (
                  <Toggle value={field.value} />
                ) : field.type === 'select' ? (
                  <select className="text-xs bg-white border border-gray-200 rounded-lg px-2 py-1 text-gray-900 focus:outline-none focus:border-blue-500">
                    {field.options.map(o => <option key={o} className="bg-white">{o}</option>)}
                  </select>
                ) : field.type === 'password' ? (
                  <div className="relative">
                    <Key size={10} className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input type="password" defaultValue={field.value}
                      className="text-xs bg-white border border-gray-200 rounded-lg pl-5 pr-2 py-1 text-gray-900 focus:outline-none focus:border-blue-500 w-36 shadow-sm" />
                  </div>
                ) : (
                  <input type={field.type} defaultValue={field.value}
                    className="text-xs bg-white border border-gray-200 rounded-lg px-2 py-1 text-gray-900 focus:outline-none focus:border-blue-500 w-28 text-right shadow-sm" />
                )}
              </div>
            ))}
          </div>
        </motion.div>
      ))}

      <div className="flex justify-end">
        <button className="btn-primary flex items-center gap-2">
          <Save size={14} />
          Save All Settings
        </button>
      </div>
    </motion.div>
  )
}
