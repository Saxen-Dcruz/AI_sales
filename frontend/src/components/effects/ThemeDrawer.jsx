import { motion, AnimatePresence } from 'framer-motion'
import { Sun, Moon, X, Monitor } from 'lucide-react'
import { useState } from 'react'

export default function ThemeDrawer({ isOpen, onClose }) {
  const [theme, setTheme] = useState('light')

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-gray-900/20 backdrop-blur-sm z-40"
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 h-full w-80 bg-white shadow-2xl z-50 flex flex-col border-l border-gray-200"
          >
            <div className="flex items-center justify-between p-6 border-b border-gray-100 bg-white">
              <h2 className="text-lg font-semibold text-gray-900">Theme Settings</h2>
              <button onClick={onClose} className="p-2 -mr-2 text-gray-400 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors">
                <X size={20} />
              </button>
            </div>
            <div className="p-6 flex-1 bg-gray-50/50">
              <p className="text-sm text-gray-500 mb-5">Choose your preferred theme appearance.</p>
              <div className="space-y-3">
                {[
                  { id: 'light', icon: Sun, label: 'Light Mode' },
                  { id: 'dark', icon: Moon, label: 'Dark Mode' },
                  { id: 'system', icon: Monitor, label: 'System Preference' },
                ].map(({ id, icon: Icon, label }) => (
                  <button
                    key={id}
                    onClick={() => setTheme(id)}
                    className={`w-full flex items-center gap-3 p-4 rounded-xl border-2 transition-all ${
                      theme === id 
                        ? 'border-blue-500 bg-blue-50 text-blue-700 shadow-sm' 
                        : 'border-transparent bg-white hover:border-gray-200 shadow-sm text-gray-700'
                    }`}
                  >
                    <div className={`p-2 rounded-lg ${theme === id ? 'bg-blue-100' : 'bg-gray-100'}`}>
                      <Icon size={18} className={theme === id ? 'text-blue-600' : 'text-gray-500'} />
                    </div>
                    <span className="font-semibold text-sm">{label}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="p-6 border-t border-gray-100 bg-white">
               <button onClick={onClose} className="w-full btn-primary bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-xl font-medium shadow-md transition-all">
                 Apply Settings
               </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
