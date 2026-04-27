import { NavLink, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Linkedin, Phone, Users, MessageSquare,
  Target, Bot, Settings, Bell, ChevronRight, Zap, X,
  BarChart3, PhoneCall, UserCheck, TrendingUp, Package, PlusSquare,
  BrainCircuit, AlertCircle, Mail, Calendar, BookOpen
} from 'lucide-react'

const navSections = [
  {
    title: 'Overview',
    items: [
      { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    ]
  },
  {
    title: 'Analytics',
    items: [
      { path: '/linkedin', icon: Linkedin, label: 'LinkedIn Analytics' },
      { path: '/calls', icon: PhoneCall, label: 'Call Analytics' },
      { path: '/ai-analytics', icon: BrainCircuit, label: 'AI Analytics' },
      { path: '/users', icon: UserCheck, label: 'User Analytics' },
    ]
  },
  {
    title: 'Management',
    items: [
      { path: '/leads', icon: Target, label: 'Lead Management' },
      { path: '/gaps', icon: AlertCircle, label: 'Knowledge Gaps' },
      { path: '/feedback', icon: MessageSquare, label: 'User Feedback' },
      { path: '/ai-logs', icon: Bot, label: 'AI Call Logs' },
    ]
  },
  {
    title: 'Communication',
    items: [
      { path: '/gmail', icon: Mail, label: 'Gmail Inbox' },
      { path: '/calendar', icon: Calendar, label: 'Calendar' },
    ]
  },
  {
    title: 'Products',
    items: [
      { path: '/products', icon: Package, label: 'Products' },
      { path: '/add-product', icon: PlusSquare, label: 'Add Product' },
    ]
  },
  {
    title: 'System',
    items: [
      { path: '/settings', icon: Settings, label: 'Settings' },
    ]
  },
]

export default function Sidebar({ open, mobileOpen, onMobileClose }) {
  const location = useLocation()

  const sidebarContent = (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-gray-200">
        <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{ background: 'linear-gradient(135deg, #2563eb, #3b82f6)' }}>
          <Zap size={16} className="text-white" />
        </div>
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2 }}
              className="flex flex-col"
            >
              <span className="text-sm font-bold text-gray-900 leading-none">NexusAI</span>
              <span className="text-[10px] text-gray-500 font-medium mt-0.5">Admin Dashboard</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-6">
        {navSections.map((section) => (
          <div key={section.title}>
            <AnimatePresence>
              {open && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest px-3 mb-2"
                >
                  {section.title}
                </motion.p>
              )}
            </AnimatePresence>
            <ul className="space-y-1">
              {section.items.map(({ path, icon: Icon, label }) => {
                const isActive = location.pathname === path
                return (
                  <li key={path}>
                    <NavLink
                      to={path}
                      onClick={onMobileClose}
                      className={`nav-item group relative flex items-center gap-3 px-3 py-2 rounded-xl transition-colors ${isActive ? 'text-blue-600' : 'text-gray-600 hover:bg-gray-100'}`}
                      title={!open ? label : undefined}
                    >
                      {isActive && (
                        <motion.div
                          layoutId="activeNav"
                          className="absolute inset-0 rounded-xl bg-blue-50"
                          transition={{ type: 'spring', bounce: 0.2, duration: 0.5 }}
                        />
                      )}
                      <Icon
                        size={16}
                        className={`flex-shrink-0 relative z-10 transition-colors ${isActive ? 'text-blue-600' : 'text-gray-500 group-hover:text-gray-900'}`}
                      />
                      <AnimatePresence>
                        {open && (
                          <motion.span
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -8 }}
                            transition={{ duration: 0.15 }}
                            className="relative z-10 text-sm font-medium"
                          >
                            {label}
                          </motion.span>
                        )}
                      </AnimatePresence>
                      {isActive && open && (
                        <ChevronRight size={12} className="ml-auto text-blue-600 relative z-10" />
                      )}
                    </NavLink>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Bottom user section */}
      <div className="p-3 border-t border-gray-200">
        <NavLink to="/settings" onClick={onMobileClose} className="flex items-center gap-3 px-2 py-2 rounded-xl hover:bg-gray-100 transition-colors cursor-pointer w-full text-left">
          <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold text-white shadow-sm"
            style={{ background: 'linear-gradient(135deg, #2563eb, #3b82f6)' }}>
            AD
          </div>
          <AnimatePresence>
            {open && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex-1 min-w-0"
              >
                <p className="text-xs font-semibold text-gray-900 truncate">Admin User</p>
                <p className="text-[10px] text-gray-500 truncate">admin@nexusai.io</p>
              </motion.div>
            )}
          </AnimatePresence>
        </NavLink>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop sidebar */}
      <motion.aside
        animate={{ width: open ? 260 : 72 }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
        className="fixed left-0 top-0 h-full z-30 hidden lg:block overflow-hidden border-r border-gray-200 bg-white"
      >
        {sidebarContent}
      </motion.aside>

      {/* Mobile sidebar */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.aside
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            exit={{ x: -280 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed left-0 top-0 h-full w-64 z-50 lg:hidden border-r border-gray-200 bg-white"
          >
            <button
              onClick={onMobileClose}
              className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-900 transition-colors"
            >
              <X size={16} />
            </button>
            {sidebarContent}
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  )
}
