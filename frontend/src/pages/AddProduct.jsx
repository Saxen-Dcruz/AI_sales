import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Save, Image as ImageIcon, Plus, Trash2, X } from 'lucide-react'

const CATEGORY_MAP = {
  'Software': ['Voice AI', 'Chatbot', 'CRM'],
  'Services': ['Consulting', 'Implementation'],
  'Add-on': ['Storage', 'API Access']
}

export default function AddProduct() {
  const [formData, setFormData] = useState({
    name: '',
    orderCode: '',
    brand: '',
    category: '',
    subcategory: '',
    singlePrice: '',
    bulkPrice: '',
    description: '',
    subheading: '',
    status: 'Draft'
  })

  const [features, setFeatures] = useState([''])
  const [packageItems, setPackageItems] = useState([''])

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value,
      // Reset subcategory if category changes
      ...(name === 'category' ? { subcategory: '' } : {})
    }))
  }

  const handleDynamicChange = (index, value, setter) => {
    setter(prev => {
      const updated = [...prev]
      updated[index] = value
      return updated
    })
  }

  const addDynamicField = (setter) => {
    setter(prev => [...prev, ''])
  }

  const removeDynamicField = (index, setter, currentList) => {
    if (currentList.length > 1) {
      setter(prev => prev.filter((_, i) => i !== index))
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const finalData = {
      ...formData,
      features: features.filter(f => f.trim() !== ''),
      packageContains: packageItems.filter(p => p.trim() !== '')
    }
    console.log('Submitting Product Data:', finalData)
    // Here we would call the ApiService if available
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 16 }} 
      animate={{ opacity: 1, y: 0 }} 
      className="space-y-6 max-w-5xl mx-auto pb-12"
    >
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Add New Product</h1>
          <p className="text-sm text-gray-500 mt-1">Configure your product specifications and pricing</p>
        </div>
        <div className="flex gap-3">
          <button className="btn-ghost">Cancel</button>
          <button onClick={handleSubmit} className="btn-primary flex items-center gap-2">
            <Save size={16} />
            Save Product
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Main Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Identity & Classification */}
          <div className="glass-card p-6 space-y-5">
            <h2 className="text-lg font-semibold text-gray-900 border-b border-gray-100 pb-3">Identity & Classification</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">Product Name</label>
                <input 
                  type="text" 
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-medium" 
                  placeholder="e.g. Enterprise Voice AI" 
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">Order Code</label>
                <input 
                  type="text" 
                  name="orderCode"
                  value={formData.orderCode}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all" 
                  placeholder="e.g. AI-VOC-001" 
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">Brand</label>
                <input 
                  type="text" 
                  name="brand"
                  value={formData.brand}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all" 
                  placeholder="e.g. Lumina AI" 
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">Status</label>
                <select 
                  name="status"
                  value={formData.status}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 transition-all"
                >
                  <option value="Draft">Draft</option>
                  <option value="Active">Active</option>
                  <option value="Archived">Archived</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">Category</label>
                <select 
                  name="category"
                  value={formData.category}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 transition-all"
                >
                  <option value="">Select Category</option>
                  {Object.keys(CATEGORY_MAP).map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">Subcategory</label>
                <select 
                  name="subcategory"
                  value={formData.subcategory}
                  onChange={handleInputChange}
                  disabled={!formData.category}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <option value="">Select Subcategory</option>
                  {formData.category && CATEGORY_MAP[formData.category].map(sub => (
                    <option key={sub} value={sub}>{sub}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Pricing & Subheading */}
          <div className="glass-card p-6 space-y-5">
            <h2 className="text-lg font-semibold text-gray-900 border-b border-gray-100 pb-3">Pricing & Subheading</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">Single Price ($)</label>
                <input 
                  type="number" 
                  name="singlePrice"
                  value={formData.singlePrice}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 transition-all" 
                  placeholder="0.00" 
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">Bulk Price ($)</label>
                <input 
                  type="number" 
                  name="bulkPrice"
                  value={formData.bulkPrice}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 transition-all" 
                  placeholder="0.00" 
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-gray-700">Subheading</label>
              <input 
                type="text" 
                name="subheading"
                value={formData.subheading}
                onChange={handleInputChange}
                className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 transition-all" 
                placeholder="Brief tagline for the product" 
              />
            </div>
          </div>

          {/* Features Dynamic Section */}
          <div className="glass-card p-6 space-y-5">
            <div className="flex justify-between items-center border-b border-gray-100 pb-3">
              <h2 className="text-lg font-semibold text-gray-900">Product Features</h2>
              <button 
                type="button"
                onClick={() => addDynamicField(setFeatures)}
                className="text-blue-600 hover:text-blue-700 text-sm font-medium flex items-center gap-1"
              >
                <Plus size={16} />
                Add More
              </button>
            </div>
            
            <div className="space-y-3">
              <AnimatePresence>
                {features.map((feature, index) => (
                  <motion.div 
                    key={index}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="flex gap-2"
                  >
                    <input 
                      type="text" 
                      value={feature}
                      onChange={(e) => handleDynamicChange(index, e.target.value, setFeatures)}
                      className="flex-1 px-4 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 transition-all" 
                      placeholder={`Feature point ${index + 1}`} 
                    />
                    <button 
                      type="button"
                      onClick={() => removeDynamicField(index, setFeatures, features)}
                      className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                      disabled={features.length === 1}
                    >
                      <Trash2 size={18} />
                    </button>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>
        </div>

        {/* Right Column - Image & Package */}
        <div className="space-y-6">
          {/* Product Image */}
          <div className="glass-card p-6 space-y-5">
            <h2 className="text-sm font-semibold text-gray-900 border-b border-gray-100 pb-3">Product Image</h2>
            <div className="w-full h-40 border-2 border-dashed border-gray-200 rounded-xl flex flex-col items-center justify-center text-gray-400 bg-gray-50 hover:bg-gray-100 hover:border-gray-300 transition-colors cursor-pointer group">
              <ImageIcon size={32} className="mb-2 group-hover:text-blue-500 transition-colors" />
              <span className="text-xs font-medium">Click to upload</span>
              <span className="text-[10px] mt-1">PNG, JPG up to 5MB</span>
            </div>
          </div>

          {/* Description */}
          <div className="glass-card p-6 space-y-4">
            <h2 className="text-sm font-semibold text-gray-900 border-b border-gray-100 pb-3">Description</h2>
            <textarea 
              rows={6} 
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 transition-all resize-none" 
              placeholder="Detailed product overview..."
            ></textarea>
          </div>

          {/* Package Contains Dynamic Section */}
          <div className="glass-card p-6 space-y-5">
            <div className="flex justify-between items-center border-b border-gray-100 pb-3">
              <h2 className="text-sm font-semibold text-gray-900">Package Contains</h2>
              <button 
                type="button"
                onClick={() => addDynamicField(setPackageItems)}
                className="text-blue-600 hover:text-blue-700 text-xs font-medium flex items-center gap-1"
              >
                <Plus size={14} />
                Add
              </button>
            </div>
            
            <div className="space-y-2">
              <AnimatePresence>
                {packageItems.map((item, index) => (
                  <motion.div 
                    key={index}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, x: 10 }}
                    className="flex gap-2"
                  >
                    <input 
                      type="text" 
                      value={item}
                      onChange={(e) => handleDynamicChange(index, e.target.value, setPackageItems)}
                      className="flex-1 px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-900 focus:outline-none focus:border-blue-500 transition-all" 
                      placeholder="e.g. API Docs" 
                    />
                    <button 
                      type="button"
                      onClick={() => removeDynamicField(index, setPackageItems, packageItems)}
                      className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
                      disabled={packageItems.length === 1}
                    >
                      <X size={14} />
                    </button>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
