import { useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { SparkLineChart } from './SparkLineChart'

export default function AnalyticsCard({ title, value, change, changeLabel, icon: Icon, color, data, prefix = '', suffix = '' }) {
  const cardRef = useRef(null)
  const [tilt, setTilt] = useState({ x: 0, y: 0 })
  const [glowPos, setGlowPos] = useState({ x: 50, y: 50 })
  const [hovered, setHovered] = useState(false)

  const handleMouseMove = (e) => {
    const rect = cardRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    const cx = rect.width / 2
    const cy = rect.height / 2
    setTilt({
      x: ((y - cy) / cy) * -8,
      y: ((x - cx) / cx) * 8,
    })
    setGlowPos({ x: (x / rect.width) * 100, y: (y / rect.height) * 100 })
  }

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0 })
    setHovered(false)
  }

  const isPositive = change > 0
  const isNeutral = change === 0

  const colorMap = {
    blue: { light: 'rgba(79,142,247,0.15)', border: 'rgba(79,142,247,0.3)', icon: '#4f8ef7', glow: 'rgba(79,142,247,0.2)' },
    purple: { light: 'rgba(139,92,246,0.15)', border: 'rgba(139,92,246,0.3)', icon: '#8b5cf6', glow: 'rgba(139,92,246,0.2)' },
    cyan: { light: 'rgba(6,182,212,0.15)', border: 'rgba(6,182,212,0.3)', icon: '#06b6d4', glow: 'rgba(6,182,212,0.2)' },
    green: { light: 'rgba(16,185,129,0.15)', border: 'rgba(16,185,129,0.3)', icon: '#10b981', glow: 'rgba(16,185,129,0.2)' },
    orange: { light: 'rgba(245,158,11,0.15)', border: 'rgba(245,158,11,0.3)', icon: '#f59e0b', glow: 'rgba(245,158,11,0.2)' },
    red: { light: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.3)', icon: '#ef4444', glow: 'rgba(239,68,68,0.2)' },
    pink: { light: 'rgba(236,72,153,0.15)', border: 'rgba(236,72,153,0.3)', icon: '#ec4899', glow: 'rgba(236,72,153,0.2)' },
  }
  const c = colorMap[color] || colorMap.blue

  return (
    <motion.div
      ref={cardRef}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={handleMouseLeave}
      style={{
        transform: `perspective(1000px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
        transition: hovered ? 'transform 0.1s ease' : 'transform 0.4s ease',
      }}
      className="relative rounded-2xl p-5 overflow-hidden cursor-default"
    >
      {/* Glass background */}
      <div className="absolute inset-0 rounded-2xl bg-white shadow-sm"
        style={{
          border: `1px solid ${hovered ? c.border : 'rgba(229,231,235,1)'}`,
          transition: 'border-color 0.3s ease, box-shadow 0.3s ease',
          boxShadow: hovered ? '0 4px 12px rgba(0,0,0,0.05)' : '0 1px 2px rgba(0,0,0,0.05)',
        }} />

      {/* Mouse glow */}
      {hovered && (
        <div className="absolute inset-0 rounded-2xl pointer-events-none transition-opacity duration-300"
          style={{
            background: `radial-gradient(200px circle at ${glowPos.x}% ${glowPos.y}%, ${c.glow}, transparent)`,
          }} />
      )}

      <div className="relative z-10">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">{title}</p>
            <div className="flex items-baseline gap-1">
              {prefix && <span className="text-sm font-medium text-gray-400">{prefix}</span>}
              <span className="text-2xl font-bold text-gray-900">{value}</span>
              {suffix && <span className="text-sm font-medium text-gray-400">{suffix}</span>}
            </div>
          </div>
          <div className="p-2.5 rounded-xl"
            style={{ background: c.light }}>
            <Icon size={18} style={{ color: c.icon }} />
          </div>
        </div>

        {/* Sparkline */}
        {data && (
          <div className="mb-3 h-12">
            <SparkLineChart data={data} color={c.icon} />
          </div>
        )}

        {/* Trend */}
        <div className="flex items-center gap-1.5">
          {isNeutral ? (
            <Minus size={12} className="text-gray-400" />
          ) : isPositive ? (
            <TrendingUp size={12} className="text-accent-green" />
          ) : (
            <TrendingDown size={12} className="text-accent-red" />
          )}
          <span className={`text-xs font-semibold ${isNeutral ? 'text-gray-500' : isPositive ? 'text-accent-green' : 'text-accent-red'}`}>
            {isPositive ? '+' : ''}{change}%
          </span>
          {changeLabel && (
            <span className="text-xs text-gray-400">{changeLabel}</span>
          )}
        </div>
      </div>
    </motion.div>
  )
}
