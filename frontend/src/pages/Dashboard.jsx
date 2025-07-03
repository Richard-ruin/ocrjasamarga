// src/pages/Dashboard.jsx - Perbaikan error handling dan token
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import AdminLayout from "../components/AdminLayout";
import { useAuth } from "../context/AuthContext";
import { useNotification } from "../context/NotificationContext";
import axios from "axios";

const Dashboard = () => {
  const { user, logout } = useAuth();
  const { error, success } = useNotification();
  const [stats, setStats] = useState({
    jadwal: { total: 0, scheduled: 0, completed: 0, cancelled: 0, today: 0 },
    inspeksi: { total: 0, draft: 0, generated: 0, saved: 0 },
    history: { total: 0, this_week: 0 },
    recent_activities: { jadwal: [], inspeksi: [] }
  });
  const [loading, setLoading] = useState(true);

  // Perbaikan fetchStats dengan error handling yang lebih detail
  const fetchStats = async () => {
    try {
      setLoading(true);
      
      // Check if token exists
      const token = localStorage.getItem('token');
      console.log('Token exists:', !!token);
      
      if (!token) {
        error("Token tidak ditemukan. Silakan login kembali.");
        logout();
        return;
      }
      
      // Make request with proper headers and timeout
      const response = await axios.get("http://localhost:8000/api/dashboard/stats", {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        timeout: 10000 // 10 seconds timeout
      });
      
      console.log('Dashboard stats response:', response.data);
      setStats(response.data);
      
    } catch (err) {
      console.error("Error fetching stats:", err);
      
      // Detailed error handling
      if (err.code === 'ECONNABORTED') {
        error("Request timeout. Server mungkin sedang lambat.");
      } else if (err.response?.status === 401) {
        error("Sesi login telah berakhir. Silakan login kembali.");
        logout();
      } else if (err.response?.status === 404) {
        error("Endpoint dashboard tidak ditemukan");
      } else if (err.response?.status === 500) {
        error("Server error. Pastikan backend berjalan dengan benar.");
        console.error("Server error details:", err.response?.data);
      } else if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error')) {
        error("Tidak dapat terhubung ke server. Pastikan backend berjalan di http://localhost:8000");
      } else {
        error(`Gagal memuat statistik: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
      }
    } finally {
      setLoading(false);
    }
  };

  // Tambahkan fungsi untuk generate Excel dari cache
  const handleGenerateExcel = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        error("Token tidak ditemukan. Silakan login kembali.");
        return;
      }

      success("Mengambil data dari cache...");
      
      const response = await axios.post(
        "http://localhost:8000/api/inspeksi/generate-from-cache",
        {},
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
          responseType: 'blob'
        }
      );

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `inspeksi-cache-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      success("File Excel berhasil didownload!");
      
    } catch (err) {
      console.error("Error generating Excel:", err);
      if (err.response?.status === 400) {
        error("Tidak ada data cache untuk di-generate. Silakan input data terlebih dahulu.");
      } else {
        error("Gagal generate Excel: " + (err.response?.data?.detail || err.message));
      }
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  // Rest of component remains the same until Quick Actions section
  const StatCard = ({ title, value, icon, color, subtitle, trend }) => (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 mb-1">{title}</p>
          <p className={`text-3xl font-bold ${color}`}>{value}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
        </div>
        <div className={`w-14 h-14 rounded-xl flex items-center justify-center ${color.replace('text-', 'bg-').replace('-600', '-100')}`}>
          {icon}
        </div>
      </div>
      {trend && (
        <div className="mt-4 flex items-center space-x-2">
          <div className="flex items-center text-xs text-green-600">
            <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
            {trend}
          </div>
        </div>
      )}
    </div>
  );

  if (loading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Memuat statistik...</p>
          </div>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      {/* Welcome Section */}
      <div className="mb-8">
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-2xl p-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold mb-2">
                Selamat Datang, {user?.full_name}! 👋
              </h1>
              <p className="text-blue-100 text-lg">
                Kelola data infrastruktur Jasa Marga dengan mudah dan efisien
              </p>
              <div className="mt-4 flex items-center space-x-6 text-blue-100">
                <div className="flex items-center space-x-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="text-sm">
                    {new Date().toLocaleDateString('id-ID', { 
                      weekday: 'long', 
                      year: 'numeric', 
                      month: 'long', 
                      day: 'numeric' 
                    })}
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                  <span className="text-sm">System Online</span>
                </div>
              </div>
            </div>
            <div className="hidden md:block">
              <div className="w-32 h-32 bg-white/10 rounded-2xl flex items-center justify-center backdrop-blur-sm">
                <svg className="w-16 h-16 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions - PERBAIKAN: Tambah tombol Generate Excel */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Aksi Cepat</h2>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <Link
            to="/jadwal"
            className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-all duration-200 hover:scale-105 group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center group-hover:bg-blue-600 transition-colors">
                <svg className="w-6 h-6 text-blue-600 group-hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Buat Jadwal</h3>
                <p className="text-sm text-gray-500">Jadwal inspeksi baru</p>
              </div>
            </div>
          </Link>

          <Link
            to="/inspeksi"
            className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-all duration-200 hover:scale-105 group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center group-hover:bg-green-600 transition-colors">
                <svg className="w-6 h-6 text-green-600 group-hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Input Data</h3>
                <p className="text-sm text-gray-500">Inspeksi lapangan</p>
              </div>
            </div>
          </Link>

          <Link
            to="/history"
            className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-all duration-200 hover:scale-105 group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center group-hover:bg-purple-600 transition-colors">
                <svg className="w-6 h-6 text-purple-600 group-hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Lihat History</h3>
                <p className="text-sm text-gray-500">Data tersimpan</p>
              </div>
            </div>
          </Link>

          {/* PERBAIKAN: Tombol Generate Excel yang mengambil dari cache */}
          <button 
            onClick={handleGenerateExcel}
            className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-all duration-200 hover:scale-105 group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-yellow-100 rounded-xl flex items-center justify-center group-hover:bg-yellow-600 transition-colors">
                <svg className="w-6 h-6 text-yellow-600 group-hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Generate Excel</h3>
                <p className="text-sm text-gray-500">Download dari cache</p>
              </div>
            </div>
          </button>

          <button 
            onClick={fetchStats}
            className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-all duration-200 hover:scale-105 group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center group-hover:bg-orange-600 transition-colors">
                <svg className="w-6 h-6 text-orange-600 group-hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Refresh Data</h3>
                <p className="text-sm text-gray-500">Update statistik</p>
              </div>
            </div>
          </button>
        </div>
      </div>

      {/* Rest of the component remains the same... */}
      {/* Statistics Overview */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Statistik Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            title="Total Jadwal"
            value={stats.jadwal.total}
            subtitle={`${stats.jadwal.today} jadwal hari ini`}
            icon={
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            }
            color="text-blue-600"
            trend="+12% dari minggu lalu"
          />

          <StatCard
            title="Inspeksi Aktif"
            value={stats.inspeksi.draft}
            subtitle={`${stats.inspeksi.total} total inspeksi`}
            icon={
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            }
            color="text-green-600"
            trend="+8% dari bulan lalu"
          />

          <StatCard
            title="Data Tersimpan"
            value={stats.history.total}
            subtitle={`${stats.history.this_week} minggu ini`}
            icon={
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
              </svg>
            }
            color="text-purple-600"
            trend="+23% dari bulan lalu"
          />

          <StatCard
            title="Completion Rate"
            value={`${Math.round((stats.jadwal.completed / (stats.jadwal.total || 1)) * 100)}%`}
            subtitle={`${stats.jadwal.completed} selesai`}
            icon={
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            }
            color="text-orange-600"
            trend="+5% dari minggu lalu"
          />
        </div>
      </div>

      {/* Recent Activities */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Recent Jadwal */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Jadwal Terbaru</h3>
            <Link to="/jadwal" className="text-blue-600 hover:text-blue-800 text-sm font-medium">
              Lihat Semua →
            </Link>
          </div>
          <div className="space-y-3">
            {stats.recent_activities.jadwal.length > 0 ? (
              stats.recent_activities.jadwal.map((item, index) => (
                <div key={index} className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                  <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-900">{item.nama_inspektur}</p>
                    <p className="text-xs text-gray-500">
                      {new Date(item.tanggal).toLocaleDateString('id-ID')} • {item.status}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-gray-500 text-sm text-center py-4">Belum ada jadwal terbaru</p>
            )}
          </div>
        </div>

        {/* Recent Inspeksi */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Inspeksi Terbaru</h3>
            <Link to="/inspeksi" className="text-green-600 hover:text-green-800 text-sm font-medium">
              Lihat Semua →
            </Link>
          </div>
          <div className="space-y-3">
            {stats.recent_activities.inspeksi.length > 0 ? (
              stats.recent_activities.inspeksi.map((item, index) => (
                <div key={index} className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-900">
                      Inspeksi {item.status} • {item.data?.length || 0} data
                    </p>
                    <p className="text-xs text-gray-500">
                      {new Date(item.created_at).toLocaleDateString('id-ID')}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-gray-500 text-sm text-center py-4">Belum ada inspeksi terbaru</p>
            )}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
};

export default Dashboard;