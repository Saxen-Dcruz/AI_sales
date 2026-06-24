import React, { useState, useEffect, useRef } from 'react'
import {
  Container,
  Paper,
  Typography,
  TextField,
  Autocomplete,
  Button,
  Stack,
  Box,
  IconButton,
  Alert,
  CircularProgress,
  InputAdornment,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  Divider
} from '@mui/material'
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Save as SaveIcon,
  ArrowBack as ArrowBackIcon,
  PlaylistAdd as PlaylistAddIcon,
  Inventory as InventoryIcon,
  ContentCopy as ContentCopyIcon,
  Visibility as PreviewIcon,
  DescriptionOutlined as DraftIcon,
  HelpOutline as FaqIcon,
  LocalOffer as PricingIcon
} from '@mui/icons-material'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate, useParams } from 'react-router-dom'
import {
  AddProductService,
  EditProductService,
  ShowOneProductService,
  GetProductCategoriesService
} from '../services/ApiService'

// Seed categories/subcategories used when the catalog is empty
const CATEGORY_MAP = {
  'Software': ['Voice AI', 'Chatbot', 'CRM'],
  'Services': ['Consulting', 'Implementation'],
  'Add-on': ['Storage', 'API Access']
}

const emptyFaq = () => ({ question: '', answer: '' })
const emptyBulkTier = () => ({ quantity: '', price: '' })
const defaultBulkTiers = () => [
  { quantity: '10', price: '' },
  { quantity: '25', price: '' },
  { quantity: '100', price: '' }
]
const emptyProductCode = () => ({ order_code: '', single_price: '', bulk_pricing: defaultBulkTiers() })

const DRAFT_PREFIX = 'addProductDraft_'

