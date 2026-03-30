import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar'
import TopNavbar from '../components/layout/TopNavbar'
import ParticleBackground from '../components/effects/ParticleBackground'

export default function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)

  return (
    <div className="relative min-h-screen bg-gray-50 overflow-hidden text-gray-900">
      {/* Animated background */}
      <ParticleBackground />

      {/* Gradient blobs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="blob1 absolute -top-40 -left-20 w-96 h-96 rounded-full opacity-[0.08]"
          style={{ background: 'radial-gradient(circle, rgba(97,114,243,0.8) 0%, transparent 70%)' }} />
        <div className="blob2 absolute top-1/2 -right-20 w-80 h-80 rounded-full opacity-[0.06]"
          style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.8) 0%, transparent 70%)' }} />
        <div className="blob1 absolute bottom-0 left-1/3 w-72 h-72 rounded-full opacity-[0.05]"
          style={{ background: 'radial-gradient(circle, rgba(6,182,212,0.8) 0%, transparent 70%)' }} />
      </div>

      {/* Mobile overlay */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 bg-gray-900/40 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <Sidebar
        open={sidebarOpen}
        mobileOpen={mobileSidebarOpen}
        onMobileClose={() => setMobileSidebarOpen(false)}
      />

      {/* Main area */}
      <div
        className="flex flex-col min-h-screen transition-all duration-300"
        style={{ marginLeft: sidebarOpen ? '260px' : '72px' }}
      >
        <TopNavbar
          onMenuClick={() => {
            if (window.innerWidth < 1024) {
              setMobileSidebarOpen(true)
            } else {
              setSidebarOpen(!sidebarOpen)
            }
          }}
          sidebarOpen={sidebarOpen}
        />
        <main className="flex-1 p-6 overflow-y-auto relative z-10">
          <Outlet />
        </main>
      </div>

      {/* Mobile layout override */}
      <style>{`
        @media (max-width: 1023px) {
          .main-content { margin-left: 0 !important; }
        }
      `}</style>
    </div>
  )
}
