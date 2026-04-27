import React, { useState, useEffect } from 'react'
import {
  Container,
  Paper,
  Typography,
  Box,
  Button,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  CircularProgress,
  Tooltip,
  Breadcrumbs,
  Link as MuiLink
} from '@mui/material'
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  ArrowBack as ArrowBackIcon,
  Save as SaveIcon,
  Refresh as RefreshIcon,
  LibraryBooks as KnowledgeBaseIcon
} from '@mui/icons-material'
import { motion } from 'framer-motion'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ShowOneProductService, EditProductService } from '../services/ApiService'

export default function KnowledgeBase() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)
  const [entries, setEntries] = useState([])
  
  // Form state
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingEntry, setEditingEntry] = useState(null)
  const [formData, setFormData] = useState({ title: '', content: '' })
  const [saving, setSaving] = useState(false)

  const fetchProduct = () => {
    setLoading(true)
    ShowOneProductService(
      { id },
      (data) => {
        setProduct(data)
        // Convert sections dict to entries list
        if (data.sections) {
          const entryList = Object.entries(data.sections).map(([title, content]) => ({
            id: title, // Use title as ID for simplicity
            title,
            content: typeof content === 'string' ? content : JSON.stringify(content)
          }))
          setEntries(entryList)
        }
        setLoading(false)
      },
      (status, err) => {
        console.error("Fetch Error:", err)
        setLoading(false)
      }
    )
  }

  useEffect(() => {
    fetchProduct()
  }, [id])

  const handleOpenDialog = (entry = null) => {
    if (entry) {
      setEditingEntry(entry)
      setFormData({ title: entry.title, content: entry.content })
    } else {
      setEditingEntry(null)
      setFormData({ title: '', content: '' })
    }
    setDialogOpen(true)
  }

  const handleSave = () => {
    if (!formData.title || !formData.content) return
    setSaving(true)

    const updatedSections = { ...product.sections }
    if (editingEntry && editingEntry.title !== formData.title) {
      delete updatedSections[editingEntry.title]
    }
    updatedSections[formData.title] = formData.content

    EditProductService(
      id,
      { ...product, sections: updatedSections },
      () => {
        setSaving(false)
        setDialogOpen(false)
        fetchProduct()
      },
      (status, err) => {
        alert("Save failed: " + err)
        setSaving(false)
      }
    )
  }

  const handleDelete = (title) => {
    if (!window.confirm(`Are you sure you want to delete "${title}"?`)) return
    
    const updatedSections = { ...product.sections }
    delete updatedSections[title]

    EditProductService(
      id,
      { ...product, sections: updatedSections },
      () => {
        fetchProduct()
      },
      (status, err) => alert("Delete failed: " + err)
    )
  }

  if (loading && !product) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 20 }}>
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        
        {/* Breadcrumbs */}
        <Breadcrumbs sx={{ mb: 2 }}>
          <MuiLink component={Link} to="/products" color="inherit" underline="hover">Products</MuiLink>
          <Typography color="text.primary">Knowledge Base</Typography>
        </Breadcrumbs>

        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <IconButton onClick={() => navigate('/products')} sx={{ bgcolor: 'grey.100' }}>
              <ArrowBackIcon />
            </IconButton>
            <Box>
              <Typography variant="h4" fontWeight={800} color="text.primary">
                {product?.name || 'Knowledge Base'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Managing knowledge base entries for product embeddings
              </Typography>
            </Box>
          </Box>
          <Button 
            variant="contained" 
            startIcon={<AddIcon />}
            onClick={() => handleOpenDialog()}
            sx={{ borderRadius: 3, px: 3, py: 1 }}
          >
            Add Entry
          </Button>
        </Box>

        {/* Table Container */}
        <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 3, overflow: 'hidden' }}>
          <Table>
            <TableHead sx={{ bgcolor: 'grey.50' }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>Entry Title</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Content Preview</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {entries.length > 0 ? (
                entries.map((entry) => (
                  <TableRow key={entry.id} hover>
                    <TableCell sx={{ width: '25%' }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <KnowledgeBaseIcon sx={{ color: 'primary.main', fontSize: 20 }} />
                        <Typography variant="subtitle2" fontWeight={600}>{entry.title}</Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary" sx={{ 
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden'
                      }}>
                        {entry.content}
                      </Typography>
                    </TableCell>
                    <TableCell align="right" sx={{ width: '15%' }}>
                      <Tooltip title="Edit">
                        <IconButton size="small" color="primary" onClick={() => handleOpenDialog(entry)}>
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton size="small" color="error" onClick={() => handleDelete(entry.title)}>
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={3} align="center" sx={{ py: 8 }}>
                    <Typography variant="body2" color="text.secondary">No knowledge base entries found.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Add/Edit Dialog */}
        <Dialog 
          open={dialogOpen} 
          onClose={() => setDialogOpen(false)}
          fullWidth
          maxWidth="sm"
          PaperProps={{ sx: { borderRadius: 3 } }}
        >
          <DialogTitle sx={{ fontWeight: 700 }}>
            {editingEntry ? 'Edit Entry' : 'Add New Entry'}
          </DialogTitle>
          <DialogContent>
            <Box sx={{ pt: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
              <TextField
                fullWidth
                label="Entry Title (e.g., Features, Installation)"
                variant="outlined"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              />
              <TextField
                fullWidth
                label="Content"
                multiline
                rows={8}
                variant="outlined"
                value={formData.content}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                placeholder="Enter detailed information for this section..."
              />
            </Box>
          </DialogContent>
          <DialogActions sx={{ p: 2.5 }}>
            <Button onClick={() => setDialogOpen(false)} color="inherit">Cancel</Button>
            <Button 
              onClick={handleSave} 
              variant="contained" 
              startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
              disabled={saving || !formData.title || !formData.content}
            >
              {saving ? 'Saving...' : 'Save Entry'}
            </Button>
          </DialogActions>
        </Dialog>

      </motion.div>
    </Container>
  )
}
