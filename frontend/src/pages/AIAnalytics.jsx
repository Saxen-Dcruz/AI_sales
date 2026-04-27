import React, { useState, useEffect } from 'react'
import {
  Container,
  Typography,
  Box,
  Paper,
  Grid,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Chip,
  IconButton,
  Tooltip
} from '@mui/material'
import {
  TrendingUp,
  QueryStats,
  Timer,
  AttachMoney,
  OpenInNew,
  ErrorOutline,
  LibraryAdd
} from '@mui/icons-material'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { GetAIAnalyticsService, GetAILogsService } from '../services/ApiService'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip
} from 'recharts'

export default function AIAnalytics() {
  const navigate = useNavigate()
  const [summary, setSummary] = useState(null)
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      new Promise((resolve) => GetAIAnalyticsService(resolve, (s, e) => { console.error(e); resolve(null); })),
      new Promise((resolve) => GetAILogsService({ limit: 10 }, resolve, (s, e) => { console.error(e); resolve(null); }))
    ]).then(([summaryData, logsData]) => {
      setSummary(summaryData)
      if (logsData && logsData.items) {
        setLogs(logsData.items)
      }
      setLoading(false)
    })
  }, [])

  const stats = [
    { label: 'Total Queries', value: summary?.total_queries || 0, icon: QueryStats, color: '#6172f3' },
    { label: 'Total Cost (USD)', value: `$${summary?.total_cost_usd || 0}`, icon: AttachMoney, color: '#10b981' },
    { label: 'Avg Latency', value: `${summary?.avg_latency_ms || 0}ms`, icon: Timer, color: '#f59e0b' },
    { label: 'Input Tokens', value: summary?.total_input_tokens || 0, icon: TrendingUp, color: '#8b5cf6' },
  ]

  const sentimentColor = {
    POSITIVE: 'success',
    NEUTRAL: 'default',
    FRUSTRATED: 'error'
  }

  if (loading && !summary) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 20 }}>
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
          <Box>
            <Typography variant="h4" fontWeight={800} color="text.primary">AI Analytics</Typography>
            <Typography variant="body2" color="text.secondary">Real-time performance metrics for RAG and AI responses</Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button 
              variant="outlined" 
              startIcon={<ErrorOutline />}
              onClick={() => navigate('/gaps')}
              sx={{ borderRadius: 3 }}
            >
              Unanswered Queries
            </Button>
            <Button 
              variant="contained" 
              startIcon={<LibraryAdd />}
              onClick={() => navigate('/products')}
              sx={{ borderRadius: 3 }}
            >
              Add Knowledge
            </Button>
          </Box>
        </Box>

        {/* Stats Grid */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          {stats.map((s, i) => (
            <Grid item xs={12} sm={6} md={3} key={i}>
              <Paper elevation={0} sx={{ p: 3, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Box sx={{ p: 1.5, bgcolor: `${s.color}15`, borderRadius: 3 }}>
                    <s.icon sx={{ color: s.color }} />
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">{s.label}</Typography>
                    <Typography variant="h6" fontWeight={700}>{s.value}</Typography>
                  </Box>
                </Box>
              </Paper>
            </Grid>
          ))}
        </Grid>

        {/* Chart Section */}
        {logs.length > 0 && (
          <Paper elevation={0} sx={{ p: 3, mb: 4, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 3 }}>Latency Trend (Recent Queries)</Typography>
            <Box sx={{ height: 250 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={logs.slice().reverse()} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6172f3" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#6172f3" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f1f1" />
                  <XAxis hide />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#94a3b8' }} />
                  <RechartsTooltip />
                  <Area type="monotone" dataKey="latency_ms" stroke="#6172f3" fillOpacity={1} fill="url(#colorLatency)" />
                </AreaChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        )}

        {/* Logs Table */}
        <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>Detailed Query Logs</Typography>
        <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 4, overflow: 'hidden' }}>
          <Table>
            <TableHead sx={{ bgcolor: 'grey.50' }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>Question</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Standalone</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Sentiment</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Latency</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Cost</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Source</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {logs.length > 0 ? (
                logs.map((log) => (
                  <TableRow key={log.id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={500} sx={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {log.question}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">{new Date(log.created_at).toLocaleString()}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" sx={{ color: 'primary.main', bgcolor: 'primary.light', px: 1, py: 0.2, borderRadius: 1 }}>
                        {log.standalone_query || '-'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip label={log.sentiment} size="small" color={sentimentColor[log.sentiment] || 'default'} variant="tonal" sx={{ fontWeight: 600, fontSize: '0.7rem' }} />
                    </TableCell>
                    <TableCell><Typography variant="body2">{log.latency_ms}ms</Typography></TableCell>
                    <TableCell><Typography variant="body2" fontWeight={600}>${log.estimated_cost}</Typography></TableCell>
                    <TableCell align="right">
                      <Chip label={log.source} size="small" variant="outlined" sx={{ fontSize: '0.65rem' }} />
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 8 }}>
                    <Typography variant="body2" color="text.secondary">No query logs found.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>

      </motion.div>
    </Container>
  )
}
