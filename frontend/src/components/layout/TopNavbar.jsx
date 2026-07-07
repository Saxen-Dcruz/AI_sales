import { AnimatePresence, motion } from 'framer-motion'
import { Bell, CheckCircle2, ChevronDown, LogOut, Menu, Settings as SettingsIcon, Shield, User, Users } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import ApplicationStore from '../../utils/ApplicationStore'
import { GetCurrentUserService, LogoutService } from '../../services/ApiService'

const pageTitles = {
  '/dashboard':      { title: 'Dashboard',          sub: 'Pipeline overview & key metrics' },
  '/gmail':          { title: 'Gmail Inbox',         sub: 'AI-driven email management' },
  '/gmail-analytics':{ title: 'Email Analytics',     sub: 'Pipeline performance & SLA compliance' },
  '/calls':          { title: 'Call Analytics',      sub: 'Inbound & outbound performance' },
  '/ai-analytics':   { title: 'AI Analytics',        sub: 'Model performance & automation insights' },
  '/linkedin':       { title: 'LinkedIn Analytics',  sub: 'Lead generation insights' },
  '/users':          { title: 'Team Analytics',      sub: 'Engagement & behaviour metrics' },
  '/leads':          { title: 'Lead Management',     sub: 'Pipeline & qualification tracking' },
  '/gaps':           { title: 'Knowledge Gaps',      sub: 'Unanswered questions & missing product info' },
  '/feedback':       { title: 'User Feedback',       sub: 'Sentiment & feature requests' },
  '/ai-logs':        { title: 'AI Call Logs',        sub: 'Automated call history' },
  '/calendar':       { title: 'Calendar',            sub: 'Meetings & follow-up schedule' },
  '/products':       { title: 'Products',            sub: 'Product catalogue management' },
  '/add-product':    { title: 'Add Product',         sub: 'Create a new product listing' },
  '/settings':         { title: 'Settings',            sub: 'Account & system configuration' },
  '/user-management':  { title: 'User Management',     sub: 'Manage team accounts & permissions' },
}

const dummyNotifications = [
  { id: 1, title: 'New lead assigned', time: '5m ago', unread: true },
  { id: 2, title: 'System update completed', time: '1h ago', unread: true },
  { id: 3, title: 'Weekly report ready', time: '2h ago', unread: false },
]

