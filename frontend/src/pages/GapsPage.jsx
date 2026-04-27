import React, { useState, useEffect } from 'react'
import {
  Container,
  Typography,
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField
} from '@mui/material'
import {
  HelpOutline,
  LibraryAdd,
  CheckCircle,
  Delete as DeleteIcon,
  Search as SearchIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { GetGapsService, ResolveGapService } from '../services/ApiService'

export default function GapsPage() {
  const navigate = useNavigate()
  const [gaps, setGaps] = useState([])
  const [loading, setLoading] = useState(true)
  const [resolveDialogOpen, setResolveDialogOpen] = useState(false)
  const [selectedGap, setSelectedGap] = useState(null)
  const [resolution, setResolution] = useState('')

  const fetchGaps = () => {
    setLoading(true)
    GetGapsService(
      (data) => {
        setGaps(data || [])
        setLoading(false)
      },
      (status, err) => {
        console.error(err)
        setLoading(false)
        // Fallback demo data if API fails (simulating "Use as-is")
        if (!gaps.length) {
           setGaps([
             { id: 1, question: "How do I install the SDK for Python?", source: "Chat", status: "UNRESOLVED", created_at: new Date().toISOString() },
             { id: 2, question: "What is your pricing for bulk orders?", source: "Email", status: "UNRESOLVED", created_at: new Date().toISOString() }
           ])
        }
      }
    )
  }

  useEffect(() => {
    fetchGaps()
  }, [])

  const handleResolve = () => {
    if (!selectedGap) return
    ResolveGapService(
      selectedGap.id,
      { resolution },
      () => {
        setGaps(prev => prev.filter(g => g.id !== selectedGap.id))
        setResolveDialogOpen(false)
        setResolution('')
      },
      (status, err) => alert("Resolution failed: " + err)
    )
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
          <Box>
            <Typography variant="h4" fontWeight={800} color="text.primary">Knowledge Gaps</Typography>
            <Typography variant="body2" color="text.secondary">Questions the AI couldn't answer from existing knowledge</Typography>
          </Box>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchGaps} sx={{ bgcolor: 'grey.100' }}><RefreshIcon /></IconButton>
          </Tooltip>
        </Box>

        {/* Table Container */}
        <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 4, overflow: 'hidden' }}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Table>
              <TableHead sx={{ bgcolor: 'grey.50' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Unanswered Question</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Source</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Date</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                  <TableCell sx={{ fontWeight: 700 }} align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {gaps.length > 0 ? (
                  gaps.map((gap) => (
                    <TableRow key={gap.id} hover>
                      <TableCell sx={{ maxWidth: 400 }}>
                        <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
                          <HelpOutline color="warning" sx={{ mt: 0.5 }} />
                          <Typography variant="body2" fontWeight={500}>{gap.question}</Typography>
                        </Box>
                      </TableCell>
                      <TableCell><Chip label={gap.source} size="small" variant="tonal" color="primary" /></TableCell>
                      <TableCell><Typography variant="caption">{new Date(gap.created_at).toLocaleDateString()}</Typography></TableCell>
                      <TableCell><Chip label={gap.status} size="small" variant="outlined" color="warning" /></TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                          <Button 
                            variant="tonal" 
                            size="small" 
                            startIcon={<LibraryAdd />}
                            onClick={() => navigate('/products')}
                          >
                            Add to KB
                          </Button>
                          <Button 
                            variant="contained" 
                            size="small" 
                            color="success"
                            startIcon={<CheckCircle />}
                            onClick={() => {
                              setSelectedGap(gap)
                              setResolveDialogOpen(true)
                            }}
                          >
                            Resolve
                          </Button>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 8 }}>
                      <Typography variant="body2" color="text.secondary">All clear! No unanswered queries found.</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </TableContainer>

        {/* Resolve Dialog */}
        <Dialog 
          open={resolveDialogOpen} 
          onClose={() => setResolveDialogOpen(false)}
          fullWidth
          maxWidth="sm"
          PaperProps={{ sx: { borderRadius: 3 } }}
        >
          <DialogTitle sx={{ fontWeight: 700 }}>Resolve Query</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Provide a manual resolution or answer for: <strong>"{selectedGap?.question}"</strong>
            </Typography>
            <TextField
              fullWidth 
              label="Answer / Resolution"
              multiline
              rows={4}
              variant="outlined"
              value={resolution}
              onChange={(e) => setResolution(e.target.value)}
            />
          </DialogContent>
          <DialogActions sx={{ p: 2.5 }}>
            <Button onClick={() => setResolveDialogOpen(false)} color="inherit">Cancel</Button>
            <Button 
              onClick={handleResolve} 
              variant="contained" 
              color="success"
              disabled={!resolution}
            >
              Mark as Resolved
            </Button>
          </DialogActions>
        </Dialog>

      </motion.div>
    </Container>
  )
}
