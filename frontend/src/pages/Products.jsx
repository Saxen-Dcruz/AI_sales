import React, { useState, useEffect } from 'react'
import {
  Container,
  Paper,
  Typography,
  Box,
  Button,
  TextField,
  InputAdornment,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Chip,
  FormControl,
  Select,
  MenuItem,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Menu,
  Tooltip,
  Stack,
  Divider
} from '@mui/material'
import {
  Search as SearchIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  MoreVert as MoreVertIcon,
  Inventory as PackageIcon,
  Edit as EditIcon,
  FilterList as FilterListIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  Block as BlockIcon,
  Visibility as VisibilityIcon,
  LibraryBooks as KnowledgeBaseIcon
} from '@mui/icons-material'
import { motion } from 'framer-motion'
import { Link, useNavigate } from 'react-router-dom'
import { ShowAllProductService, DeleteProductService, ToggleActiveInactiveService } from '../services/ApiService'

export default function Products() {
  const navigate = useNavigate()
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('All Categories')
  
  // Dialog & Menu states
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [anchorEl, setAnchorEl] = useState(null)
  
  const [viewDialogOpen, setViewDialogOpen] = useState(false)
  const [selectedProductForView, setSelectedProductForView] = useState(null)

  const fetchProducts = () => {
    setLoading(true)
    ShowAllProductService(
      null,
      (data) => {
        const mappedData = (data || []).map(p => ({
          ...p,
          name: p.Product_id || p.name || 'Unnamed Product',
          category: p.Category || p.category || 'Uncategorized',
          price: p.Price !== undefined ? p.Price : (p.singlePrice || 0),
          status: p.is_active !== undefined ? (p.is_active ? 'Active' : 'Inactive') : (p.status || 'Active')
        }))
        setProducts(mappedData)
        setLoading(false)
      },
      (status, err) => {
        console.error("Fetch Error:", err)
        setLoading(false)
      }
    )
  }

  useEffect(() => {
    fetchProducts()
  }, [])

  const handleDeleteClick = (product) => {
    setSelectedProduct(product)
    setDeleteDialogOpen(true)
    setAnchorEl(null)
  }

  const confirmDelete = () => {
    if (!selectedProduct) return
    DeleteProductService(
      selectedProduct.id,
      () => {
        setProducts(prev => prev.filter(p => p.id !== selectedProduct.id))
        setDeleteDialogOpen(false)
      },
      (status, err) => alert(`Delete failed: ${err}`)
    )
  }

  const handleToggleStatus = (product) => {
    ToggleActiveInactiveService(
      { id: product.id },
      () => {
        setProducts(prev => prev.map(p => 
          p.id === product.id ? { ...p, status: p.status === 'Active' ? 'Inactive' : 'Active' } : p
        ))
      },
      (status, err) => alert(`Toggle failed: ${err}`)
    )
  }

  const filteredProducts = products.filter(p => {
    const matchesSearch = p.name?.toLowerCase().includes(search.toLowerCase()) || 
                          p.id?.toString().includes(search)
    const matchesCategory = category === 'All Categories' || p.category === category
    return matchesSearch && matchesCategory
  })

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
          <Box>
            <Typography variant="h4" fontWeight={800} color="text.primary">Products</Typography>
            <Typography variant="body2" color="text.secondary">Manage your software and services catalog</Typography>
          </Box>
          <Button 
            component={Link} 
            to="/add-product" 
            variant="contained" 
            startIcon={<AddIcon />}
            sx={{ borderRadius: 3, px: 3, py: 1 }}
          >
            Add Product
          </Button>
        </Box>

        {/* Filters Area */}
        <Paper elevation={0} sx={{ p: 2, mb: 3, border: '1px solid', borderColor: 'divider', borderRadius: 3, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField
            size="small"
            placeholder="Search products..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            InputProps={{
              startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>
            }}
            sx={{ flexGrow: 1, maxWidth: 400 }}
          />

          <FormControl size="small" sx={{ minWidth: 160 }}>
            <Select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              startAdornment={<FilterListIcon fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />}
            >
              <MenuItem value="All Categories">All Categories</MenuItem>
              <MenuItem value="Software">Software</MenuItem>
              <MenuItem value="Services">Services</MenuItem>
              <MenuItem value="Add-on">Add-on</MenuItem>
            </Select>
          </FormControl>

          <Tooltip title="Refresh List">
            <IconButton onClick={fetchProducts} size="small"><RefreshIcon /></IconButton>
          </Tooltip>
        </Paper>

        {/* Table Container */}
        <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 3, overflow: 'hidden' }}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Table>
              <TableHead sx={{ bgcolor: 'grey.50' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Product Details</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Category</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Price</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                  <TableCell sx={{ fontWeight: 700 }} align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredProducts.length > 0 ? (
                  filteredProducts.map((product) => (
                    <TableRow key={product.id} hover>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                          <Box sx={{ p: 1, bgcolor: 'primary.light', borderRadius: 2, color: 'primary.contrastText', display: 'flex' }}>
                            <PackageIcon fontSize="small" />
                          </Box>
                          <Box>
                            <Typography variant="subtitle2" fontWeight={600}>{product.name}</Typography>
                            <Typography variant="caption" color="text.secondary">ID: {product.id}</Typography>
                          </Box>
                        </Box>
                      </TableCell>
                      <TableCell><Typography variant="body2">{product.category}</Typography></TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          ${product.singlePrice || product.price || '0'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={product.status || 'Active'} 
                          size="small" 
                          color={product.status === 'Active' ? 'success' : 'warning'}
                          variant="tonal"
                          sx={{ fontWeight: 600 }}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title="View Details">
                          <IconButton size="small" onClick={() => {
                            setSelectedProductForView(product)
                            setViewDialogOpen(true)
                          }} color="primary" sx={{ mr: 1 }}>
                            <VisibilityIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <IconButton size="small" onClick={(e) => {
                          setAnchorEl(e.currentTarget)
                          setSelectedProduct(product)
                        }}>
                          <MoreVertIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 8 }}>
                      <Typography variant="body2" color="text.secondary">No products found matching your criteria.</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </TableContainer>

        {/* Action Menu */}
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={() => setAnchorEl(null)}
          PaperProps={{ elevation: 2, sx: { borderRadius: 2, minWidth: 150 } }}
        >
          <MenuItem onClick={() => {
            navigate(`/edit-product/${selectedProduct.id}`)
            setAnchorEl(null)
          }}>
            <EditIcon sx={{ mr: 1, fontSize: 18 }} />
            Edit Product
          </MenuItem>
          <MenuItem onClick={() => {
            handleToggleStatus(selectedProduct)
            setAnchorEl(null)
          }}>
            {selectedProduct?.status === 'Active' ? <BlockIcon sx={{ mr: 1, fontSize: 18 }} /> : <CheckCircleIcon sx={{ mr: 1, fontSize: 18 }} />}
            {selectedProduct?.status === 'Active' ? 'Deactivate' : 'Activate'}
          </MenuItem>
          <MenuItem onClick={() => {
            navigate(`/knowledge-base/${selectedProduct.id}`)
            setAnchorEl(null)
          }}>
            <KnowledgeBaseIcon sx={{ mr: 1, fontSize: 18 }} />
            Add Knowledge Base
          </MenuItem>
          <MenuItem onClick={() => handleDeleteClick(selectedProduct)} sx={{ color: 'error.main' }}>
            <DeleteIcon sx={{ mr: 1, fontSize: 18 }} />
            Delete
          </MenuItem>
        </Menu>

        {/* Delete Confirmation Dialog */}
        <Dialog 
          open={deleteDialogOpen} 
          onClose={() => setDeleteDialogOpen(false)}
          PaperProps={{ sx: { borderRadius: 3 } }}
        >
          <DialogTitle sx={{ fontWeight: 700 }}>Confirm Deletion</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to delete <strong>{selectedProduct?.name}</strong>? This action cannot be undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions sx={{ p: 2, pt: 0 }}>
            <Button onClick={() => setDeleteDialogOpen(false)} color="inherit">Cancel</Button>
            <Button onClick={confirmDelete} color="error" variant="contained">Delete Product</Button>
          </DialogActions>
        </Dialog>

        {/* View Details Dialog */}
        <Dialog 
          open={viewDialogOpen} 
          onClose={() => setViewDialogOpen(false)}
          PaperProps={{ sx: { borderRadius: 3, maxWidth: 500, width: '100%' } }}
        >
          <DialogTitle sx={{ fontWeight: 700, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            Product Details
            <Chip 
              label={selectedProductForView?.status || 'Active'} 
              size="small" 
              color={selectedProductForView?.status === 'Active' ? 'success' : 'warning'}
            />
          </DialogTitle>
          <Divider />
          <DialogContent>
            {selectedProductForView && (
              <Stack spacing={3}>
                <Box>
                  <Typography variant="caption" color="text.secondary">Product Name & System ID</Typography>
                  <Typography variant="subtitle1" fontWeight={600}>{selectedProductForView.name}</Typography>
                  <Typography variant="caption" color="text.disabled" sx={{ wordBreak: 'break-all' }}>{selectedProductForView.id}</Typography>
                </Box>
                <Stack direction="row" spacing={4} flexWrap="wrap" useFlexGap>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Order Code</Typography>
                    <Typography variant="body1">{selectedProductForView['Order Code'] || '-'}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Brand</Typography>
                    <Typography variant="body1">{selectedProductForView.Brand || '-'}</Typography>
                  </Box>
                </Stack>
                
                <Stack direction="row" spacing={4} flexWrap="wrap" useFlexGap>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Category</Typography>
                    <Typography variant="body1">{selectedProductForView.category}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Sub-category</Typography>
                    <Typography variant="body1">{selectedProductForView['Sub-category'] || '-'}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Price</Typography>
                    <Typography variant="body1" fontWeight={600} color="primary.main">
                      ${selectedProductForView.price}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Bulk Price</Typography>
                    <Typography variant="body1" fontWeight={600} color="primary.dark">
                      ${selectedProductForView.bulk_price || '0'}
                    </Typography>
                  </Box>
                </Stack>

                {(selectedProductForView['Product Link'] || selectedProductForView['Data Sheet link'] || selectedProductForView['User Manual'] || selectedProductForView['Learning Center SDK']) && (
                  <Box>
                    <Typography variant="caption" color="text.secondary" gutterBottom>External References</Typography>
                    <Stack direction="row" spacing={1} sx={{ mt: 0.5, flexWrap: 'wrap', gap: 1 }}>
                      {selectedProductForView['Product Link'] && <Chip size="small" label="Product Link" component="a" href={selectedProductForView['Product Link']} target="_blank" clickable color="info" variant="outlined" />}
                      {selectedProductForView['Data Sheet link'] && <Chip size="small" label="Data Sheet" component="a" href={selectedProductForView['Data Sheet link']} target="_blank" clickable color="info" variant="outlined" />}
                      {selectedProductForView['User Manual'] && <Chip size="small" label="User Manual" component="a" href={selectedProductForView['User Manual']} target="_blank" clickable color="info" variant="outlined" />}
                      {selectedProductForView['Learning Center SDK'] && <Chip size="small" label="Learning Center SDK" component="a" href={selectedProductForView['Learning Center SDK']} target="_blank" clickable color="info" variant="outlined" />}
                    </Stack>
                  </Box>
                )}
                {selectedProductForView.sections?.description && (
                  <Box>
                    <Typography variant="caption" color="text.secondary">Description</Typography>
                    <Typography variant="body2">{selectedProductForView.sections.description}</Typography>
                  </Box>
                )}
                {selectedProductForView.sections?.features?.length > 0 && (
                  <Box>
                    <Typography variant="caption" color="text.secondary">Features</Typography>
                    <Box component="ul" sx={{ mt: 0.5, pl: 2, mb: 0 }}>
                      {selectedProductForView.sections.features.map((f, i) => (
                        <Typography component="li" variant="body2" key={i}>{f}</Typography>
                      ))}
                    </Box>
                  </Box>
                )}
              </Stack>
            )}
          </DialogContent>
          <DialogActions sx={{ p: 2, pt: 0 }}>
            <Button onClick={() => setViewDialogOpen(false)} variant="contained" color="primary">Close</Button>
          </DialogActions>
        </Dialog>

      </motion.div>
    </Container>
  )
}
