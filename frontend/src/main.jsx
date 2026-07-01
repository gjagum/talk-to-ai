import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import App from './App.jsx'
import { AuthProvider } from './lib/auth'
import ProtectedRoute from './components/ProtectedRoute'
import HomePage from './pages/HomePage'
import BookingsPage from './pages/BookingsPage'
import DriveThruPage from './pages/DriveThruPage'
import LoginPage from './pages/LoginPage'
import ManagementPage from './pages/ManagementPage'
import './index.css'

/**
 * Route map.
 *
 *   /                → HomePage       (public voice playground)
 *   /bookings        → BookingsPage   (public demo)
 *   /drive-thru      → DriveThruPage  (public demo)
 *   /login           → LoginPage      (public)
 *   /management      → ManagementPage (auth + agent:read)
 *
 * AuthProvider wraps the router so useAuth() works everywhere (Nav link
 * gating, ProtectedRoute, LoginPage). Unknown paths fall back to /.
 */
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<App />}>
            <Route index element={<HomePage />} />
            <Route path="bookings" element={<BookingsPage />} />
            <Route path="drive-thru" element={<DriveThruPage />} />
            <Route path="login" element={<LoginPage />} />
            <Route
              path="management"
              element={
                <ProtectedRoute permission="agent:read">
                  <ManagementPage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>,
)
