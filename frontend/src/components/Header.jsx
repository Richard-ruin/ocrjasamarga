// src/components/Header.jsx - Versi yang disederhanakan dengan tombol logout langsung
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useNotification } from "../context/NotificationContext";

const Header = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { success } = useNotification();

  const handleLogout = async () => {
    await logout();
    success("Logout berhasil!");
    navigate("/login");
  };

  return (
    <header className="bg-gradient-to-r from-blue-800 to-blue-900 text-white shadow-lg relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-r from-blue-600/20 to-transparent"></div>
      <div className="relative z-10 flex items-center justify-between p-6">
        <div className="flex items-center space-x-4">
          <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center backdrop-blur-sm">
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">OCR Jasa Marga</h1>
            <p className="text-blue-200 text-sm">Sistem Manajemen Data Infrastruktur v2.0</p>
          </div>
        </div>
        
        <div className="flex items-center space-x-4">
          {/* Notifications */}
          <button className="relative p-2 text-blue-200 hover:text-white hover:bg-white/10 rounded-lg transition-all duration-200">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-5 5v-5zM4 6h16v12a2 2 0 01-2 2H6a2 2 0 01-2-2V6z" />
            </svg>
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full border-2 border-blue-800"></div>
          </button>

          {/* User Info Display */}
          <div className="flex items-center space-x-3 bg-white/10 px-4 py-2 rounded-lg backdrop-blur-sm border border-white/20">
            <div className="w-8 h-8 bg-gradient-to-r from-blue-400 to-blue-500 rounded-lg flex items-center justify-center">
              <span className="text-sm font-bold text-white">
                {user?.full_name?.charAt(0).toUpperCase() || "A"}
              </span>
            </div>
            <div className="hidden md:block text-left">
              <div className="text-sm font-medium text-white">
                {user?.full_name || "Admin User"}
              </div>
              <div className="text-xs text-blue-200">
                {user?.email || "admin@ocrjasamarga.com"}
              </div>
            </div>
          </div>

          {/* Direct Logout Button */}
          <button
            onClick={handleLogout}
            className="flex items-center space-x-2 bg-red-500/80 hover:bg-red-600 px-4 py-2 rounded-lg transition-all duration-200 backdrop-blur-sm border border-red-400/30 hover:border-red-300"
            title="Logout"
          >
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            <span className="hidden sm:inline text-sm font-medium text-white">Logout</span>
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;