export default function AddProduct() {
  const navigate = useNavigate()
  const { id } = useParams()
  const isEdit = Boolean(id)
  const draftKey = `${DRAFT_PREFIX}${isEdit ? id : 'new'}`

  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(isEdit)
  const [statusMsg, setStatusMsg] = useState({ type: '', text: '' })
  const [previewOpen, setPreviewOpen] = useState(false)
  const [draftDialogOpen, setDraftDialogOpen] = useState(false)
  const [pendingDraft, setPendingDraft] = useState(null)

  // Category/subcategory options pulled from the catalog
  const [availableCategories, setAvailableCategories] = useState(Object.keys(CATEGORY_MAP))
  const [availableSubcategories, setAvailableSubcategories] = useState(
    Array.from(new Set(Object.values(CATEGORY_MAP).flat()))
  )

  // Core Form State
  const [formData, setFormData] = useState({
    categories: [],
    subcategories: [],
    name: '',
    description: '',
    productLink: '',
    dataSheetLink: '',
    userManualLink: '',
    sdkLink: ''
  })

  // Dynamic Fields State
  const [showSubheading, setShowSubheading] = useState(false)
  const [subheading, setSubheading] = useState('')
  const [features, setFeatures] = useState([''])
  const [packageItems, setPackageItems] = useState([''])
  const [applications, setApplications] = useState([''])
  const [benefits, setBenefits] = useState([''])
  const [enclosureDimensions, setEnclosureDimensions] = useState([''])
  const [faqs, setFaqs] = useState([emptyFaq()])
  const [productCodes, setProductCodes] = useState([emptyProductCode()])

  const hasLoadedRef = useRef(false)

  // ── Load category/subcategory options ──────────────────────────────────────
  useEffect(() => {
    GetProductCategoriesService(
      (data) => {
        if (data?.categories?.length) {
          setAvailableCategories(prev => Array.from(new Set([...prev, ...data.categories])))
        }
        if (data?.subcategories?.length) {
          setAvailableSubcategories(prev => Array.from(new Set([...prev, ...data.subcategories])))
        }
      },
      () => {}
    )
  }, [])

  // ── Load existing product (edit mode) ──────────────────────────────────────
  useEffect(() => {
    if (isEdit) {
      setFetching(true)
      ShowOneProductService(
        { id },
        (data) => {
          if (data) {
            applyProductData(data)
          }
          setFetching(false)
          hasLoadedRef.current = true
        },
        (status, err) => {
          setFetching(false)
          if (status === 401) {
            navigate('/login')
          } else {
            setStatusMsg({ type: 'error', text: `Failed to load product: ${err}` })
          }
        }
      )
    } else {
      // New product — check for a copied product or a saved draft
      const copySource = sessionStorage.getItem('productCopySource')
      if (copySource) {
        try {
          const copied = JSON.parse(copySource)
          applyProductData(copied, { isCopy: true })
          setStatusMsg({ type: 'info', text: 'Copied product details loaded — review and save as a new product.' })
        } catch { /* ignore malformed copy data */ }
        sessionStorage.removeItem('productCopySource')
      } else {
        const draft = localStorage.getItem(draftKey)
        if (draft) {
          try {
            const parsed = JSON.parse(draft)
            setPendingDraft(parsed)
            setDraftDialogOpen(true)
            return
          } catch { /* ignore malformed draft */ }
        }
      }
      hasLoadedRef.current = true
    }
  }, [id, isEdit])

  const handleRestoreDraft = () => {
    if (pendingDraft) applyDraftData(pendingDraft)
    setStatusMsg({ type: 'info', text: 'Restored your unsaved draft.' })
    setPendingDraft(null)
    setDraftDialogOpen(false)
    hasLoadedRef.current = true
  }

  const handleDiscardDraft = () => {
    localStorage.removeItem(draftKey)
    setPendingDraft(null)
    setDraftDialogOpen(false)
    hasLoadedRef.current = true
  }

  // Convert legacy/back-end tier shapes (min_qty/discount_percent/final_price) into the
  // simple quantity/price tiers used by the Product Details form
  const normalizeBulkTiers = (tiers) => {
    if (!tiers?.length) return defaultBulkTiers()
    return tiers.map(t => ({
      quantity: t.quantity ?? t.min_qty ?? '',
      price: t.price ?? t.final_price ?? ''
    }))
  }

  const applyProductData = (data, { isCopy = false } = {}) => {
    const sections = data.sections || {}
    setFormData({
      categories: data.categories?.length ? data.categories : (data.Category || data.category ? [data.Category || data.category] : []),
      subcategories: data.subcategories?.length ? data.subcategories : (data['Sub-category'] || data.sub_category ? [data['Sub-category'] || data.sub_category] : []),
      name: isCopy ? `${data.Product_id || data.name || ''} (Copy)` : (data.Product_id || data.name || ''),
      description: sections.description || '',
      productLink: data['Product Link'] || data.product_link || '',
      dataSheetLink: data['Data Sheet link'] || data.datasheet_link || '',
      userManualLink: data['User Manual'] || data.user_manual_link || '',
      sdkLink: data['Learning Center SDK'] || data.sdk_link || ''
    })
    if (sections.subheading) {
      setSubheading(sections.subheading)
      setShowSubheading(true)
    }
    if (sections.features?.length) setFeatures(sections.features)
    if (sections.packageContains?.length) setPackageItems(sections.packageContains)
    if (sections.applications?.length) setApplications(sections.applications)
    if (sections.benefits?.length) setBenefits(sections.benefits)
    if (sections.enclosure_dimensions?.length) setEnclosureDimensions(sections.enclosure_dimensions)
    if (data.faqs?.length) setFaqs(data.faqs)

    const mainCode = {
      order_code: isCopy ? '' : (data['Order Code'] || data.order_code || ''),
      single_price: data.Price !== undefined ? data.Price : (data.single_price ?? ''),
      bulk_pricing: normalizeBulkTiers(data.bulk_pricing)
    }
    const extraCodes = (data.variations || []).map(v => ({
      order_code: isCopy ? '' : (v.order_code || ''),
      single_price: v.single_price ?? '',
      bulk_pricing: normalizeBulkTiers(v.bulk_pricing)
    }))
    setProductCodes([mainCode, ...extraCodes])
  }

  const applyDraftData = (draft) => {
    if (draft.formData) setFormData(draft.formData)
    if (draft.subheading !== undefined) setSubheading(draft.subheading)
    if (draft.showSubheading !== undefined) setShowSubheading(draft.showSubheading)
    if (draft.features) setFeatures(draft.features)
    if (draft.packageItems) setPackageItems(draft.packageItems)
    if (draft.applications) setApplications(draft.applications)
    if (draft.benefits) setBenefits(draft.benefits)
    if (draft.enclosureDimensions) setEnclosureDimensions(draft.enclosureDimensions)
    if (draft.faqs) setFaqs(draft.faqs)
    if (draft.productCodes) setProductCodes(draft.productCodes)
  }

  // ── Autosave to localStorage ────────────────────────────────────────────────
  useEffect(() => {
    if (!hasLoadedRef.current) return
    const timer = setTimeout(() => {
      const draft = { formData, subheading, showSubheading, features, packageItems, applications, benefits, enclosureDimensions, faqs, productCodes }
      localStorage.setItem(draftKey, JSON.stringify(draft))
    }, 800)
    return () => clearTimeout(timer)
  }, [formData, subheading, showSubheading, features, packageItems, applications, benefits, enclosureDimensions, faqs, productCodes, draftKey])

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
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

  // FAQ handlers
  const addFaq = () => setFaqs(prev => [...prev, emptyFaq()])
  const removeFaq = (index) => setFaqs(prev => prev.filter((_, i) => i !== index))
  const updateFaq = (index, field, value) => {
    setFaqs(prev => {
      const updated = [...prev]
      updated[index] = { ...updated[index], [field]: value }
      return updated
    })
  }

  // Product Code handlers — each code has an order code, single price, and its own bulk pricing tiers
  const addProductCode = () => setProductCodes(prev => [...prev, emptyProductCode()])
  const removeProductCode = (index) => setProductCodes(prev => prev.filter((_, i) => i !== index))
  const updateProductCode = (index, field, value) => {
    setProductCodes(prev => {
      const updated = [...prev]
      updated[index] = { ...updated[index], [field]: value }
      return updated
    })
  }

  // Bulk pricing tier handlers, scoped to a single product code
  const addBulkTier = (codeIndex) => {
    setProductCodes(prev => {
      const updated = [...prev]
      updated[codeIndex] = { ...updated[codeIndex], bulk_pricing: [...updated[codeIndex].bulk_pricing, emptyBulkTier()] }
      return updated
    })
  }
  const removeBulkTier = (codeIndex, tierIndex) => {
    setProductCodes(prev => {
      const updated = [...prev]
      updated[codeIndex] = { ...updated[codeIndex], bulk_pricing: updated[codeIndex].bulk_pricing.filter((_, i) => i !== tierIndex) }
      return updated
    })
  }
  const updateBulkTier = (codeIndex, tierIndex, field, value) => {
    setProductCodes(prev => {
      const updated = [...prev]
      const tiers = [...updated[codeIndex].bulk_pricing]
      tiers[tierIndex] = { ...tiers[tierIndex], [field]: value }
      updated[codeIndex] = { ...updated[codeIndex], bulk_pricing: tiers }
      return updated
    })
  }

  const cleanBulkTiers = (tiers) => (tiers || [])
    .filter(t => t.quantity !== '' || t.price !== '')
    .map(t => ({
      quantity: t.quantity !== '' ? parseFloat(t.quantity) : null,
      price: t.price !== '' ? parseFloat(t.price) : null
    }))

  const buildPayload = () => {
    const cleanFaqs = faqs.filter(f => f.question.trim() || f.answer.trim())
    const mainCode = productCodes[0] || emptyProductCode()
    const mainBulkPricing = cleanBulkTiers(mainCode.bulk_pricing)
    const cleanVariations = productCodes
      .slice(1)
      .filter(v => v.order_code.trim() || v.single_price !== '')
      .map(v => ({
        order_code: v.order_code || null,
        single_price: v.single_price !== '' ? parseFloat(v.single_price) : null,
        bulk_pricing: cleanBulkTiers(v.bulk_pricing)
      }))

    return {
      name: formData.name,
      order_code: mainCode.order_code,
      category: formData.categories[0] || '',
      sub_category: formData.subcategories[0] || '',
      categories: formData.categories,
      subcategories: formData.subcategories,
      single_price: parseFloat(mainCode.single_price) || 0,
      bulk_price: mainBulkPricing[0]?.price ?? 0,
      product_link: formData.productLink || null,
      datasheet_link: formData.dataSheetLink || null,
      user_manual_link: formData.userManualLink || null,
      sdk_link: formData.sdkLink || null,
      is_active: true,
      faqs: cleanFaqs,
      bulk_pricing: mainBulkPricing,
      variations: cleanVariations,
      sections: {
        description: formData.description,
        subheading: showSubheading ? subheading : '',
        features: features.filter(f => f.trim() !== ''),
        packageContains: packageItems.filter(p => p.trim() !== ''),
        applications: applications.filter(a => a.trim() !== ''),
        benefits: benefits.filter(b => b.trim() !== ''),
        enclosure_dimensions: enclosureDimensions.filter(d => d.trim() !== ''),
        faqs: cleanFaqs
      }
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()

    // Validation
    const mainCode = productCodes[0] || emptyProductCode()
    if (!formData.name || formData.categories.length === 0 || formData.subcategories.length === 0 || !mainCode.order_code || !mainCode.single_price) {
      setStatusMsg({ type: 'error', text: 'Product Name, Order Code, Price, Category and Subcategory are required.' })
      window.scrollTo({ top: 0, behavior: 'smooth' })
      return
    }

    setLoading(true)
    setStatusMsg({ type: '', text: '' })

    const payload = buildPayload()

    const onSuccess = (message) => {
      setLoading(false)
      localStorage.removeItem(draftKey)
      setStatusMsg({ type: 'success', text: message })
      setTimeout(() => navigate('/products'), 1500)
    }
    const onError = (status, error) => {
      setLoading(false)
      setStatusMsg({ type: 'error', text: `Error: ${error || 'Failed to save product'}` })
    }

    if (isEdit) {
      EditProductService(id, payload, () => onSuccess('Product successfully updated! Redirecting...'), onError)
    } else {
      AddProductService(payload, () => onSuccess('Product successfully created! Redirecting...'), onError)
    }
  }

  const handleSaveDraft = () => {
    const draft = { formData, subheading, showSubheading, features, packageItems, applications, benefits, enclosureDimensions, faqs, productCodes }
    localStorage.setItem(draftKey, JSON.stringify(draft))
    setStatusMsg({ type: 'success', text: 'Draft saved locally on this browser.' })
  }

  const handleCopyProduct = () => {
    const payload = buildPayload()
    sessionStorage.setItem('productCopySource', JSON.stringify({
      ...payload,
      Product_id: payload.name,
      sections: payload.sections
    }))
    navigate('/add-product')
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
        <Box sx={{ mb: 4, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
          <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/products')} sx={{ color: 'text.secondary' }}>
            Back to Products
          </Button>
          <Typography variant="h4" fontWeight={800} color="primary.main">
            {isEdit ? 'Edit Product' : 'New Product'}
          </Typography>
        </Box>

        {statusMsg.text && (
          <Alert severity={statusMsg.type || 'info'} sx={{ mb: 4, borderRadius: 2 }} onClose={() => setStatusMsg({ type: '', text: '' })}>
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
                  <Autocomplete
                    multiple
                    freeSolo
                    fullWidth
                    options={availableCategories}
                    value={formData.categories}
                    onChange={(_e, newValue) => setFormData(prev => ({ ...prev, categories: newValue }))}
                    renderTags={(value, getTagProps) =>
                      value.map((option, index) => (
                        <Chip variant="outlined" label={option} size="small" {...getTagProps({ index })} key={option} />
                      ))
                    }
                    renderInput={(params) => (
                      <TextField {...params} label="Categories" placeholder="Select or type to add new" required={formData.categories.length === 0} />
                    )}
                  />
                  <Autocomplete
                    multiple
                    freeSolo
                    fullWidth
                    options={availableSubcategories}
                    value={formData.subcategories}
                    onChange={(_e, newValue) => setFormData(prev => ({ ...prev, subcategories: newValue }))}
                    renderTags={(value, getTagProps) =>
                      value.map((option, index) => (
                        <Chip variant="outlined" label={option} size="small" {...getTagProps({ index })} key={option} />
                      ))
                    }
                    renderInput={(params) => (
                      <TextField {...params} label="Subcategories" placeholder="Select or type to add new" required={formData.subcategories.length === 0} />
                    )}
                  />
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
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h6" fontWeight={700}>Product Details</Typography>
                <Button startIcon={<AddIcon />} onClick={addProductCode} size="small" variant="outlined">Add Product Code</Button>
              </Box>
              <Stack spacing={3}>
                <AnimatePresence mode="popLayout">
                  {productCodes.map((pc, codeIndex) => (
                    <motion.div key={codeIndex} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      <Box sx={{ p: 3, border: '1px solid', borderColor: 'divider', borderRadius: 3, position: 'relative' }}>
                        {codeIndex > 0 && (
                          <IconButton size="small" color="error" onClick={() => removeProductCode(codeIndex)} sx={{ position: 'absolute', top: 8, right: 8 }}>
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        )}
                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                          <TextField fullWidth label="Order Code" value={pc.order_code}
                            onChange={(e) => updateProductCode(codeIndex, 'order_code', e.target.value)} required={codeIndex === 0} />
                          <TextField fullWidth label="Single Price" type="number" value={pc.single_price}
                            onChange={(e) => updateProductCode(codeIndex, 'single_price', e.target.value)} required={codeIndex === 0}
                            InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }} />
                        </Stack>

                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 3, mb: 1.5 }}>
                          <Typography variant="subtitle2" fontWeight={700} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <PricingIcon fontSize="small" /> Bulk Price
                          </Typography>
                          <Button startIcon={<AddIcon />} onClick={() => addBulkTier(codeIndex)} size="small" variant="outlined">Add+</Button>
                        </Box>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                          <AnimatePresence mode="popLayout">
                            {pc.bulk_pricing.map((tier, tierIndex) => (
                              <motion.div key={tierIndex} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <TextField size="small" type="number" label="Buy Qty" value={tier.quantity} sx={{ width: 100 }}
                                    onChange={(e) => updateBulkTier(codeIndex, tierIndex, 'quantity', e.target.value)} />
                                  <TextField size="small" type="number" label="Price" value={tier.price} sx={{ width: 120 }}
                                    onChange={(e) => updateBulkTier(codeIndex, tierIndex, 'price', e.target.value)}
                                    InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }} />
                                  {pc.bulk_pricing.length > 1 && (
                                    <IconButton size="small" color="error" onClick={() => removeBulkTier(codeIndex, tierIndex)}>
                                      <DeleteIcon fontSize="small" />
                                    </IconButton>
                                  )}
                                </Box>
                              </motion.div>
                            ))}
                          </AnimatePresence>
                        </Box>
                      </Box>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </Stack>
            </Paper>

            {/* Documentation Links */}
            <Paper elevation={0} sx={{ p: 4, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
              <Typography variant="h6" gutterBottom fontWeight={700} sx={{ mb: 3 }}>Resource Links</Typography>
              <Stack spacing={3}>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                  <TextField fullWidth label="Product Webpage URL" name="productLink" value={formData.productLink} onChange={handleInputChange} />
                  <TextField fullWidth label="Data Sheet URL" name="dataSheetLink" value={formData.dataSheetLink} onChange={handleInputChange} />
                </Stack>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                  <TextField fullWidth label="User Manual URL" name="userManualLink" value={formData.userManualLink} onChange={handleInputChange} />
                  <TextField fullWidth label="Learning Center SDK URL" name="sdkLink" value={formData.sdkLink} onChange={handleInputChange} />
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

            {/* 5b. Application */}
            <Paper elevation={0} sx={{ p: 4, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                <Typography variant="h6" fontWeight={700}>Application</Typography>
                <Button startIcon={<PlaylistAddIcon />} onClick={() => addDynamicField(setApplications)} size="small" variant="outlined">Add Item</Button>
              </Box>
              <Stack spacing={2}>
                <AnimatePresence mode="popLayout">
                  {applications.map((item, index) => (
                    <motion.div key={index} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      <TextField fullWidth size="small" value={item} onChange={(e) => updateDynamicField(index, e.target.value, setApplications)}
                        InputProps={{
                          endAdornment: applications.length > 1 && (
                            <InputAdornment position="end">
                              <IconButton size="small" onClick={() => removeDynamicField(index, setApplications)} color="error"><DeleteIcon fontSize="small" /></IconButton>
                            </InputAdornment>
                          ),
                        }}
                      />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </Stack>
            </Paper>

            {/* 5c. Benefits */}
            <Paper elevation={0} sx={{ p: 4, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                <Typography variant="h6" fontWeight={700}>Benefits</Typography>
                <Button startIcon={<PlaylistAddIcon />} onClick={() => addDynamicField(setBenefits)} size="small" variant="outlined">Add Item</Button>
              </Box>
              <Stack spacing={2}>
                <AnimatePresence mode="popLayout">
                  {benefits.map((item, index) => (
                    <motion.div key={index} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      <TextField fullWidth size="small" value={item} onChange={(e) => updateDynamicField(index, e.target.value, setBenefits)}
                        InputProps={{
                          endAdornment: benefits.length > 1 && (
                            <InputAdornment position="end">
                              <IconButton size="small" onClick={() => removeDynamicField(index, setBenefits)} color="error"><DeleteIcon fontSize="small" /></IconButton>
                            </InputAdornment>
                          ),
                        }}
                      />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </Stack>
            </Paper>

            {/* 5d. Enclosure Dimensions */}
            <Paper elevation={0} sx={{ p: 4, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                <Typography variant="h6" fontWeight={700}>Enclosure Dimensions</Typography>
                <Button startIcon={<PlaylistAddIcon />} onClick={() => addDynamicField(setEnclosureDimensions)} size="small" variant="outlined">Add Item</Button>
              </Box>
              <Stack spacing={2}>
                <AnimatePresence mode="popLayout">
                  {enclosureDimensions.map((item, index) => (
                    <motion.div key={index} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      <TextField fullWidth size="small" value={item} onChange={(e) => updateDynamicField(index, e.target.value, setEnclosureDimensions)}
                        InputProps={{
                          endAdornment: enclosureDimensions.length > 1 && (
                            <InputAdornment position="end">
                              <IconButton size="small" onClick={() => removeDynamicField(index, setEnclosureDimensions)} color="error"><DeleteIcon fontSize="small" /></IconButton>
                            </InputAdornment>
                          ),
                        }}
                      />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </Stack>
            </Paper>

            {/* 6. FAQs */}
            <Paper elevation={0} sx={{ p: 4, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                <Typography variant="h6" fontWeight={700} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <FaqIcon fontSize="small" /> Frequently Asked Questions
                </Typography>
                <Button startIcon={<AddIcon />} onClick={addFaq} size="small" variant="outlined">Add FAQ</Button>
              </Box>
              <Stack spacing={3}>
                <AnimatePresence mode="popLayout">
                  {faqs.map((faq, index) => (
                    <motion.div key={index} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      <Stack spacing={1.5} sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 3, position: 'relative' }}>
                        <TextField fullWidth size="small" label="Question" value={faq.question}
                          onChange={(e) => updateFaq(index, 'question', e.target.value)} />
                        <TextField fullWidth size="small" label="Answer" multiline rows={2} value={faq.answer}
                          onChange={(e) => updateFaq(index, 'answer', e.target.value)} />
                        {faqs.length > 1 && (
                          <IconButton size="small" color="error" onClick={() => removeFaq(index)} sx={{ position: 'absolute', top: 8, right: 8 }}>
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        )}
                      </Stack>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </Stack>
            </Paper>

            {/* Submit Actions */}
            <Box sx={{ pt: 2, display: 'flex', gap: 2, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
              {isEdit && (
                <Button startIcon={<ContentCopyIcon />} onClick={handleCopyProduct} disabled={loading} sx={{ borderRadius: 3 }}>
                  Copy Product
                </Button>
              )}
              <Button startIcon={<DraftIcon />} onClick={handleSaveDraft} disabled={loading} sx={{ borderRadius: 3 }}>
                Save Draft
              </Button>
              <Button startIcon={<PreviewIcon />} onClick={() => setPreviewOpen(true)} disabled={loading} sx={{ borderRadius: 3 }}>
                Preview
              </Button>
              <Button onClick={() => navigate('/products')} disabled={loading}>Cancel</Button>
              <Button type="submit" variant="contained" startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SaveIcon />} disabled={loading} sx={{ borderRadius: 3, px: 6 }}>
                {loading ? 'Saving...' : (isEdit ? 'Update Product' : 'Create Product')}
              </Button>
            </Box>
          </Stack>
        </form>

        {/* Unsaved Draft Dialog */}
        <Dialog open={draftDialogOpen} onClose={handleDiscardDraft} maxWidth="xs" fullWidth>
          <DialogTitle sx={{ fontWeight: 800 }}>Restore Unsaved Draft?</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary">
              We found a draft you didn't finish saving. Do you want to restore it into this form, or discard it permanently?
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDiscardDraft} color="error">Discard Draft</Button>
            <Button onClick={handleRestoreDraft} variant="contained">Restore Draft</Button>
          </DialogActions>
        </Dialog>

        {/* Preview Dialog */}
        <Dialog open={previewOpen} onClose={() => setPreviewOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle sx={{ fontWeight: 800 }}>{formData.name || 'Untitled Product'}</DialogTitle>
          <DialogContent>
            <Stack spacing={2}>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                {formData.categories.map(c => <Chip key={c} label={c} size="small" color="primary" />)}
                {formData.subcategories.map(c => <Chip key={c} label={c} size="small" variant="outlined" />)}
              </Stack>
              {subheading && showSubheading && <Typography variant="subtitle1" color="text.secondary">{subheading}</Typography>}
              <Typography variant="body2"><strong>Order Code:</strong> {productCodes[0]?.order_code || '—'}</Typography>
              <Typography variant="body2"><strong>Price:</strong> {productCodes[0]?.single_price ? `$${productCodes[0].single_price}` : '—'}</Typography>
              {formData.description && (
                <>
                  <Divider />
                  <Typography variant="body2">{formData.description}</Typography>
                </>
              )}
              {features.filter(f => f.trim()).length > 0 && (
                <>
                  <Divider />
                  <Typography variant="subtitle2" fontWeight={700}>Features</Typography>
                  {features.filter(f => f.trim()).map((f, i) => <Typography key={i} variant="body2">• {f}</Typography>)}
                </>
              )}
              {packageItems.filter(p => p.trim()).length > 0 && (
                <>
                  <Divider />
                  <Typography variant="subtitle2" fontWeight={700}>Package Includes</Typography>
                  {packageItems.filter(p => p.trim()).map((p, i) => <Typography key={i} variant="body2">• {p}</Typography>)}
                </>
              )}
              {applications.filter(a => a.trim()).length > 0 && (
                <>
                  <Divider />
                  <Typography variant="subtitle2" fontWeight={700}>Application</Typography>
                  {applications.filter(a => a.trim()).map((a, i) => <Typography key={i} variant="body2">• {a}</Typography>)}
                </>
              )}
              {benefits.filter(b => b.trim()).length > 0 && (
                <>
                  <Divider />
                  <Typography variant="subtitle2" fontWeight={700}>Benefits</Typography>
                  {benefits.filter(b => b.trim()).map((b, i) => <Typography key={i} variant="body2">• {b}</Typography>)}
                </>
              )}
              {enclosureDimensions.filter(d => d.trim()).length > 0 && (
                <>
                  <Divider />
                  <Typography variant="subtitle2" fontWeight={700}>Enclosure Dimensions</Typography>
                  {enclosureDimensions.filter(d => d.trim()).map((d, i) => <Typography key={i} variant="body2">• {d}</Typography>)}
                </>
              )}
              {productCodes.some(pc => pc.bulk_pricing.some(t => t.quantity !== '' || t.price !== '')) && (
                <>
                  <Divider />
                  <Typography variant="subtitle2" fontWeight={700}>Bulk Pricing</Typography>
                  {productCodes.map((pc, i) => (
                    pc.bulk_pricing.filter(t => t.quantity !== '' || t.price !== '').length > 0 && (
                      <Box key={i}>
                        <Typography variant="caption" color="text.secondary">{pc.order_code || `Product Code ${i + 1}`}</Typography>
                        {pc.bulk_pricing.filter(t => t.quantity !== '' || t.price !== '').map((t, j) => (
                          <Typography key={j} variant="body2">Buy {t.quantity || '—'}: {t.price ? `$${t.price}` : '—'}</Typography>
                        ))}
                      </Box>
                    )
                  ))}
                </>
              )}
              {productCodes.length > 1 && (
                <>
                  <Divider />
                  <Typography variant="subtitle2" fontWeight={700}>Additional Order Codes</Typography>
                  {productCodes.slice(1).map((pc, i) => (
                    <Typography key={i} variant="body2">{pc.order_code || 'no code'} {pc.single_price ? `($${pc.single_price})` : ''}</Typography>
                  ))}
                </>
              )}
              {faqs.filter(f => f.question.trim()).length > 0 && (
                <>
                  <Divider />
                  <Typography variant="subtitle2" fontWeight={700}>FAQs</Typography>
                  {faqs.filter(f => f.question.trim()).map((f, i) => (
                    <Box key={i}>
                      <Typography variant="body2" fontWeight={600}>Q: {f.question}</Typography>
                      <Typography variant="body2" color="text.secondary">A: {f.answer || '—'}</Typography>
                    </Box>
                  ))}
                </>
              )}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setPreviewOpen(false)}>Close</Button>
          </DialogActions>
        </Dialog>
      </motion.div>
    </Container>
  )
}
