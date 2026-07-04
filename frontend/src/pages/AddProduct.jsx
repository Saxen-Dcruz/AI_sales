import React, { useState, useEffect, useRef, useMemo } from 'react'
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
  Divider,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  Checkbox,
  Tooltip
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
  LocalOffer as PricingIcon,
  TableChart as TableChartIcon,
  CategoryRounded as CategoryIcon,
  QrCode2Rounded as CodeIcon,
  LinkRounded as LinkIcon,
  NotesRounded as NotesIcon,
  ChecklistRounded as ChecklistIcon,
  RocketLaunchRounded as ApplicationIcon,
  EmojiEventsRounded as BenefitsIcon,
  StraightenRounded as DimensionsIcon
} from '@mui/icons-material'
import { alpha } from '@mui/material/styles'
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
const emptyBulkTier = () => ({ quantity: '', discount_percent: '' })
const defaultBulkTiers = () => [
  { quantity: '10', discount_percent: '' },
  { quantity: '25', discount_percent: '' },
  { quantity: '100', discount_percent: '' }
]
const emptyProductCode = () => ({ order_code: '', single_price: '', bulk_pricing: defaultBulkTiers() })

const DRAFT_PREFIX = 'addProductDraft_'

// Shared card styling for every form section — rounded, subtle border, hover lift
const cardSx = {
  p: { xs: 2.5, sm: 3.5 },
  borderRadius: 3,
  border: '1px solid',
  borderColor: 'divider',
  bgcolor: 'background.paper',
  transition: 'box-shadow .25s ease, border-color .25s ease, transform .25s ease',
  '&:hover': { boxShadow: '0 12px 32px -16px rgba(0,0,0,0.22)', borderColor: 'primary.light' },
}

