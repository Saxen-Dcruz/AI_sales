import { useState } from 'react'
import { motion } from 'framer-motion'
import { Zap, Moon } from 'lucide-react'
import BackgroundAnimation from '../components/effects/BackgroundAnimation'
import LoginForm from '../components/auth/LoginForm'
import ThemeDrawer from '../components/effects/ThemeDrawer'

export default function LoginPage() {
  const [isThemeDrawerOpen, setIsThemeDrawerOpen] = useState(false)

  return (
    <div className="min-h-screen w-full flex bg-gray-50 relative overflow-hidden font-sans">
      {/* 3D Animated Background */}
      <BackgroundAnimation />

      {/* Theme Settings Toggle */}
      <div className="absolute top-6 right-6 z-20">
        <button
          onClick={() => setIsThemeDrawerOpen(true)}
          className="p-3 bg-white/80 backdrop-blur-md border border-gray-200 rounded-full shadow-sm text-gray-600 hover:text-blue-600 hover:border-blue-300 hover:shadow-md transition-all"
        >
          <Moon size={22} className="opacity-80" />
        </button>
      </div>

      <ThemeDrawer isOpen={isThemeDrawerOpen} onClose={() => setIsThemeDrawerOpen(false)} />

      {/* Main Content Layout */}
      <div className="relative z-10 flex flex-col items-center justify-center w-full min-h-screen p-6 sm:p-12">
        
        {/* Logo */}
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="flex items-center gap-3 mb-8"
        >
          <div className="w-10 h-10 rounded-2xl flex items-center justify-center bg-gradient-to-br from-blue-500 to-indigo-500 shadow-md">
            <Zap size={20} className="text-white" />
          </div>
          <span className="text-2xl font-bold tracking-tight text-gray-900">NexusAI</span>
        </motion.div>

        {/* Form wrapper */}
        <div className="w-full max-w-md perspective-1000">
          <LoginForm />
        </div>

      </div>
    </div>
  )
}
