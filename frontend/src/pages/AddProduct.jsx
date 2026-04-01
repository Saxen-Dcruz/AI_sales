import React, { useState, useEffect } from 'react'
import {
  Container,
  Paper,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Stack,
  Box,
  IconButton,
  Divider,
  Alert,
  CircularProgress,
  InputAdornment
} from '@mui/material'
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Save as SaveIcon,
  ArrowBack as ArrowBackIcon,
  PlaylistAdd as PlaylistAddIcon,
  Inventory as InventoryIcon,
  Edit as EditIcon
} from '@mui/icons-material'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate, useParams } from 'react-router-dom'
import { AddProductService, EditProductService, ShowOneProductService } from '../services/ApiService'

const CATEGORY_MAP = {
  'Software': ['Voice AI', 'Chatbot', 'CRM'],
  'Services': ['Consulting', 'Implementation'],
  'Add-on': ['Storage', 'API Access']
}

export default function AddProduct() {
  const navigate = useNavigate()
  const { id } = useParams()
  const isEdit = Boolean(id)

  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(isEdit)
  const [statusMsg, setStatusMsg] = useState({ type: '', text: '' })

  // Core Form State
  const [formData, setFormData] = useState({
    category: '',
    subcategory: '',
    name: '',
    orderCode: '',
    brand: '',
    singlePrice: '',
    bulkPrice: '',
    description: '',
  })

  // Dynamic Fields State
  const [showSubheading, setShowSubheading] = useState(false)
  const [subheading, setSubheading] = useState('')
  const [features, setFeatures] = useState([''])
  const [packageItems, setPackageItems] = useState([''])

  useEffect(() => {
    if (isEdit) {
      setFetching(true)
      ShowOneProductService(
        { id },
        (data) => {
          if (data) {
            setFormData({
              category: data.category || '',
              subcategory: data.subcategory || '',
              name: data.name || '',
              orderCode: data.orderCode || '',
              brand: data.brand || '',
              singlePrice: data.singlePrice || '',
              bulkPrice: data.bulkPrice || '',
              description: data.description || '',
            })
            if (data.subheading) {
              setSubheading(data.subheading)
              setShowSubheading(true)
            }
            if (data.features?.length) setFeatures(data.features)
            if (data.packageContains?.length) setPackageItems(data.packageContains)
          }
          setFetching(false)
        },
        (status, err) => {
          setStatusMsg({ type: 'error', text: `Failed to load product: ${err}` })
          setFetching(false)
        }
      )
    }
  }, [id, isEdit])

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value,
      ...(name === 'category' ? { subcategory: '' } : {})
    }))
  }

  // Dynamic Array Handlers
  const addDynamicField = (setter) => setter(prev => [...prev, ''])
  const removeDynamicField = (index, setter) => setter(prev => prev.filter((_, i) => i !== index))
  const updateDynamicField = (index, value, setter) => {
    setter(prev => {
      const updated = [...prev]
      updated[index] = value
      return updated
    })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    
    // Validation
    if (!formData.name || !formData.category) {
      setStatusMsg({ type: 'error', text: 'Product Name and Category are required.' })
      window.scrollTo({ top: 0, behavior: 'smooth' })
      return
    }

    setLoading(true)
    setStatusMsg({ type: '', text: '' })

    const payload = {
      ...formData,
      id: isEdit ? id : undefined,
      subheading: showSubheading ? subheading : '',
      singlePrice: parseFloat(formData.singlePrice) || 0,
      bulkPrice: parseFloat(formData.bulkPrice) || 0,
      features: features.filter(f => f.trim() !== ''),
      packageContains: packageItems.filter(p => p.trim() !== '')
    }

    const serviceCall = isEdit ? EditProductService : AddProductService

    serviceCall(
      payload,
      () => {
        setLoading(false)
        setStatusMsg({ type: 'success', text: `Product successfully ${isEdit ? 'updated' : 'created'}! Redirecting...` })
        setTimeout(() => navigate('/products'), 1500)
      },
      (status, error) => {
        setLoading(false)
        setStatusMsg({ type: 'error', text: `Error: ${error || 'Failed to save product'}` })
      }
    )
  }

  if (fetching) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 20 }}>
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Container maxWidth="md" sx={{ py: 6 }}>
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        
        {/* Header Navigation */}
        <Box sx={{ mb: 4, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/products')} sx={{ color: 'text.secondary' }}>
            Back to Products
          </Button>
          <Typography variant="h4" fontWeight={800} color="primary.main">
            {isEdit ? 'Edit Product' : 'New Product'}
          </Typography>
        </Box>

        {statusMsg.text && (
          <Alert severity={statusMsg.type} sx={{ mb: 4, borderRadius: 2 }} onClose={() => setStatusMsg({ type: '', text: '' })}>
            {statusMsg.text}
          </Alert>
        )}

        <form onSubmit={handleSubmit}>
          <Stack spacing={4}>
            
            {/* 1. Identity & Classification */}
            <Paper elevation={0} sx={{ p: 4, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
              <Typography variant="h6" gutterBottom fontWeight={700} sx={{ mb: 3 }}>
                Identity & Classification
              </Typography>
              <Stack spacing={3}>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                  <FormControl fullWidth size="medium">
                    <InputLabel>Category</InputLabel>
                    <Select name="category" value={formData.category} label="Category" onChange={handleInputChange} required>
                      {Object.keys(CATEGORY_MAP).map(cat => (
                        <MenuItem key={cat} value={cat}>{cat}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <FormControl fullWidth size="medium" disabled={!formData.category}>
                    <InputLabel>Subcategory</InputLabel>
                    <Select name="subcategory" value={formData.subcategory} label="Subcategory" onChange={handleInputChange}>
                      {formData.category && CATEGORY_MAP[formData.category].map(sub => (
                        <MenuItem key={sub} value={sub}>{sub}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Stack>
                <TextField fullWidth label="Product Name" name="name" value={formData.name} onChange={handleInputChange} required />
                <AnimatePresence>
                  {!showSubheading ? (
                    <Button startIcon={<AddIcon />} size="small" onClick={() => setShowSubheading(true)} sx={{ textTransform: 'none', width: 'fit-content' }}>
                      Add Subheading
                    </Button>
                  ) : (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} style={{ overflow: 'hidden' }}>
                      <TextField fullWidth label="Product Subheading" value={subheading} onChange={(e) => setSubheading(e.target.value)}
                        InputProps={{
                          endAdornment: (
                            <InputAdornment position="end">
                              <IconButton size="small" onClick={() => setShowSubheading(false)} color="error"><DeleteIcon fontSize="small" /></IconButton>
                            </InputAdornment>
                          ),
                        }}
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
              </Stack>
            </Paper>

            {/* 2. Product Details */}
            <Paper elevation={0} sx={{ p: 4, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
              <Typography variant="h6" gutterBottom fontWeight={700} sx={{ mb: 3 }}>Product Details</Typography>
              <Stack spacing={3}>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                  <TextField fullWidth label="Order Code" name="orderCode" value={formData.orderCode} onChange={handleInputChange} />
                  <TextField fullWidth label="Brand" name="brand" value={formData.brand} onChange={handleInputChange} />
                </Stack>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                  <TextField fullWidth label="Single Price" name="singlePrice" type="number" value={formData.singlePrice} onChange={handleInputChange} 
                    InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }} />
                  <TextField fullWidth label="Bulk Price" name="bulkPrice" type="number" value={formData.bulkPrice} onChange={handleInputChange} 
                    InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }} />
                </Stack>
              </Stack>
            </Paper>

            {/* 3. Description */}
            <Paper elevation={0} sx={{ p: 4, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
              <Typography variant="h6" gutterBottom fontWeight={700}>Description</Typography>
              <TextField fullWidth multiline rows={5} name="description" value={formData.description} onChange={handleInputChange} />
            </Paper>

            {/* 4. Features */}
            <Paper elevation={0} sx={{ p: 4, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                <Typography variant="h6" fontWeight={700}>Product Features</Typography>
                <Button startIcon={<PlaylistAddIcon />} onClick={() => addDynamicField(setFeatures)} size="small" variant="outlined">Add Feature</Button>
              </Box>
              <Stack spacing={2}>
                <AnimatePresence mode="popLayout">
                  {features.map((feature, index) => (
                    <motion.div key={index} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      <TextField fullWidth size="small" value={feature} onChange={(e) => updateDynamicField(index, e.target.value, setFeatures)}
                        InputProps={{
                          endAdornment: features.length > 1 && (
                            <InputAdornment position="end">
                              <IconButton size="small" onClick={() => removeDynamicField(index, setFeatures)} color="error"><DeleteIcon fontSize="small" /></IconButton>
                            </InputAdornment>
                          ),
                        }}
                      />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </Stack>
            </Paper>

            {/* 5. Package Contains */}
            <Paper elevation={0} sx={{ p: 4, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                <Typography variant="h6" fontWeight={700}>Package Includes</Typography>
                <Button startIcon={<InventoryIcon />} onClick={() => addDynamicField(setPackageItems)} size="small" variant="outlined">Add Item</Button>
              </Box>
              <Stack spacing={2}>
                {packageItems.map((item, index) => (
                  <TextField key={index} fullWidth size="small" value={item} onChange={(e) => updateDynamicField(index, e.target.value, setPackageItems)}
                    InputProps={{
                      endAdornment: packageItems.length > 1 && (
                        <InputAdornment position="end">
                          <IconButton size="small" onClick={() => removeDynamicField(index, setPackageItems)} color="error"><DeleteIcon fontSize="small" /></IconButton>
                        </InputAdornment>
                      ),
                    }}
                  />
                ))}
              </Stack>
            </Paper>

            {/* Submit Actions */}
            <Box sx={{ pt: 2, display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
              <Button onClick={() => navigate('/products')} disabled={loading}>Cancel</Button>
              <Button type="submit" variant="contained" startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SaveIcon />} disabled={loading} sx={{ borderRadius: 3, px: 6 }}>
                {loading ? 'Saving...' : (isEdit ? 'Update Product' : 'Create Product')}
              </Button>
            </Box>
          </Stack>
        </form>
      </motion.div>
    </Container>
  )
}
