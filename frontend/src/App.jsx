import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { useAuth } from './hooks/useAuth'
import { Sidebar } from './components/ui/sidebar'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Enquiries from './pages/Enquiries'
import Quotes from './pages/Quotes'
import AdminPending from './pages/admin/Pending'
import AdminApproved from './pages/admin/Approved'
import AdminDocuments from './pages/admin/Documents'
import AdminKnowledgeBase from './pages/admin/KnowledgeBase'
import AdminDecisionTrees from './pages/admin/DecisionTrees'

function PrivateRoute({ children }) {
  const { token } = useAuth()
  return token ? children : <Navigate to="/login" />
}

function AdminRoute({ children }) {
  const { user, token } = useAuth()
  return token && user?.role === 'admin' ? children : <Navigate to="/" />
}

function App() {
  const { token } = useAuth()

  if (!token) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="*" element={<Navigate to="/login" />} />
      </Routes>
    )
  }

  return (
    <div className="flex h-screen w-screen flex-col md:flex-row bg-neutral-100">
      <Sidebar />
      <main className="flex h-screen grow flex-col overflow-auto bg-white md:rounded-l-3xl">
        <Routes>
          <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/enquiries" element={<PrivateRoute><Enquiries /></PrivateRoute>} />
          <Route path="/quotes" element={<PrivateRoute><Quotes /></PrivateRoute>} />
          
          {/* Admin Routes */}
          <Route path="/admin/pending" element={<AdminRoute><AdminPending /></AdminRoute>} />
          <Route path="/admin/approved" element={<AdminRoute><AdminApproved /></AdminRoute>} />
          <Route path="/admin/documents" element={<AdminRoute><AdminDocuments /></AdminRoute>} />
          <Route path="/admin/knowledge-base" element={<AdminRoute><AdminKnowledgeBase /></AdminRoute>} />
          <Route path="/admin/decision-trees" element={<AdminRoute><AdminDecisionTrees /></AdminRoute>} />
          
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
