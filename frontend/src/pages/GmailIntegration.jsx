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
  Tooltip
} from '@mui/material'
import {
  Email,
  Sync as SyncIcon,
  Refresh as RefreshIcon,
  Visibility as VisibilityIcon,
  MarkEmailRead,
  ErrorOutline
} from '@mui/icons-material'
import { motion } from 'framer-motion'
import { GetGmailMessagesService, SyncGmailService } from '../services/ApiService'

export default function GmailIntegration() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)

  const fetchMessages = () => {
    setLoading(true)
    GetGmailMessagesService(
      (data) => {
        setMessages(data || [])
        setLoading(false)
      },
      (status, err) => {
        console.error(err)
        setLoading(false)
        // Placeholder data if service is missing
        if (!messages.length) {
          setMessages([
            { id: 1, subject: "Potential Partnership - TechFlow", from: "alex@techflow.com", date: new Date().toISOString(), status: "SCANNED" },
            { id: 2, subject: "Question about AI Analytics", from: "maria@innovate.co", date: new Date().toISOString(), status: "UNRESOLVED" }
          ])
        }
      }
    )
  }

  const handleSync = () => {
    setSyncing(true)
    SyncGmailService(
      () => {
        setSyncing(false)
        fetchMessages()
      },
      (status, err) => {
        alert("Sync failed: " + err)
        setSyncing(false)
      }
    )
  }

  useEffect(() => {
    fetchMessages()
  }, [])

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
          <Box>
            <Typography variant="h4" fontWeight={800} color="text.primary">Gmail Integration</Typography>
            <Typography variant="body2" color="text.secondary">Automated lead communication and scanning</Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Tooltip title="Refresh List">
              <IconButton onClick={fetchMessages} sx={{ bgcolor: 'grey.100' }}><RefreshIcon /></IconButton>
            </Tooltip>
            <Button 
              variant="contained" 
              startIcon={syncing ? <CircularProgress size={20} color="inherit" /> : <SyncIcon />}
              onClick={handleSync}
              disabled={syncing}
              sx={{ borderRadius: 3, px: 3 }}
            >
              {syncing ? 'Syncing...' : 'Sync Emails'}
            </Button>
          </Box>
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
                  <TableCell sx={{ fontWeight: 700 }}>Subject</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>From</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Date</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                  <TableCell sx={{ fontWeight: 700 }} align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {messages.length > 0 ? (
                  messages.map((msg) => (
                    <TableRow key={msg.id} hover>
                      <TableCell>
                        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                          <Email color="primary" />
                          <Typography variant="body2" fontWeight={600}>{msg.subject}</Typography>
                        </Box>
                      </TableCell>
                      <TableCell><Typography variant="body2" color="text.secondary">{msg.from}</Typography></TableCell>
                      <TableCell><Typography variant="caption">{new Date(msg.date).toLocaleString()}</Typography></TableCell>
                      <TableCell>
                        <Chip 
                          label={msg.status} 
                          size="small" 
                          color={msg.status === 'SCANNED' ? 'success' : 'warning'} 
                          variant="tonal"
                          sx={{ fontSize: '0.7rem', fontWeight: 700 }}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <IconButton size="small" color="primary">
                          <VisibilityIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 8 }}>
                      <Typography variant="body2" color="text.secondary">No emails found. Click Sync to fetch latest communications.</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </TableContainer>

      </motion.div>
    </Container>
  )
}
