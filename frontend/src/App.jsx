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
import KnowledgeBase from './pages/KnowledgeBase'
import AIAnalytics from './pages/AIAnalytics'
import GapsPage from './pages/GapsPage'
import GmailIntegration from './pages/GmailIntegration'
import CalendarIntegration from './pages/CalendarIntegration'
import EmbeddingsPage from './pages/EmbeddingsPage'
import GmailAnalytics from './pages/GmailAnalytics'

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
          <Route path="ai-analytics" element={<AIAnalytics />} />
          <Route path="gaps" element={<GapsPage />} />
          <Route path="gmail" element={<GmailIntegration />} />
          <Route path="calendar" element={<CalendarIntegration />} />
          <Route path="products" element={<Products />} />
          <Route path="add-product" element={<AddProduct />} />
          <Route path="edit-product/:id" element={<AddProduct />} />
          <Route path="knowledge-base/:id" element={<KnowledgeBase />} />
          <Route path="embeddings" element={<EmbeddingsPage />} />
          <Route path="gmail-analytics" element={<GmailAnalytics />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </Router>
  )
}
