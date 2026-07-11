import { useState, useEffect } from 'react'
import {
  Container, Typography, Box, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Button, Chip, CircularProgress,
  IconButton, Tooltip, Dialog, DialogTitle, DialogContent,
  Tabs, Tab
} from '@mui/material'
import { HelpOutline, CheckCircle, Refresh as RefreshIcon } from '@mui/icons-material'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  GetEmailGapsService, ResolveEmailGapService,
  GetCallGapsService,  ResolveCallGapService,
  GetWhatsAppGapsService, ResolveWhatsAppGapService,
} from '../services/ApiService'
import GapResolveForm from '../components/GapResolveForm'

// ── Flatten helpers ────────────────────────────────────────────────────────────

function flattenEmailGaps(emailItems) {
  const rows = []
  for (const email of emailItems) {
    (email.gaps || []).forEach((gap, idx) => {
      if (!gap.resolved) {
        rows.push({
          email_id:    email.email_id,
          gap_index:   idx,
          question:    gap.question,
          topic:       gap.topic,
          product_name: gap.product_name,
          product_id:  gap.product_id,
          source:      email.customer_email,
          subject:     email.subject,
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
          call_id:     call.id,
          gap_index:   idx,
          question,
          topic:       typeof gap === 'object' ? gap.topic        : 'general',
          product_name: typeof gap === 'object' ? gap.product_name : null,
          product_id:  typeof gap === 'object' ? gap.product_id   : null,
          source:      call.phone_number || 'Unknown',
          type: 'call',
        })
      }
    })
  }
  return rows
}

