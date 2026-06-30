import { AnimatePresence, motion } from 'framer-motion'
import {
    AlertCircle,
    Bot,
    BrainCircuit,
    Calendar,
    ChevronDown,
    ChevronRight,
    Inbox,
    LayoutDashboard,
    Linkedin,
    Mail,
    MailSearch,
    Megaphone,
    MessageSquare,
    Package,
    PhoneCall,
    PlusSquare,
    Search,
    Settings,
    Target,
    UserCheck,
    X,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

const navSections = [
  {
    key: 'overview',
    title: 'Overview',
    defaultOpen: true,
    items: [
      { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    ],
  },
  {
    key: 'analytics',
    title: 'Analytics',
    defaultOpen: true,
    items: [
      { path: '/calls', icon: PhoneCall, label: 'Call Analytics' },
      { path: '/sales-analytics', icon: MailSearch, label: 'Sales Analytics' },
      { path: '/ai-analytics', icon: BrainCircuit, label: 'AI Analytics' },
      { path: '/linkedin', icon: Linkedin, label: 'LinkedIn Analytics' },
      { path: '/linkedin-integration', icon: Linkedin, label: 'LinkedIn Pipeline' },
      { path: '/users', icon: UserCheck, label: 'Team Analytics' },
    ],
  },
  {
    key: 'management',
    title: 'Management',
    defaultOpen: true,
    items: [
      { path: '/leads', icon: Target, label: 'Lead Management' },
      { path: '/gaps', icon: AlertCircle, label: 'Knowledge Gaps' },
      { path: '/feedback', icon: MessageSquare, label: 'User Feedback' },
      { path: '/ai-logs', icon: Bot, label: 'AI Call Logs' },
    ],
  },
  {
    key: 'communication',
    title: 'Communication',
    defaultOpen: true,
    items: [
      { path: '/gmail', icon: Mail, label: 'Gmail Inbox' },
      { path: '/calendar', icon: Calendar, label: 'Calendar' },
    ],
  },
  {
    key: 'products',
    title: 'Products',
    defaultOpen: true,
    items: [
      { path: '/products', icon: Package, label: 'Products' },
      { path: '/add-product', icon: PlusSquare, label: 'Add Product' },
    ],
  },
  {
    key: 'lead-gen',
    title: 'Lead Generation',
    defaultOpen: true,
    items: [
      { path: '/lead-discovery', icon: Search, label: 'Lead Discovery' },
      { path: '/campaigns', icon: Megaphone, label: 'Campaigns' },
      { path: '/outreach-queue', icon: Inbox, label: 'Outreach Queue' },
    ],
  },
  {
    key: 'system',
    title: 'System',
    defaultOpen: true,
    items: [
      { path: '/settings', icon: Settings, label: 'Settings' },
    ],
  },
]

function NavItem({ path, icon: Icon, label, open, onClick }) {
  const location = useLocation()
  const isActive = location.pathname === path
  return (
    <NavLink
      to={path}
      onClick={onClick}
      className={`nav-item group relative flex items-center gap-3 px-3 py-2 rounded-xl transition-colors ${
        isActive ? 'text-blue-600' : 'text-gray-600 hover:bg-gray-100'
      }`}
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
        className={`flex-shrink-0 relative z-10 transition-colors ${
          isActive ? 'text-blue-600' : 'text-gray-500 group-hover:text-gray-900'
        }`}
      />
      <AnimatePresence>
        {open && (
          <motion.span
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.15 }}
            className="relative z-10 text-sm font-medium flex-1"
          >
            {label}
          </motion.span>
        )}
      </AnimatePresence>
      {isActive && open && (
        <ChevronRight size={12} className="ml-auto text-blue-600 relative z-10" />
      )}
    </NavLink>
  )
}

function CollapsibleSection({ section, sidebarOpen, onMobileClose }) {
  const location = useLocation()
  const hasActive = section.items.some(i => i.path === location.pathname)
  const [expanded, setExpanded] = useState(section.defaultOpen)

  return (
    <div>
      {/* Section header — only shown when sidebar is expanded */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setExpanded(e => !e)}
            className="w-full flex items-center justify-between px-3 mb-1 group"
          >
            <span className={`text-[10px] font-semibold uppercase tracking-widest transition-colors ${
              hasActive ? 'text-blue-500' : 'text-gray-400 group-hover:text-gray-600'
            }`}>
              {section.title}
            </span>
            <motion.div animate={{ rotate: expanded ? 0 : -90 }} transition={{ duration: 0.2 }}>
              <ChevronDown size={11} className="text-gray-300 group-hover:text-gray-500" />
            </motion.div>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Items — always visible in icon-only mode, toggled in expanded mode */}
      <AnimatePresence initial={false}>
        {(!sidebarOpen || expanded) && (
          <motion.ul
            initial={sidebarOpen ? { height: 0, opacity: 0 } : false}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="space-y-0.5 overflow-hidden"
          >
            {section.items.map(item => (
              <li key={`${section.key}-${item.path}-${item.label}`}>
                <NavItem {...item} open={sidebarOpen} onClick={onMobileClose} />
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function Sidebar({ open, mobileOpen, onMobileClose }) {
  const sidebarContent = (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-gray-200">
        <img src="/favicon.png" alt="RDL Technologies" className="w-8 h-8 rounded-xl flex-shrink-0 object-contain" />
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2 }}
              className="flex flex-col"
            >
              <span className="text-sm font-bold text-gray-900 leading-none">RDL Sales </span>
              <span className="text-[10px] text-gray-500 font-medium mt-0.5">Admin Dashboard</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-4">
        {navSections.map(section => (
          <CollapsibleSection
            key={section.key}
            section={section}
            sidebarOpen={open}
            onMobileClose={onMobileClose}
          />
        ))}
      </nav>

      {/* Bottom user */}
      <div className="p-3 border-t border-gray-200">
        <NavLink
          to="/settings"
          onClick={onMobileClose}
          className="flex items-center gap-3 px-2 py-2 rounded-xl hover:bg-gray-100 transition-colors cursor-pointer w-full text-left"
        >
          <div
            className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold text-white shadow-sm"
            style={{ background: 'linear-gradient(135deg, #2563eb, #3b82f6)' }}
          >
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
                <p className="text-[10px] text-gray-500 truncate">admin@RDL Sales .io</p>
              </motion.div>
            )}
          </AnimatePresence>
        </NavLink>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop */}
      <motion.aside
        animate={{ width: open ? 260 : 72 }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
        className="fixed left-0 top-0 h-full z-30 hidden lg:block overflow-hidden border-r border-gray-200 bg-white"
      >
        {sidebarContent}
      </motion.aside>

      {/* Mobile */}
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
