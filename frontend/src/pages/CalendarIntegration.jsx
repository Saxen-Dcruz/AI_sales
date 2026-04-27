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
  CircularProgress,
  Chip,
  IconButton,
  Tooltip
} from '@mui/material'
import {
  CalendarMonth,
  Event as EventIcon,
  Refresh as RefreshIcon,
  Schedule
} from '@mui/icons-material'
import { motion } from 'framer-motion'
import { GetCalendarEventsService } from '../services/ApiService'

export default function CalendarIntegration() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchEvents = () => {
    setLoading(true)
    GetCalendarEventsService(
      (data) => {
        setEvents(data || [])
        setLoading(false)
      },
      (status, err) => {
        console.error(err)
        setLoading(false)
        // Placeholder data
        if (!events.length) {
          setEvents([
            { id: 1, title: "Product Demo - Alex Mitchell", start: new Date(Date.now() + 86400000).toISOString(), end: new Date(Date.now() + 90000000).toISOString(), status: "CONFIRMED" },
            { id: 2, title: "Intro Call - InnovateTech", start: new Date(Date.now() + 172800000).toISOString(), end: new Date(Date.now() + 176400000).toISOString(), status: "TENTATIVE" }
          ])
        }
      }
    )
  }

  useEffect(() => {
    fetchEvents()
  }, [])

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
          <Box>
            <Typography variant="h4" fontWeight={800} color="text.primary">Calendar Integration</Typography>
            <Typography variant="body2" color="text.secondary">Scheduled demos and follow-up calls</Typography>
          </Box>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchEvents} sx={{ bgcolor: 'grey.100' }}><RefreshIcon /></IconButton>
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
                  <TableCell sx={{ fontWeight: 700 }}>Event Title</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Start Time</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>End Time</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {events.length > 0 ? (
                  events.map((event) => (
                    <TableRow key={event.id} hover>
                      <TableCell>
                        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                          <EventIcon color="primary" />
                          <Typography variant="body2" fontWeight={600}>{event.title}</Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Schedule fontSize="small" color="disabled" />
                          <Typography variant="body2">{new Date(event.start).toLocaleString()}</Typography>
                        </Box>
                      </TableCell>
                      <TableCell><Typography variant="body2">{new Date(event.end).toLocaleString()}</Typography></TableCell>
                      <TableCell>
                        <Chip 
                          label={event.status} 
                          size="small" 
                          color={event.status === 'CONFIRMED' ? 'success' : 'default'} 
                          variant="tonal"
                          sx={{ fontSize: '0.7rem', fontWeight: 700 }}
                        />
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={4} align="center" sx={{ py: 8 }}>
                      <Typography variant="body2" color="text.secondary">No upcoming events found.</Typography>
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
