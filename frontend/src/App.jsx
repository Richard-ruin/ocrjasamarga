// src/App.jsx
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Jadwal from "./pages/Jadwal";
import Inspeksi from "./pages/Inspeksi";
import History from "./pages/History";
import EditDashboard from "./pages/EditDashboard";
import PrivateRoute from "./utils/PrivateRoute";
import { AuthProvider } from "./context/AuthContext";
import { NotificationProvider } from "./context/NotificationContext";
import UserManagement from "./pages/UserManagement";

function App() {
  return (
    <AuthProvider>
      <NotificationProvider>
        <Router>
          <Routes>
            <Route path="/" element={<Login />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route 
              path="/dashboard" 
              element={
                <PrivateRoute>
                  <Dashboard />
                </PrivateRoute>
              } 
            />
            <Route 
              path="/jadwal" 
              element={
                <PrivateRoute>
                  <Jadwal />
                </PrivateRoute>
              } 
            />
            <Route 
              path="/inspeksi" 
              element={
                <PrivateRoute>
                  <Inspeksi />
                </PrivateRoute>
              } 
            />
            <Route 
              path="/history" 
              element={
                <PrivateRoute>
                  <History />
                </PrivateRoute>
              } 
            />
            <Route 
              path="/users" 
              element={
                <PrivateRoute>
                  <UserManagement />
                </PrivateRoute>
              } 
            />
            <Route 
              path="/edit/:id" 
              element={
                <PrivateRoute>
                  <EditDashboard />
                </PrivateRoute>
              } 
            />
          </Routes>
        </Router>
      </NotificationProvider>
    </AuthProvider>
  );
}

export default App;