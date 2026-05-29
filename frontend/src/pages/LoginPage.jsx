import { motion } from 'framer-motion'
import { Zap } from 'lucide-react'
import LoginForm from '../components/auth/LoginForm'
import BackgroundAnimation from '../components/effects/BackgroundAnimation'

export default function LoginPage() {
  return (
    <div className="min-h-screen w-full flex bg-white relative overflow-hidden font-sans">
      <BackgroundAnimation />

      <div className="relative z-10 flex flex-col items-center justify-center w-full min-h-screen p-6 sm:p-12">

        {/* Logo */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="flex items-center gap-3 mb-8"
        >
          <div className="w-10 h-10 rounded-2xl flex items-center justify-center bg-gradient-to-br from-indigo-500 to-violet-500 shadow-lg shadow-indigo-200">
            <Zap size={20} className="text-white" />
          </div>
          <span className="text-2xl font-bold tracking-tight text-gray-900">RDL Sales</span>
        </motion.div>

        {/* Form */}
        <div className="w-full max-w-md">
          <LoginForm />
        </div>

      </div>
    </div>
  )
}