// Consistent iconed section header with an optional action button and subtitle
function SectionHeader({ icon, title, subtitle, action, accent = 'primary' }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 2, mb: subtitle ? 2 : 3, flexWrap: 'wrap' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, minWidth: 0 }}>
        <Box sx={{
          width: 42, height: 42, borderRadius: 2, display: 'grid', placeItems: 'center', flexShrink: 0,
          color: `${accent}.main`,
          bgcolor: (t) => alpha(t.palette[accent].main, 0.12),
        }}>
          {icon}
        </Box>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h6" fontWeight={700} lineHeight={1.25}>{title}</Typography>
          {subtitle && <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>{subtitle}</Typography>}
        </Box>
      </Box>
      {action && <Box sx={{ flexShrink: 0 }}>{action}</Box>}
    </Box>
  )
}

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
  // category -> [subcategories]; seeded with CATEGORY_MAP, extended from the catalog
  const [categorySubMap, setCategorySubMap] = useState(CATEGORY_MAP)

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
  // Order Information matrix: rows of { attribute, values[] }; values are index-aligned to productCodes
  const [orderInfoRows, setOrderInfoRows] = useState([])

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
        if (data?.category_subcategories) {
          setCategorySubMap(prev => {
            const merged = { ...prev }
            Object.entries(data.category_subcategories).forEach(([cat, subs]) => {
              merged[cat] = Array.from(new Set([...(merged[cat] || []), ...(subs || [])]))
            })
            return merged
          })
        }
      },
      () => {}
    )
  }, [])

  // Subcategory options depend on the selected categories. With no category chosen
  // yet, show every known subcategory; once categories are picked, narrow to their
  // mapped subcategories (already-selected values are always kept visible).
  const subcategoryOptions = useMemo(() => {
    if (!formData.categories.length) return availableSubcategories
    const opts = new Set()
    formData.categories.forEach(cat => (categorySubMap[cat] || []).forEach(s => opts.add(s)))
    formData.subcategories.forEach(s => opts.add(s))
    return Array.from(opts)
  }, [formData.categories, formData.subcategories, categorySubMap, availableSubcategories])

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

  // Convert legacy/back-end tier shapes (min_qty/price/final_price) into the
  // simple quantity/discount_percent tiers used by the Product Details form
  const normalizeBulkTiers = (tiers) => {
    if (!tiers?.length) return defaultBulkTiers()
    return tiers.map(t => ({
      quantity: t.quantity ?? t.min_qty ?? '',
      discount_percent: t.discount_percent ?? ''
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

    // Restore the Order Information matrix (round-trips via its own column)
    const oi = data.order_information
    if (oi?.rows?.length) {
      setOrderInfoRows(oi.rows.map(r => ({
        attribute: r.attribute || '',
        values: Array.isArray(r.values) ? r.values.map(v => (v ?? '').toString()) : []
      })))
    }
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
    if (draft.orderInfoRows) setOrderInfoRows(draft.orderInfoRows)
  }

  // ── Autosave to localStorage ────────────────────────────────────────────────
  useEffect(() => {
    if (!hasLoadedRef.current) return
    const timer = setTimeout(() => {
      const draft = { formData, subheading, showSubheading, features, packageItems, applications, benefits, enclosureDimensions, faqs, productCodes, orderInfoRows }
      localStorage.setItem(draftKey, JSON.stringify(draft))
    }, 800)
    return () => clearTimeout(timer)
  }, [formData, subheading, showSubheading, features, packageItems, applications, benefits, enclosureDimensions, faqs, productCodes, orderInfoRows, draftKey])

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
  const removeProductCode = (index) => {
    setProductCodes(prev => prev.filter((_, i) => i !== index))
    // Drop the matching column from every Order Information row to stay aligned
    setOrderInfoRows(prev => prev.map(row => ({
      ...row,
      values: (row.values || []).filter((_, i) => i !== index)
    })))
  }

  // ── Order Information matrix (per-order-code feature comparison) ─────────────
  // Cells are checkboxes: "✓" = the order code has the feature, "✗" = it doesn't.
  const FEATURE_YES = '✓'
  const FEATURE_NO = '✗'
  const orderInfoColumns = productCodes.map((pc, i) => pc.order_code?.trim() || `Code ${i + 1}`)
  const addOrderInfoRow = () =>
    setOrderInfoRows(prev => [...prev, { attribute: '', values: Array(productCodes.length).fill(FEATURE_NO) }])
  const removeOrderInfoRow = (rowIndex) =>
    setOrderInfoRows(prev => prev.filter((_, i) => i !== rowIndex))
  const updateOrderInfoAttribute = (rowIndex, value) =>
    setOrderInfoRows(prev => {
      const updated = [...prev]
      updated[rowIndex] = { ...updated[rowIndex], attribute: value }
      return updated
    })
  // Toggle a single cell's checkbox between ✓ and ✗
  const toggleOrderInfoValue = (rowIndex, colIndex) =>
    setOrderInfoRows(prev => {
      const updated = [...prev]
      const values = [...(updated[rowIndex].values || [])]
      while (values.length < productCodes.length) values.push(FEATURE_NO)
      values[colIndex] = values[colIndex] === FEATURE_YES ? FEATURE_NO : FEATURE_YES
      updated[rowIndex] = { ...updated[rowIndex], values }
      return updated
    })
  // Pull the Product Features list in as comparison rows. Existing rows (matched by
  // attribute text) keep their ticked checkboxes; brand-new features default to ✗.
  const loadFeaturesAsRows = () => {
    const featureList = features.map(f => f.trim()).filter(Boolean)
    setOrderInfoRows(prev => {
      const byAttribute = new Map(prev.map(r => [r.attribute.trim(), r]))
      return featureList.map(feature => {
        const existing = byAttribute.get(feature)
        const values = Array.from({ length: productCodes.length }, (_, i) =>
          existing?.values?.[i] === FEATURE_YES ? FEATURE_YES : FEATURE_NO
        )
        return { attribute: feature, values }
      })
    })
  }
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
    .filter(t => t.quantity !== '' || t.discount_percent !== '')
    .map(t => ({
      quantity: t.quantity !== '' ? parseFloat(t.quantity) : null,
      discount_percent: t.discount_percent !== '' ? parseFloat(t.discount_percent) : null
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

    // Order Information matrix — keep only rows with an attribute label, align values to codes
    const cleanOrderInfo = orderInfoRows
      .filter(r => r.attribute.trim())
      .map(r => ({
        attribute: r.attribute.trim(),
        values: productCodes.map((_, i) => (r.values?.[i] ?? '').toString())
      }))
    const orderInformation = cleanOrderInfo.length
      ? { order_codes: orderInfoColumns, rows: cleanOrderInfo }
      : null

    return {
      name: formData.name,
      order_code: mainCode.order_code,
      order_information: orderInformation,
      category: formData.categories[0] || '',
      sub_category: formData.subcategories[0] || '',
      categories: formData.categories,
      subcategories: formData.subcategories,
      single_price: parseFloat(mainCode.single_price) || 0,
      // Lowest tier's discount applied to single_price → effective bulk price in money
      bulk_price: mainBulkPricing[0]?.discount_percent != null
        ? Math.round((parseFloat(mainCode.single_price) || 0) * (1 - mainBulkPricing[0].discount_percent / 100) * 100) / 100
        : 0,
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
    const draft = { formData, subheading, showSubheading, features, packageItems, applications, benefits, enclosureDimensions, faqs, productCodes, orderInfoRows }
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
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/products')} sx={{ color: 'text.secondary', mb: 2 }}>
          Back to Products
        </Button>

        {/* Gradient banner */}
        <Box sx={{
          mb: 4, p: { xs: 3, sm: 4 }, borderRadius: 3, color: 'common.white',
          display: 'flex', alignItems: 'center', gap: 2.5,
          background: (t) => `linear-gradient(135deg, ${t.palette.primary.main} 0%, ${t.palette.primary.dark} 100%)`,
          boxShadow: (t) => `0 16px 40px -16px ${alpha(t.palette.primary.main, 0.6)}`,
        }}>
          <Box sx={{ width: 54, height: 54, borderRadius: 2.5, display: 'grid', placeItems: 'center', bgcolor: alpha('#fff', 0.18), flexShrink: 0 }}>
            <InventoryIcon sx={{ fontSize: 30 }} />
          </Box>
          <Box>
            <Typography variant="h4" fontWeight={800} lineHeight={1.1}>
              {isEdit ? 'Edit Product' : 'New Product'}
            </Typography>
            <Typography variant="body2" sx={{ opacity: 0.85, mt: 0.5 }}>
              {isEdit ? 'Update details, pricing and knowledge for this product.' : 'Fill in the details below to add a product to your catalog.'}
            </Typography>
          </Box>
        </Box>

        {statusMsg.text && (
          <Alert severity={statusMsg.type || 'info'} sx={{ mb: 4, borderRadius: 2 }} onClose={() => setStatusMsg({ type: '', text: '' })}>
            {statusMsg.text}
          </Alert>
        )}

        <form onSubmit={handleSubmit}>
          <Stack spacing={4}>

            {/* 1. Identity & Classification */}
            <Paper elevation={0} sx={cardSx}>
              <SectionHeader
                accent="primary"
                icon={<CategoryIcon />}
                title="Identity & Classification"
                subtitle="Name your product and place it in the catalog"
              />
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
                    options={subcategoryOptions}
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
            <Paper elevation={0} sx={cardSx}>
              <SectionHeader
                accent="info"
                icon={<CodeIcon />}
                title="Product Details"
                subtitle="Order codes, pricing and bulk tiers"
                action={<Button startIcon={<AddIcon />} onClick={addProductCode} size="small" variant="outlined">Add Product Code</Button>}
              />
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
                                  <TextField size="small" type="number" label="Discount" value={tier.discount_percent} sx={{ width: 120 }}
                                    onChange={(e) => updateBulkTier(codeIndex, tierIndex, 'discount_percent', e.target.value)}
                                    InputProps={{ endAdornment: <InputAdornment position="end">%</InputAdornment> }} />
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

            {/* 2b. Order Information Table — tick which features each Order Code has */}
            <Paper elevation={0} sx={cardSx}>
              <SectionHeader
                accent="secondary"
                icon={<TableChartIcon />}
                title="Order Information Table"
                action={
                  <Stack direction="row" spacing={1}>
                    <Tooltip title="Pull rows from the Product Features list below">
                      <span>
                        <Button startIcon={<PlaylistAddIcon />} onClick={loadFeaturesAsRows} size="small" variant="contained"
                          disabled={features.every(f => !f.trim())}>
                          Load Features
                        </Button>
                      </span>
                    </Tooltip>
                    <Button startIcon={<AddIcon />} onClick={addOrderInfoRow} size="small" variant="outlined">Add Row</Button>
                  </Stack>
                }
              />
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start', p: 1.5, mb: 2, borderRadius: 2, bgcolor: (t) => alpha(t.palette.info.main, 0.07) }}>
                <Typography variant="body2" color="text.secondary">
                  Columns are your Order Codes above. Click <strong>Load Features</strong> to turn the Product Features list into rows,
                  then tick the box under each Order Code (e.g. RDL838A) that includes that feature. A ticked box shows ✓, unticked shows ✗.
                </Typography>
              </Box>
              <TableContainer sx={{ overflowX: 'auto' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700, minWidth: 200 }}>Feature / Spec</TableCell>
                      {orderInfoColumns.map((col, i) => (
                        <TableCell key={i} align="center" sx={{ fontWeight: 700, minWidth: 110 }}>{col}</TableCell>
                      ))}
                      <TableCell padding="none" />
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {orderInfoRows.map((row, rowIndex) => (
                      <TableRow key={rowIndex}>
                        <TableCell>
                          <TextField size="small" fullWidth placeholder="e.g. Isolated Digital 4CH Inputs" value={row.attribute}
                            onChange={(e) => updateOrderInfoAttribute(rowIndex, e.target.value)} />
                        </TableCell>
                        {orderInfoColumns.map((_, colIndex) => (
                          <TableCell key={colIndex} align="center" padding="checkbox">
                            <Checkbox
                              color="success"
                              checked={row.values?.[colIndex] === FEATURE_YES}
                              onChange={() => toggleOrderInfoValue(rowIndex, colIndex)}
                            />
                          </TableCell>
                        ))}
                        <TableCell padding="none">
                          <IconButton size="small" color="error" onClick={() => removeOrderInfoRow(rowIndex)}>
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                    {orderInfoRows.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={orderInfoColumns.length + 2}>
                          <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
                            No rows yet — click “Load Features” to bring in your Product Features, or “Add Row” for a custom spec.
                          </Typography>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>

            {/* Documentation Links */}
            <Paper elevation={0} sx={cardSx}>
              <SectionHeader
                accent="info"
                icon={<LinkIcon />}
                title="Resource Links"
                subtitle="Webpage, datasheet, manual and SDK URLs"
              />
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
            <Paper elevation={0} sx={cardSx}>
              <SectionHeader
                accent="primary"
                icon={<NotesIcon />}
                title="Description"
                subtitle="A short overview of the product"
              />
              <TextField fullWidth multiline rows={5} name="description" value={formData.description} onChange={handleInputChange} />
            </Paper>

            {/* 4. Features */}
            <Paper elevation={0} sx={cardSx}>
              <SectionHeader
                accent="success"
                icon={<ChecklistIcon />}
                title="Product Features"
                subtitle="These feed the Order Information rows above"
                action={<Button startIcon={<PlaylistAddIcon />} onClick={() => addDynamicField(setFeatures)} size="small" variant="outlined">Add Feature</Button>}
              />
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
            <Paper elevation={0} sx={cardSx}>
              <SectionHeader
                accent="warning"
                icon={<InventoryIcon />}
                title="Package Includes"
                subtitle="What ships in the box"
                action={<Button startIcon={<InventoryIcon />} onClick={() => addDynamicField(setPackageItems)} size="small" variant="outlined">Add Item</Button>}
              />
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
            <Paper elevation={0} sx={cardSx}>
              <SectionHeader
                accent="info"
                icon={<ApplicationIcon />}
                title="Application"
                subtitle="Where this product is typically used"
                action={<Button startIcon={<PlaylistAddIcon />} onClick={() => addDynamicField(setApplications)} size="small" variant="outlined">Add Item</Button>}
              />
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
            <Paper elevation={0} sx={cardSx}>
              <SectionHeader
                accent="success"
                icon={<BenefitsIcon />}
                title="Benefits"
                subtitle="Why customers should choose it"
                action={<Button startIcon={<PlaylistAddIcon />} onClick={() => addDynamicField(setBenefits)} size="small" variant="outlined">Add Item</Button>}
              />
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
            <Paper elevation={0} sx={cardSx}>
              <SectionHeader
                accent="secondary"
                icon={<DimensionsIcon />}
                title="Enclosure Dimensions"
                subtitle="Physical size and form factor"
                action={<Button startIcon={<PlaylistAddIcon />} onClick={() => addDynamicField(setEnclosureDimensions)} size="small" variant="outlined">Add Item</Button>}
              />
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
            <Paper elevation={0} sx={cardSx}>
              <SectionHeader
                accent="primary"
                icon={<FaqIcon />}
                title="Frequently Asked Questions"
                subtitle="Answers the AI can use to reply to customers"
                action={<Button startIcon={<AddIcon />} onClick={addFaq} size="small" variant="outlined">Add FAQ</Button>}
              />
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

            {/* Submit Actions — sticky footer bar */}
            <Box sx={{
              position: 'sticky', bottom: 16, zIndex: 5, mt: 1,
              p: 1.5, display: 'flex', gap: 1.5, justifyContent: 'flex-end', flexWrap: 'wrap', alignItems: 'center',
              borderRadius: 3, border: '1px solid', borderColor: 'divider',
              bgcolor: (t) => alpha(t.palette.background.paper, 0.85),
              backdropFilter: 'blur(8px)',
              boxShadow: '0 8px 30px -12px rgba(0,0,0,0.25)',
            }}>
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
              <Box sx={{ flex: 1 }} />
              <Button onClick={() => navigate('/products')} disabled={loading} color="inherit">Cancel</Button>
              <Button type="submit" variant="contained" startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SaveIcon />} disabled={loading} sx={{ borderRadius: 3, px: 5, boxShadow: 'none' }}>
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
              {productCodes.some(pc => pc.bulk_pricing.some(t => t.quantity !== '' || t.discount_percent !== '')) && (
                <>
                  <Divider />
                  <Typography variant="subtitle2" fontWeight={700}>Bulk Pricing</Typography>
                  {productCodes.map((pc, i) => (
                    pc.bulk_pricing.filter(t => t.quantity !== '' || t.discount_percent !== '').length > 0 && (
                      <Box key={i}>
                        <Typography variant="caption" color="text.secondary">{pc.order_code || `Product Code ${i + 1}`}</Typography>
                        {pc.bulk_pricing.filter(t => t.quantity !== '' || t.discount_percent !== '').map((t, j) => (
                          <Typography key={j} variant="body2">Buy {t.quantity || '—'}: {t.discount_percent ? `${t.discount_percent}% off` : '—'}</Typography>
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
              {orderInfoRows.some(r => r.attribute.trim()) && (
                <>
                  <Divider />
                  <Typography variant="subtitle2" fontWeight={700}>Order Information</Typography>
                  {orderInfoRows.filter(r => r.attribute.trim()).map((r, i) => (
                    <Typography key={i} variant="body2">
                      <strong>{r.attribute}:</strong>{' '}
                      {orderInfoColumns.map((c, j) => `${c}=${r.values?.[j]?.trim() || '—'}`).join(', ')}
                    </Typography>
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