export default function TopNavbar({ onMenuClick, sidebarOpen }) {
  const location = useLocation()
  const cachedDetails = (ApplicationStore().getStorage("userDetails") || {}).userDetails || {};
  const [userDetails, setUserDetails] = useState(cachedDetails)
  const email = userDetails.email || "admin@RDL Sales .io";
  const name = email.split('@')[0];
  const initials = name.substring(0, 2).toUpperCase();
  const isSuperAdmin = userDetails.userRole === "Admin";
  const navigate = useNavigate()

  // The cached profile snapshot (sessionStorage) is written once at login and can drift
  // from the actual session — e.g. logging in as a different account in another tab
  // shares the same auth cookie but not this tab's cached display. Refresh against the
  // live session on mount so the badge/role shown here can never lie about who — and
  // what permissions — the current requests are actually running as.
  useEffect(() => {
    GetCurrentUserService(
      (data) => {
        const fresh = { ...cachedDetails, id: data.id, email: data.email, userRole: data.is_superuser ? "Admin" : "User" }
        setUserDetails(fresh)
        const existing = ApplicationStore().getStorage("userDetails") || {}
        ApplicationStore().setStorage("userDetails", { ...existing, userDetails: fresh })
      },
      () => {}
    )
  }, [])
  const page = pageTitles[location.pathname] || { title: location.pathname.replace('/', '').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Dashboard', sub: '' }

  const [showNotifications, setShowNotifications] = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [notifications, setNotifications] = useState(dummyNotifications)

  const searchInputRef = useRef(null)
  const notificationsRef = useRef(null)
  const profileRef = useRef(null)

  // Handle click outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (notificationsRef.current && !notificationsRef.current.contains(event.target)) {
        setShowNotifications(false)
      }
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setShowProfile(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Handle Cmd+K / Ctrl+K shortcut
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        searchInputRef.current?.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  const unreadCount = notifications.filter(n => n.unread).length

  const markAllAsRead = () => {
    setNotifications(notifications.map(n => ({ ...n, unread: false })))
  }

  const handleSignOut = () => {
    const goToLogin = () => { ApplicationStore().clearStorage(); navigate('/login') }
    // Revoke the refresh token and clear auth cookies server-side — without this the
    // access/refresh token cookies stay valid and this browser remains signed in.
    LogoutService(null, goToLogin, goToLogin)
  }

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


        {/* Notifications */}
        <div className="relative" ref={notificationsRef}>
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className={`relative p-2 rounded-xl transition-all ${showNotifications ? 'bg-blue-50 text-blue-600' : 'hover:bg-gray-100 text-gray-500 hover:text-gray-900'}`}
          >
            <Bell size={16} />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-accent-red rounded-full ring-2 ring-white" />
            )}
          </button>

          <AnimatePresence>
            {showNotifications && (
              <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 10, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 mt-2 w-80 bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden origin-top-right"
              >
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50/50">
                  <span className="text-sm font-semibold text-gray-900">Notifications</span>
                  {unreadCount > 0 && (
                    <button
                      onClick={markAllAsRead}
                      className="text-xs text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1 transition-colors"
                    >
                      <CheckCircle2 size={12} />
                      Mark all read
                    </button>
                  )}
                </div>
                <div className="max-h-[320px] overflow-y-auto">
                  {notifications.map(notification => (
                    <div
                      key={notification.id}
                      className={`px-4 py-3 border-b border-gray-50/50 hover:bg-gray-50 transition-colors cursor-pointer ${notification.unread ? 'bg-blue-50/30' : ''}`}
                    >
                      <div className="flex justify-between items-start mb-1 gap-2">
                        <span className={`text-sm ${notification.unread ? 'font-semibold text-gray-900' : 'text-gray-700'}`}>
                          {notification.title}
                        </span>
                        {notification.unread && (
                          <span className="w-2 h-2 bg-blue-600 rounded-full mt-1.5 flex-shrink-0" />
                        )}
                      </div>
                      <span className="text-xs text-gray-500">{notification.time}</span>
                    </div>
                  ))}
                  {notifications.length === 0 && (
                    <div className="px-4 py-8 text-center text-sm text-gray-500">
                      No notifications
                    </div>
                  )}
                </div>
                <div className="p-2 border-t border-gray-100 text-center">
                  <button className="text-xs font-medium text-blue-600 hover:text-blue-700 w-full py-1.5 rounded-lg hover:bg-blue-50 transition-colors">
                    View all notifications
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>


        {/* User */}
        <div className="relative" ref={profileRef}>
          <button
            onClick={() => setShowProfile(!showProfile)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-xl transition-all ${showProfile ? 'bg-gray-100' : 'hover:bg-gray-100'}`}
          >
            <div className="relative">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shadow-sm"
                style={{ background: isSuperAdmin ? 'linear-gradient(135deg, #7c3aed, #a855f7)' : 'linear-gradient(135deg, #2563eb, #3b82f6)' }}>
                {initials}
              </div>
              {isSuperAdmin && (
                <span className="absolute -bottom-1 -right-1 w-3.5 h-3.5 bg-violet-600 rounded-full flex items-center justify-center ring-2 ring-white">
                  <Shield size={7} className="text-white" />
                </span>
              )}
            </div>
            <ChevronDown size={12} className={`text-gray-500 hidden sm:block transition-transform duration-200 ${showProfile ? 'rotate-180' : ''}`} />
          </button>

          <AnimatePresence>
            {showProfile && (
              <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 10, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 mt-2 w-56 bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden origin-top-right"
              >
                <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-gray-900">{name}</p>
                    {isSuperAdmin && (
                      <span className="inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700">
                        <Shield size={8} />SUPER ADMIN
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">{email}</p>
                </div>
                <div className="p-2 space-y-0.5">
                  <Link
                    to="/settings"
                    onClick={() => setShowProfile(false)}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900 rounded-xl transition-colors"
                  >
                    <User size={14} className="text-gray-400" />
                    Profile
                  </Link>
                  <Link
                    to="/settings"
                    onClick={() => setShowProfile(false)}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900 rounded-xl transition-colors"
                  >
                    <SettingsIcon size={14} className="text-gray-400" />
                    Settings
                  </Link>
                  {isSuperAdmin && (
                    <Link
                      to="/user-management"
                      onClick={() => setShowProfile(false)}
                      className="flex items-center gap-2 px-3 py-2 text-sm text-violet-700 hover:bg-violet-50 rounded-xl transition-colors"
                    >
                      <Users size={14} className="text-violet-500" />
                      Manage Users
                    </Link>
                  )}
                </div>
                <div className="p-2 border-t border-gray-100">
                  <button
                    onClick={handleSignOut}
                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 hover:text-red-700 rounded-xl transition-colors"
                  >
                    <LogOut size={14} className="text-red-500" />
                    Sign out
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

      </div>
    </header>
  )
}
