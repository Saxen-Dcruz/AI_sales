import { useState, useEffect } from 'react'
import {
  Container, Typography, Box, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Button, Chip, CircularProgress,
  IconButton, Tooltip, Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  Tabs, Tab
} from '@mui/material'
import { HelpOutline, CheckCircle, Refresh as RefreshIcon } from '@mui/icons-material'
import { motion } from 'framer-motion'
import { GetEmailGapsService, ResolveEmailGapService, GetCallGapsService, ResolveCallGapService } from '../services/ApiService'

function flattenEmailGaps(emailItems) {
  const rows = []
  for (const email of emailItems) {
    email.gaps.forEach((gap, idx) => {
      if (!gap.resolved) {
        rows.push({
          email_id: email.email_id,
          gap_index: idx,
          question: gap.question,
          topic: gap.topic,
          product_name: gap.product_name,
          source: email.customer_email,
          subject: email.subject,
          received_at: email.received_at,
          type: 'email',
        })
      }
    })
  }
  return rows
}

function flattenCallGaps(callItems) {
  const rows = []
  for (const call of callItems) {
    const gaps = call.followup_gaps || []
    gaps.forEach((gap, idx) => {
      const question = typeof gap === 'string' ? gap : gap.question
      if (!gap.resolved) {
        rows.push({
          call_id: call.id,
          gap_index: idx,
          question,
          topic: typeof gap === 'object' ? gap.topic : 'general',
          product_name: typeof gap === 'object' ? gap.product_name : null,
          source: call.phone_number || 'Unknown',
          type: 'call',
        })
      }
    })
  }
  return rows
}

export default function GapsPage() {
  const [tab, setTab] = useState(0)
  const [emailGaps, setEmailGaps] = useState([])
  const [callGaps, setCallGaps] = useState([])
  const [loading, setLoading] = useState(true)
  const [resolveDialogOpen, setResolveDialogOpen] = useState(false)
  const [selectedGap, setSelectedGap] = useState(null)
  const [answer, setAnswer] = useState('')
  const [resolving, setResolving] = useState(false)

  const fetchGaps = () => {
    setLoading(true)
    Promise.all([
      new Promise(res => GetEmailGapsService(res, () => res(null))),
      new Promise(res => GetCallGapsService(res, () => res(null))),
    ]).then(([emailData, callData]) => {
      setEmailGaps(flattenEmailGaps(emailData?.items || []))
      setCallGaps(flattenCallGaps(callData?.items || []))
      setLoading(false)
    })
  }

  useEffect(() => { fetchGaps() }, [])

  const openResolve = (gap) => {
    setSelectedGap(gap)
    setAnswer('')
    setResolveDialogOpen(true)
  }

  const handleResolve = () => {
    if (!selectedGap || !answer.trim()) return
    setResolving(true)

    const onSuccess = () => {
      if (selectedGap.type === 'email') {
        setEmailGaps(prev => prev.filter(
          g => !(g.email_id === selectedGap.email_id && g.gap_index === selectedGap.gap_index)
        ))
      } else {
        setCallGaps(prev => prev.filter(
          g => !(g.call_id === selectedGap.call_id && g.gap_index === selectedGap.gap_index)
        ))
      }
      setResolveDialogOpen(false)
      setResolving(false)
    }

    const onError = (_s, err) => {
      alert('Resolution failed: ' + err)
      setResolving(false)
    }

    if (selectedGap.type === 'email') {
      ResolveEmailGapService(selectedGap.email_id, selectedGap.gap_index, answer, onSuccess, onError)
    } else {
      ResolveCallGapService(selectedGap.call_id, selectedGap.gap_index, answer, onSuccess, onError)
    }
  }

  const rows = tab === 0 ? emailGaps : callGaps
  const total = emailGaps.length + callGaps.length

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box>
            <Typography variant="h4" fontWeight={800} color="text.primary">Knowledge Gaps</Typography>
            <Typography variant="body2" color="text.secondary">
              {total} unresolved — questions the AI couldn't answer
            </Typography>
          </Box>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchGaps} sx={{ bgcolor: 'grey.100' }}><RefreshIcon /></IconButton>
          </Tooltip>
        </Box>

        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
          <Tab label={`Email Gaps (${emailGaps.length})`} />
          <Tab label={`Call Gaps (${callGaps.length})`} />
        </Tabs>

        <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 4, overflow: 'hidden' }}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}><CircularProgress /></Box>
          ) : (
            <Table>
              <TableHead sx={{ bgcolor: 'grey.50' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Question</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Topic</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Product</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>{tab === 0 ? 'From' : 'Phone'}</TableCell>
                  {tab === 0 && <TableCell sx={{ fontWeight: 700 }}>Subject</TableCell>}
                  <TableCell sx={{ fontWeight: 700 }} align="right">Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.length > 0 ? (
                  rows.map((gap, i) => (
                    <TableRow key={i} hover>
                      <TableCell sx={{ maxWidth: 320 }}>
                        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                          <HelpOutline color="warning" sx={{ mt: 0.3, flexShrink: 0 }} fontSize="small" />
                          <Typography variant="body2" fontWeight={500}>{gap.question}</Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip label={gap.topic || 'general'} size="small" variant="tonal" color="primary" />
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">{gap.product_name || '—'}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">{gap.source}</Typography>
                      </TableCell>
                      {tab === 0 && (
                        <TableCell sx={{ maxWidth: 180 }}>
                          <Typography variant="caption" color="text.secondary" noWrap>{gap.subject}</Typography>
                        </TableCell>
                      )}
                      <TableCell align="right">
                        <Button
                          variant="contained"
                          size="small"
                          color="success"
                          startIcon={<CheckCircle />}
                          onClick={() => openResolve(gap)}
                        >
                          Resolve
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={tab === 0 ? 6 : 5} align="center" sx={{ py: 8 }}>
                      <Typography variant="body2" color="text.secondary">No unresolved gaps. All clear!</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </TableContainer>

        <Dialog open={resolveDialogOpen} onClose={() => setResolveDialogOpen(false)} fullWidth maxWidth="sm"
          PaperProps={{ sx: { borderRadius: 3 } }}>
          <DialogTitle sx={{ fontWeight: 700 }}>Resolve Gap</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Answering: <strong>"{selectedGap?.question}"</strong>
              {selectedGap?.product_name && (
                <> — <em>{selectedGap.product_name}</em></>
              )}
            </Typography>
            <TextField
              fullWidth
              label="Answer"
              multiline
              rows={4}
              variant="outlined"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Provide the answer to embed into the RAG knowledge base..."
            />
          </DialogContent>
          <DialogActions sx={{ p: 2.5 }}>
            <Button onClick={() => setResolveDialogOpen(false)} color="inherit">Cancel</Button>
            <Button onClick={handleResolve} variant="contained" color="success" disabled={!answer.trim() || resolving}>
              {resolving ? 'Saving...' : 'Save to Knowledge Base'}
            </Button>
          </DialogActions>
        </Dialog>

      </motion.div>
    </Container>
  )
}
