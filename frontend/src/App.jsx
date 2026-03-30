import { HashRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import DashboardLayout from './layout/DashboardLayout'
import LoginPage from './pages/LoginPage'
import Dashboard from './pages/Dashboard'
import LinkedInAnalytics from './pages/LinkedInAnalytics'
import CallAnalytics from './pages/CallAnalytics'
import UserAnalytics from './pages/UserAnalytics'
import LeadManagement from './pages/LeadManagement'
import UserFeedback from './pages/UserFeedback'
import AICallLogs from './pages/AICallLogs'
import Settings from './pages/Settings'
import Products from './pages/Products'
import AddProduct from './pages/AddProduct'

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="linkedin" element={<LinkedInAnalytics />} />
          <Route path="calls" element={<CallAnalytics />} />
          <Route path="users" element={<UserAnalytics />} />
          <Route path="leads" element={<LeadManagement />} />
          <Route path="feedback" element={<UserFeedback />} />
          <Route path="ai-logs" element={<AICallLogs />} />
          <Route path="products" element={<Products />} />
          <Route path="add-product" element={<AddProduct />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </Router>
  )
}