function flattenWhatsAppGaps(waItems) {
  const rows = []
  for (const msg of waItems) {
    (msg.gaps || []).forEach((gap, idx) => {
      if (!gap.resolved) {
        rows.push({
          message_id:  msg.message_id,
          gap_index:   idx,
          question:    gap.question,
          topic:       gap.topic,
          product_name: gap.product_name,
          product_id:  gap.product_id,
          source:      msg.from_number,
          body:        msg.body,
          received_at: msg.received_at,
          type: 'whatsapp',
        })
      }
    })
  }
  return rows
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function GapsPage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState(0)
  const [emailGaps,    setEmailGaps]    = useState([])
  const [callGaps,     setCallGaps]     = useState([])
  const [whatsappGaps, setWhatsAppGaps] = useState([])
  const [loading,      setLoading]      = useState(true)
  const [resolveDialogOpen, setResolveDialogOpen] = useState(false)
  const [selectedGap,  setSelectedGap]  = useState(null)
  const [resolving,    setResolving]    = useState(false)

  const fetchGaps = () => {
    setLoading(true)
    Promise.all([
      new Promise(res => GetEmailGapsService(res,       () => res(null))),
      new Promise(res => GetCallGapsService(res,        () => res(null))),
      new Promise(res => GetWhatsAppGapsService(res,    () => res(null))),
    ]).then(([emailData, callData, waData]) => {
      setEmailGaps(flattenEmailGaps(emailData?.items || []))
      setCallGaps(flattenCallGaps(callData?.items   || []))
      setWhatsAppGaps(flattenWhatsAppGaps(waData?.items || []))
      setLoading(false)
    })
  }

  useEffect(() => { fetchGaps() }, [])

  const openResolve = (gap) => {
    setSelectedGap(gap)
    setResolveDialogOpen(true)
  }

  const handleResolve = (answer, category, productId) => {
    if (!selectedGap || !answer.trim()) return
    setResolving(true)

    const onSuccess = () => {
      if (selectedGap.type === 'email') {
        setEmailGaps(prev => prev.filter(
          g => !(g.email_id === selectedGap.email_id && g.gap_index === selectedGap.gap_index)
        ))
      } else if (selectedGap.type === 'call') {
        setCallGaps(prev => prev.filter(
          g => !(g.call_id === selectedGap.call_id && g.gap_index === selectedGap.gap_index)
        ))
      } else {
        setWhatsAppGaps(prev => prev.filter(
          g => !(g.message_id === selectedGap.message_id && g.gap_index === selectedGap.gap_index)
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
      ResolveEmailGapService(selectedGap.email_id, selectedGap.gap_index, answer, category, productId, onSuccess, onError)
    } else if (selectedGap.type === 'call') {
      ResolveCallGapService(selectedGap.call_id, selectedGap.gap_index, answer, category, productId, onSuccess, onError)
    } else {
      // WhatsApp gap — API expects {gap_index, answer}
      ResolveWhatsAppGapService(selectedGap.message_id, { gap_index: selectedGap.gap_index, answer }, onSuccess, onError)
    }
  }

  const rows  = tab === 0 ? emailGaps : tab === 1 ? callGaps : whatsappGaps
  const total = emailGaps.length + callGaps.length + whatsappGaps.length

  const colSpan = tab === 0 ? 6 : tab === 2 ? 6 : 5

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box>
            <Typography variant="h4" fontWeight={800} color="text.primary">Knowledge Gaps</Typography>
            <Typography variant="body2" color="text.secondary">
              {total} unresolved — questions the AI couldn&apos;t answer across Email, WhatsApp, and Calls
            </Typography>
          </Box>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchGaps} sx={{ bgcolor: 'grey.100' }}><RefreshIcon /></IconButton>
          </Tooltip>
        </Box>

        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
          <Tab label={`Email Gaps (${emailGaps.length})`} />
          <Tab label={`Call Gaps (${callGaps.length})`} />
          <Tab label={`WhatsApp Gaps (${whatsappGaps.length})`} />
        </Tabs>

        <TableContainer component={Paper} elevation={0}
          sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 4, overflow: 'hidden' }}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}><CircularProgress /></Box>
          ) : (
            <Table>
              <TableHead sx={{ bgcolor: 'grey.50' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Question</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Topic</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Product</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>
                    {tab === 0 ? 'From Email' : tab === 2 ? 'Phone Number' : 'Phone'}
                  </TableCell>
                  {(tab === 0 || tab === 2) && (
                    <TableCell sx={{ fontWeight: 700 }}>
                      {tab === 0 ? 'Subject' : 'Message Preview'}
                    </TableCell>
                  )}
                  <TableCell sx={{ fontWeight: 700 }} align="right">Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.length > 0 ? (
                  rows.map((gap, i) => (
                    <TableRow key={i} hover>
                      <TableCell sx={{ maxWidth: 360, width: 360 }}>
                        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                          <HelpOutline color="warning" sx={{ mt: 0.3, flexShrink: 0 }} fontSize="small" />
                          <Tooltip title={gap.question} placement="top-start">
                            <Typography
                              variant="body2" fontWeight={500}
                              sx={{
                                display: '-webkit-box', WebkitLineClamp: 3,
                                WebkitBoxOrient: 'vertical', overflow: 'hidden',
                                textOverflow: 'ellipsis', lineHeight: 1.4,
                              }}
                            >
                              {gap.question}
                            </Typography>
                          </Tooltip>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip label={gap.topic || 'general'} size="small" variant="tonal" color="primary" />
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {gap.product_name || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ maxWidth: 170, width: 170 }}>
                        <Tooltip title={gap.source || ''} placement="top-start">
                          <Typography variant="caption" color="text.secondary"
                            sx={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {gap.source}
                          </Typography>
                        </Tooltip>
                      </TableCell>
                      {(tab === 0 || tab === 2) && (
                        <TableCell sx={{ maxWidth: 160, width: 160 }}>
                          <Tooltip title={tab === 0 ? gap.subject : gap.body || ''} placement="top-start">
                            <Typography variant="caption" color="text.secondary"
                              sx={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {tab === 0 ? gap.subject : (gap.body || '').slice(0, 60)}
                            </Typography>
                          </Tooltip>
                        </TableCell>
                      )}
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                          {gap.product_id && (
                            <Button variant="outlined" size="small" color="primary"
                              onClick={() => navigate(`/knowledge-base/${gap.product_id}`)}
                              sx={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                              Fill in KB
                            </Button>
                          )}
                          {tab === 0 && gap.email_id && (
                            <Button variant="outlined" size="small" color="warning"
                              onClick={() => navigate('/gmail', { state: { selectEmailId: gap.email_id } })}
                              sx={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                              Review Email
                            </Button>
                          )}
                          {tab === 2 && gap.message_id && (
                            <Button variant="outlined" size="small"
                              sx={{ fontSize: '0.7rem', whiteSpace: 'nowrap', borderColor: '#25D366', color: '#25D366',
                                '&:hover': { borderColor: '#128C7E', background: '#f0fdf4' } }}
                              onClick={() => navigate('/whatsapp', { state: { selectMessageId: gap.message_id } })}>
                              Review WA
                            </Button>
                          )}
                          <Button variant="contained" size="small" color="success"
                            startIcon={<CheckCircle />}
                            onClick={() => openResolve(gap)}
                            sx={{ fontSize: '0.7rem' }}>
                            Resolve
                          </Button>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={colSpan} align="center" sx={{ py: 8 }}>
                      <Typography variant="body2" color="text.secondary">No unresolved gaps. All clear!</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </TableContainer>

        <Dialog open={resolveDialogOpen} onClose={() => !resolving && setResolveDialogOpen(false)}
          fullWidth maxWidth="sm" PaperProps={{ sx: { borderRadius: 3 } }}>
          <DialogTitle sx={{ fontWeight: 700, pb: 1 }}>Fill Knowledge Gap</DialogTitle>
          <DialogContent>
            {selectedGap && (
              <GapResolveForm
                gap={selectedGap}
                loading={resolving}
                onCancel={() => setResolveDialogOpen(false)}
                onResolve={handleResolve}
              />
            )}
          </DialogContent>
        </Dialog>

      </motion.div>
    </Container>
  )
}
