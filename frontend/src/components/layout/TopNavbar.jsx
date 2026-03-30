import { Bell, Search, ChevronDown, Menu } from 'lucide-react'
import { useLocation } from 'react-router-dom'

const pageTitles = {
  '/dashboard': { title: 'Dashboard', sub: 'Welcome back, Admin' },
  '/linkedin': { title: 'LinkedIn Analytics', sub: 'Lead generation insights' },
  '/calls': { title: 'Call Analytics', sub: 'Inbound & outbound performance' },
  '/users': { title: 'User Analytics', sub: 'Engagement & behavior metrics' },
  '/leads': { title: 'Lead Management', sub: 'Pipeline & qualification tracking' },
  '/feedback': { title: 'User Feedback', sub: 'Sentiment & feature requests' },
  '/ai-logs': { title: 'AI Call Logs', sub: 'Automated call history' },
  '/settings': { title: 'Settings', sub: 'System configuration' },
}

export default function TopNavbar({ onMenuClick }) {
  const location = useLocation()
  const page = pageTitles[location.pathname] || { title: 'Dashboard', sub: '' }

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white/80"
      style={{
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
      }}>
      {/* Left */}
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="p-2 rounded-xl hover:bg-gray-100 text-gray-500 hover:text-gray-900 transition-all duration-200 lg:flex hidden"
          aria-label="Toggle sidebar"
        >
          <Menu size={18} />
        </button>
        <button
          onClick={onMenuClick}
          className="p-2 rounded-xl hover:bg-gray-100 text-gray-500 hover:text-gray-900 transition-all duration-200 flex lg:hidden"
          aria-label="Open menu"
        >
          <Menu size={18} />
        </button>
        <div>
          <h1 className="text-base font-semibold text-gray-900 leading-none">{page.title}</h1>
          <p className="text-xs text-gray-500 mt-0.5">{page.sub}</p>
        </div>
      </div>

      {/* Right */}
      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="relative hidden md:flex items-center">
          <Search size={14} className="absolute left-3 text-gray-400" />
          <input
            type="text"
            placeholder="Search..."
            className="w-52 pl-9 pr-4 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-500 focus:bg-white transition-all shadow-sm"
          />
          <kbd className="absolute right-3 text-[10px] text-gray-400 font-mono">⌘K</kbd>
        </div>

        {/* Notifications */}
        <button className="relative p-2 rounded-xl hover:bg-gray-100 text-gray-500 hover:text-gray-900 transition-all">
          <Bell size={16} />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-accent-red rounded-full ring-2 ring-white" />
        </button>

        {/* Status badge */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-accent-green/10 border border-accent-green/20">
          <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
          <span className="text-xs font-medium text-accent-green">Live</span>
        </div>

        {/* User */}
        <button className="flex items-center gap-2 px-3 py-1.5 rounded-xl hover:bg-gray-100 transition-all">
          <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white"
            style={{ background: 'linear-gradient(135deg, #2563eb, #3b82f6)' }}>
            AD
          </div>
          <ChevronDown size={12} className="text-gray-400 hidden sm:block" />
        </button>
      </div>
    </header>
  )
}
