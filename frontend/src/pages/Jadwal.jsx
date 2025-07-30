// src/pages/Jadwal.jsx - Fixed with proper error handling and UI improvements
import { useState, useEffect } from "react";
import AdminLayout from "../components/AdminLayout";
import DeleteModal from "../components/DeleteModal";
import { useNotification } from "../context/NotificationContext";
import { useAuth } from "../context/AuthContext";
import axios from "axios";

const Jadwal = () => {
  const { success, error } = useNotification();
  const { isPetugas } = useAuth();
  const [jadwalList, setJadwalList] = useState([]);
  const [asetList, setAsetList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [editingJadwal, setEditingJadwal] = useState(null);
  const [deleteJadwal, setDeleteJadwal] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [form, setForm] = useState({
    nama_inspektur: "",
    tanggal: "",
    waktu: "",
    alamat: "",
    id_aset: "",
    keterangan: "",
    status: "scheduled"
  });

  // Get token from localStorage
  const getAuthHeaders = () => {
    const token = localStorage.getItem('token');
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    };
  };

  const fetchJadwal = async () => {
    try {
      setLoading(true);
      const response = await axios.get("http://localhost:8000/api/jadwal", {
        headers: getAuthHeaders()
      });
      setJadwalList(response.data);
    } catch (err) {
      console.error("Error fetching jadwal:", err);
      error("Gagal memuat data jadwal");
    } finally {
      setLoading(false);
    }
  };

  const fetchAset = async () => {
    try {
      const response = await axios.get("http://localhost:8000/api/aset", {
        headers: getAuthHeaders()
      });
      // Filter only active assets
      const activeAset = response.data.filter(aset => aset.status === 'aktif');
      setAsetList(activeAset);
    } catch (err) {
      console.error("Error fetching aset:", err);
      error("Gagal memuat data aset");
    }
  };

  useEffect(() => {
    fetchJadwal();
    fetchAset();
  }, []);

  const resetForm = () => {
    setForm({
      nama_inspektur: "",
      tanggal: "",
      waktu: "",
      alamat: "",
      id_aset: "",
      keterangan: "",
      status: "scheduled"
    });
    setEditingJadwal(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validasi form
    if (!form.nama_inspektur.trim()) {
      error("Nama inspektur harus diisi");
      return;
    }
    
    if (!form.tanggal) {
      error("Tanggal harus diisi");
      return;
    }
    
    if (!form.waktu) {
      error("Waktu harus diisi");
      return;
    }
    
    if (!form.alamat.trim()) {
      error("Alamat harus diisi");
      return;
    }
    
    if (!form.id_aset) {
      error("Aset harus dipilih");
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      if (editingJadwal) {
        await axios.put(`http://localhost:8000/api/jadwal/${editingJadwal.id}`, form, {
          headers: getAuthHeaders()
        });
        success("Jadwal berhasil diperbarui!");
      } else {
        await axios.post("http://localhost:8000/api/jadwal", form, {
          headers: getAuthHeaders()
        });
        success("Jadwal berhasil ditambahkan!");
      }
      
      setShowForm(false);
      resetForm();
      fetchJadwal();
    } catch (err) {
      console.error("Error saving jadwal:", err);
      
      // Handle different error types
      let errorMessage = "Gagal menyimpan jadwal";
      
      if (err.response) {
        const { status, data } = err.response;
        
        if (status === 422) {
          // Validation error
          if (data.detail && typeof data.detail === 'string') {
            errorMessage = data.detail;
          } else if (data.detail && Array.isArray(data.detail)) {
            // Handle FastAPI validation errors array format
            const errors = data.detail.map(err => 
              `${err.loc ? err.loc.join(' → ') : 'Field'}: ${err.msg}`
            ).join(', ');
            errorMessage = `Validation error: ${errors}`;
          } else {
            errorMessage = "Data tidak valid, periksa kembali form";
          }
        } else if (status === 400) {
          errorMessage = data.detail || "Data tidak valid";
        } else if (status === 404) {
          errorMessage = "Aset tidak ditemukan";
        } else if (status === 500) {
          errorMessage = "Terjadi kesalahan server";
        } else {
          errorMessage = data.detail || `Error ${status}`;
        }
      } else if (err.request) {
        errorMessage = "Tidak dapat terhubung ke server";
      }
      
      error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEdit = (jadwal) => {
    setEditingJadwal(jadwal);
    setForm({
      nama_inspektur: jadwal.nama_inspektur,
      tanggal: jadwal.tanggal,
      waktu: jadwal.waktu,
      alamat: jadwal.alamat,
      id_aset: jadwal.id_aset || "",
      keterangan: jadwal.keterangan || "",
      status: jadwal.status
    });
    setShowForm(true);
  };

  const handleDeleteClick = (jadwal) => {
    setDeleteJadwal(jadwal);
    setShowDeleteModal(true);
  };

  const handleDeleteConfirm = async () => {
    try {
      await axios.delete(`http://localhost:8000/api/jadwal/${deleteJadwal.id}`, {
        headers: getAuthHeaders()
      });
      success("Jadwal berhasil dihapus!");
      setShowDeleteModal(false);
      setDeleteJadwal(null);
      fetchJadwal();
    } catch (err) {
      console.error("Error deleting jadwal:", err);
      error(err.response?.data?.detail || "Gagal menghapus jadwal");
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case "scheduled":
        return "bg-blue-100 text-blue-800 border-blue-200";
      case "completed":
        return "bg-green-100 text-green-800 border-green-200";
      case "cancelled":
        return "bg-red-100 text-red-800 border-red-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case "scheduled":
        return "Terjadwal";
      case "completed":
        return "Selesai";
      case "cancelled":
        return "Dibatalkan";
      default:
        return status;
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('id-ID', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const formatTime = (timeString) => {
    return new Date(`2000-01-01T${timeString}`).toLocaleTimeString('id-ID', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Redirect if not petugas
  if (!isPetugas()) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Akses Ditolak</h3>
            <p className="text-gray-500">Hanya petugas yang dapat mengakses halaman Jadwal.</p>
          </div>
        </div>
      </AdminLayout>
    );
  }

  if (loading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Memuat jadwal...</p>
          </div>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Jadwal Inspeksi</h1>
            <p className="text-gray-600">Kelola jadwal inspeksi lapangan dengan aset</p>
          </div>
          <div className="flex items-center space-x-3">
            <div className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
              {jadwalList.length} Jadwal
            </div>
            <button
              onClick={() => {
                resetForm();
                setShowForm(true);
              }}
              className="flex items-center space-x-2 bg-gradient-to-r from-blue-600 to-blue-700 text-white px-6 py-3 rounded-xl hover:from-blue-700 hover:to-blue-800 transition-all duration-200 shadow-lg hover:shadow-xl"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              <span>Tambah Jadwal</span>
            </button>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Total Jadwal</p>
              <p className="text-2xl font-bold text-gray-900">{jadwalList.length}</p>
            </div>
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Terjadwal</p>
              <p className="text-2xl font-bold text-blue-600">
                {jadwalList.filter(j => j.status === 'scheduled').length}
              </p>
            </div>
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <span className="text-2xl">📅</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Selesai</p>
              <p className="text-2xl font-bold text-green-600">
                {jadwalList.filter(j => j.status === 'completed').length}
              </p>
            </div>
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <span className="text-2xl">✅</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Dibatalkan</p>
              <p className="text-2xl font-bold text-red-600">
                {jadwalList.filter(j => j.status === 'cancelled').length}
              </p>
            </div>
            <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
              <span className="text-2xl">❌</span>
            </div>
          </div>
        </div>
      </div>

      {/* Jadwal Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Daftar Jadwal</h3>
        </div>
        
        {jadwalList.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Belum ada jadwal</h3>
            <p className="text-gray-500 mb-4">Mulai dengan menambahkan jadwal inspeksi pertama.</p>
            <button
              onClick={() => {
                resetForm();
                setShowForm(true);
              }}
              className="inline-flex items-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              <span>Tambah Jadwal Pertama</span>
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Inspektur</th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Aset</th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tanggal & Waktu</th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Alamat</th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Aksi</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {jadwalList.map((jadwal) => (
                  <tr key={jadwal.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{jadwal.nama_inspektur}</div>
                        {jadwal.keterangan && (
                          <div className="text-sm text-gray-500 truncate max-w-xs">{jadwal.keterangan}</div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {jadwal.nama_aset || 'Aset tidak ditemukan'}
                        </div>
                        {jadwal.jenis_aset && (
                          <div className="text-xs text-gray-400">{jadwal.jenis_aset}</div>
                        )}
                        {jadwal.lokasi_aset && (
                          <div className="text-xs text-gray-400">{jadwal.lokasi_aset}</div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div>
                        <div className="text-sm text-gray-900">{formatDate(jadwal.tanggal)}</div>
                        <div className="text-sm text-gray-500">{formatTime(jadwal.waktu)}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-900 max-w-xs truncate">{jadwal.alamat}</div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(jadwal.status)}`}>
                        {getStatusText(jadwal.status)}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-3">
                        <button
                          onClick={() => handleEdit(jadwal)}
                          className="text-blue-600 hover:text-blue-800 transition-colors"
                          title="Edit"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button
                          onClick={() => handleDeleteClick(jadwal)}
                          className="text-red-600 hover:text-red-800 transition-colors"
                          title="Hapus"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
            <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold text-white">
                  {editingJadwal ? "Edit Jadwal" : "Tambah Jadwal Baru"}
                </h2>
                <button
                  onClick={() => setShowForm(false)}
                  disabled={isSubmitting}
                  className="text-white/70 hover:text-white transition-colors disabled:opacity-50"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-6 max-h-[calc(90vh-80px)] overflow-y-auto">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Nama Inspektur <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    placeholder="Masukkan nama inspektur"
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                    value={form.nama_inspektur}
                    onChange={(e) => setForm({ ...form, nama_inspektur: e.target.value })}
                    disabled={isSubmitting}
                    required
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Pilih Aset <span className="text-red-500">*</span>
                  </label>
                  <select
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                    value={form.id_aset}
                    onChange={(e) => setForm({ ...form, id_aset: e.target.value })}
                    disabled={isSubmitting}
                    required
                  >
                    <option value="">Pilih aset untuk inspeksi</option>
                    {asetList.map((aset) => (
                      <option key={aset._id || aset.id} value={aset.id_aset}>
                        {aset.nama_aset} ({aset.jenis_aset})
                      </option>
                    ))}
                  </select>
                  {asetList.length === 0 && (
                    <p className="text-sm text-amber-600 mt-1">
                      ⚠️ Tidak ada aset aktif. Silakan tambahkan aset terlebih dahulu.
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Tanggal <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                    value={form.tanggal}
                    onChange={(e) => setForm({ ...form, tanggal: e.target.value })}
                    disabled={isSubmitting}
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Waktu <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="time"
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                    value={form.waktu}
                    onChange={(e) => setForm({ ...form, waktu: e.target.value })}
                    disabled={isSubmitting}
                    required
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Alamat Inspeksi <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    placeholder="Masukkan alamat lengkap lokasi inspeksi"
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 resize-none"
                    rows="3"
                    value={form.alamat}
                    onChange={(e) => setForm({ ...form, alamat: e.target.value })}
                    disabled={isSubmitting}
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
                  <select
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                    value={form.status}
                    onChange={(e) => setForm({ ...form, status: e.target.value })}
                    disabled={isSubmitting}
                  >
                    <option value="scheduled">Terjadwal</option>
                    <option value="completed">Selesai</option>
                    <option value="cancelled">Dibatalkan</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Keterangan</label>
                  <input
                    type="text"
                    placeholder="Keterangan tambahan (opsional)"
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                    value={form.keterangan}
                    onChange={(e) => setForm({ ...form, keterangan: e.target.value })}
                    disabled={isSubmitting}
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-3 pt-4 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  disabled={isSubmitting}
                  className="px-6 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors font-medium disabled:opacity-50"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || asetList.length === 0}
                  className={`px-6 py-3 rounded-xl font-medium shadow-lg hover:shadow-xl flex items-center space-x-2 transition-all duration-200 ${
                    isSubmitting || asetList.length === 0
                      ? 'bg-gray-400 cursor-not-allowed' 
                      : 'bg-gradient-to-r from-blue-600 to-blue-700 text-white hover:from-blue-700 hover:to-blue-800'
                  }`}
                >
                  {isSubmitting ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      <span>Menyimpan...</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      <span>{editingJadwal ? "Perbarui" : "Simpan"} Jadwal</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      <DeleteModal
        isOpen={showDeleteModal}
        title="Hapus Jadwal"
        message="Apakah Anda yakin ingin menghapus jadwal ini?"
        itemName={deleteJadwal?.nama_inspektur}
        onConfirm={handleDeleteConfirm}
        onClose={() => {
          setShowDeleteModal(false);
          setDeleteJadwal(null);
        }}
      />
    </AdminLayout>
  );
};

export default Jadwal;