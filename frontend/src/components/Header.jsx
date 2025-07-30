// src/components/Header.jsx - Updated with role display
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useNotification } from "../context/NotificationContext";

const Header = () => {
  const navigate = useNavigate();
  const { user, logout, isAdmin, isPetugas } = useAuth();
  const { success } = useNotification();

  const handleLogout = async () => {
    await logout();
    success("Logout berhasil!");
    navigate("/login");
  };

  const getRoleBadge = () => {
    if (isAdmin()) {
      return {
        text: "Administrator",
        color: "bg-red-500/80 border-red-400/30 text-white",
        icon: "👑"
      };
    } else if (isPetugas()) {
      return {
        text: "Petugas",
        color: "bg-green-500/80 border-green-400/30 text-white",
        icon: "👷"
      };
    }
    return {
      text: "User",
      color: "bg-gray-500/80 border-gray-400/30 text-white",
      icon: "👤"
    };
  };

  const roleBadge = getRoleBadge();

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
            <p className="text-blue-200 text-sm">Sistem Manajemen Data Infrastruktur v3.0</p>
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

          {/* User Info Display with Role */}
          <div className="flex items-center space-x-3 bg-white/10 px-4 py-2 rounded-lg backdrop-blur-sm border border-white/20">
            <div className="w-8 h-8 bg-gradient-to-r from-blue-400 to-blue-500 rounded-lg flex items-center justify-center">
              <span className="text-sm font-bold text-white">
                {user?.full_name?.charAt(0).toUpperCase() || "A"}
              </span>
            </div>
            <div className="hidden md:block text-left">
              <div className="flex items-center space-x-2">
                <span className="text-sm font-medium text-white">
                  {user?.full_name || "User"}
                </span>
                {/* Role Badge */}
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${roleBadge.color}`}>
                  <span className="mr-1">{roleBadge.icon}</span>
                  {roleBadge.text}
                </span>
              </div>
              <div className="text-xs text-blue-200">
                {user?.email || "user@ocrjasamarga.com"}
              </div>
            </div>
          </div>

          {/* Role-specific Quick Actions */}
          {isAdmin() && (
            <div className="hidden lg:flex items-center space-x-2">
              <button
                onClick={() => navigate('/users')}
                className="flex items-center space-x-2 bg-white/10 hover:bg-white/20 px-3 py-2 rounded-lg transition-all duration-200 backdrop-blur-sm border border-white/20"
                title="Kelola User"
              >
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                </svg>
                <span className="hidden xl:inline text-sm font-medium text-white">Admin Panel</span>
              </button>
            </div>
          )}

          {isPetugas() && (
            <div className="hidden lg:flex items-center space-x-2">
              <button
                onClick={() => navigate('/aset')}
                className="flex items-center space-x-2 bg-white/10 hover:bg-white/20 px-3 py-2 rounded-lg transition-all duration-200 backdrop-blur-sm border border-white/20"
                title="Kelola Aset"
              >
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
                <span className="hidden xl:inline text-sm font-medium text-white">Aset</span>
              </button>
              <button
                onClick={() => navigate('/inspeksi')}
                className="flex items-center space-x-2 bg-white/10 hover:bg-white/20 px-3 py-2 rounded-lg transition-all duration-200 backdrop-blur-sm border border-white/20"
                title="Inspeksi"
              >
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
                <span className="hidden xl:inline text-sm font-medium text-white">Inspeksi</span>
              </button>
            </div>
          )}

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

      {/* Role Notice Banner (optional) */}
      {isAdmin() && (
        <div className="bg-red-600/20 border-t border-red-500/30 px-6 py-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <svg className="w-4 h-4 text-red-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span className="text-sm text-red-100">
                Mode Administrator: Fokus pada pengelolaan user sistem
              </span>
            </div>
          </div>
        </div>
      )}

      {isPetugas() && (
        <div className="bg-green-600/20 border-t border-green-500/30 px-6 py-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <svg className="w-4 h-4 text-green-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm text-green-100">
                Mode Petugas: Akses penuh untuk operasional sistem
              </span>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

export default Header;