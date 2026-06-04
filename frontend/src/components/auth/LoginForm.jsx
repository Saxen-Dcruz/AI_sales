import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, Eye, EyeOff, Loader2, Lock, Mail } from 'lucide-react'
import { useState } from 'react'
import ApplicationStore from '../../utils/ApplicationStore'

import { GetCurrentUserService, LoginService } from '../../services/ApiService'

export default function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [focusedInput, setFocusedInput] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!email || !password) {
      setError('Please fill in all fields')
      return
    }

    setIsLoading(true)

    try {
      const response = await LoginService({ email, password })
      const data = await response.json()

      if (!response.ok) {
        setError(data.detail || 'Invalid email or password')
        setIsLoading(false)
        return
      }

      ApplicationStore().setStorage("userDetails", {
        accessToken: data.access_token,
        userDetails: { id: "", email: email, userRole: "", companyCode: "", semesterId: "", branch: "", instituteid: "" }
      })

      GetCurrentUserService(
        (userData) => {
          ApplicationStore().setStorage("userDetails", {
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
            userDetails: {
              id: userData.id,
              email: userData.email,
              userRole: userData.is_superuser ? "Admin" : "User",
              companyCode: "RDL",
              semesterId: "N/A",
              branch: "Main",
              instituteid: "INST001"
            }
          })
          setIsLoading(false)
          window.location.href = '/dashboard'
        },
        (status, msg) => {
          setError(msg || 'Failed to fetch user profile')
          setIsLoading(false)
        }
      )
    } catch (err) {
      setError('Network error or server unavailable')
      setIsLoading(false)
    }
  }

  // Animation variants
  const formVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.6,
        ease: [0.22, 1, 0.36, 1],
        staggerChildren: 0.1
      }
    }
  }

  const itemVariants = {
    hidden: { opacity: 0, y: 15 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' } }
  }

  return (
    <motion.div variants={formVariants} initial="hidden" animate="visible" className="w-full max-w-md relative z-20">

      {/* Subtle glow blobs */}
      <div className="absolute -top-10 -left-10 w-40 h-40 bg-indigo-100 rounded-full blur-[50px] pointer-events-none opacity-60" />
      <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-violet-100 rounded-full blur-[50px] pointer-events-none opacity-60" />

      <div className="relative p-8 rounded-3xl border border-gray-200/80 overflow-hidden bg-white/85"
        style={{
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          boxShadow: '0 8px 40px rgba(99,102,241,0.08), 0 1px 0 rgba(255,255,255,0.9) inset'
        }}
      >
        <motion.div variants={itemVariants} className="text-center mb-8">
          <h2 className="text-3xl font-bold tracking-tight text-gray-900 mb-2">Welcome Back</h2>
          <p className="text-sm text-gray-500">Sign in to your RDL Sales admin dashboard</p>
        </motion.div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Email */}
          <motion.div variants={itemVariants} className="space-y-1.5 relative">
            <label className="text-sm font-medium text-gray-700 ml-1">Work Email</label>
            <div className="relative group">
              <Mail size={18} className={`absolute text-gray-400 left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-300 ${focusedInput === 'email' ? 'text-blue-500' : ''}`} />
              <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                onFocus={() => setFocusedInput('email')} onBlur={() => setFocusedInput(null)}
                className="w-full pl-11 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 outline-none transition-all duration-300 focus:border-blue-500 hover:border-gray-300"
                placeholder="name@company.com"
                style={{ boxShadow: focusedInput === 'email' ? '0 0 0 3px rgba(99,102,241,0.12)' : 'none' }} />
            </div>
          </motion.div>

          {/* Password */}
          <motion.div variants={itemVariants} className="space-y-1.5 relative">
            <div className="flex items-center justify-between ml-1">
              <label className="text-sm font-medium text-gray-700">Password</label>
              <a href="#" className="text-xs text-blue-600 font-medium hover:text-blue-500 transition-colors">Forgot password?</a>
            </div>
            <div className="relative group">
              <Lock size={18} className={`absolute text-gray-400 left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-300 ${focusedInput === 'password' ? 'text-blue-500' : ''}`} />
              <input type={showPassword ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)}
                onFocus={() => setFocusedInput('password')} onBlur={() => setFocusedInput(null)}
                className="w-full pl-11 pr-11 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 outline-none transition-all duration-300 focus:border-blue-500 hover:border-gray-300"
                placeholder="••••••••••••"
                style={{ boxShadow: focusedInput === 'password' ? '0 0 0 3px rgba(99,102,241,0.12)' : 'none' }} />
              <button type="button" onClick={() => setShowPassword(!showPassword)} tabIndex={-1}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors">
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </motion.div>

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0, marginTop: 0 }}
                animate={{ opacity: 1, height: 'auto', marginTop: 12 }}
                exit={{ opacity: 0, height: 0, marginTop: 0 }}
                className="overflow-hidden"
              >
                <div className="px-3 py-2 border border-red-200 bg-red-50 rounded-lg">
                  <p className="text-xs text-red-600 font-medium text-center">{error}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Remember me */}
          <motion.div variants={itemVariants} className="flex items-center gap-2 ml-1">
            <div className="relative flex items-center">
              <input type="checkbox" id="remember" className="peer w-4 h-4 opacity-0 absolute cursor-pointer" />
              <div className="w-4 h-4 rounded border border-gray-300 bg-white peer-checked:bg-blue-600 peer-checked:border-blue-600 flex items-center justify-center transition-colors">
                <svg className="w-2.5 h-2.5 text-white opacity-0 peer-checked:opacity-100 transition-opacity" viewBox="0 0 12 10" fill="none">
                  <path d="M1 5L4.5 8.5L11 1.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
            </div>
            <label htmlFor="remember" className="text-sm text-gray-600 cursor-pointer select-none">Remember me for 30 days</label>
          </motion.div>

          {/* Submit */}
          <motion.div variants={itemVariants} className="pt-2">
            <button type="submit" disabled={isLoading}
              className="w-full relative group h-12 bg-blue-600 text-white font-medium rounded-xl overflow-hidden transition-all duration-300 hover:bg-blue-700 active:scale-95 disabled:opacity-70 shadow-md shadow-blue-200"
            >
              <div className="absolute inset-0 flex items-center justify-center gap-2">
                {isLoading ? (
                  <><Loader2 size={18} className="animate-spin" /><span>Signing in…</span></>
                ) : (
                  <><span>Sign In</span><ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" /></>
                )}
              </div>
            </button>
          </motion.div>

          {/* <motion.div variants={itemVariants} className="relative py-4">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/10" />
            </div> */}
          {/* <div className="relative flex justify-center text-xs">
              <span className="bg-transparent px-2 text-dark-500 backdrop-blur-3xl">or continue with</span>
            </div> */}
          {/* </motion.div> */}

          {/* {/* Google SSO */}
          {/* <motion.div variants={itemVariants}>
            <button
              type="button"
              className="w-full h-11 flex items-center justify-center gap-3 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-xl text-sm font-medium text-white transition-all duration-300"
            >
              <svg viewBox="0 0 24 24" className="w-4 h-4" xmlns="http://www.w3.org/2000/svg">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              Sign in with Google
            </button>
          </motion.div> */}
        </form>
      </div>

      {/* Footer minimal terms */}
      {/* <motion.div variants={itemVariants} className="mt-8 text-center text-xs text-dark-500">
        By continuing, you agree to RDL Sales 's{' '}
        <a href="#" className="text-dark-400 hover:text-primary-400 transition-colors">Terms of Service</a> and{' '}
        <a href="#" className="text-dark-400 hover:text-primary-400 transition-colors">Privacy Policy</a>.
      </motion.div> */}
    </motion.div>
  )
}
