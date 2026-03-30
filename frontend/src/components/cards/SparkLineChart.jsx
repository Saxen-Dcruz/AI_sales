import { ResponsiveContainer, AreaChart, Area, Tooltip } from 'recharts'

export function SparkLineChart({ data, color }) {
  const chartData = data.map((v, i) => ({ v, i }))
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
        <defs>
          <linearGradient id={`spark-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Tooltip
          content={({ active, payload }) =>
            active && payload?.length ? (
              <div className="bg-white border border-gray-200 shadow-sm rounded-lg px-2 py-1 text-xs text-gray-900">
                {payload[0].value}
              </div>
            ) : null
          }
        />
        <Area
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#spark-${color.replace('#', '')})`}
          dot={false}
          activeDot={{ r: 3, fill: color }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
