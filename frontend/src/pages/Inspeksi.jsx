// src/pages/Inspeksi.jsx - Updated with jadwal-based workflow
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import AdminLayout from "../components/AdminLayout";
import AddEditModal from "../components/AddEditModal";
import DeleteModal from "../components/DeleteModal";
import { useNotification } from "../context/NotificationContext";
import { useAuth } from "../context/AuthContext";
import axios from "axios";

const Inspeksi = () => {
  const { success, error, info } = useNotification();
  const { isPetugas } = useAuth();
  const navigate = useNavigate();
  const [jadwalList, setJadwalList] = useState([]);
  const [selectedJadwal, setSelectedJadwal] = useState(null);
  const [cacheData, setCacheData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [editIndex, setEditIndex] = useState(null);
  const [deleteIndex, setDeleteIndex] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Get token from localStorage
  const getAuthHeaders = () => {
    const token = localStorage.getItem('token');
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    };
  };

  const fetchJadwalForInspeksi = async () => {
    try {
      setLoading(true);
      const response = await axios.get("http://localhost:8000/api/inspeksi/jadwal", {
        headers: getAuthHeaders()
      });
      setJadwalList(response.data);
    } catch (err) {
      console.error("Error fetching jadwal for inspeksi:", err);
      error("Gagal memuat jadwal untuk inspeksi");
    } finally {
      setLoading(false);
    }
  };

  const fetchCacheData = async (jadwalId) => {
    try {
      const response = await axios.get(`http://localhost:8000/api/inspeksi/cache/${jadwalId}`, {
        headers: getAuthHeaders()
      });
      setCacheData(response.data);
    } catch (err) {
      console.error("Error fetching cache data:", err);
      error("Gagal memuat data cache");
    }
  };

  useEffect(() => {
    fetchJadwalForInspeksi();
  }, []);

  const handleStartInspeksi = async (jadwal) => {
    try {
      const response = await axios.post(`http://localhost:8000/api/inspeksi/start/${jadwal.id}`, {}, {
        headers: getAuthHeaders()
      });
      
      setSelectedJadwal(jadwal);
      fetchCacheData(jadwal.id);
      success("Inspeksi dimulai untuk jadwal: " + jadwal.nama_inspektur);
    } catch (err) {
      console.error("Error starting inspeksi:", err);
      error(err.response?.data?.detail || "Gagal memulai inspeksi");
    }
  };

  const handleAddData = async (formData) => {
    if (!selectedJadwal) {
      error("Silakan pilih jadwal terlebih dahulu");
      return;
    }

    try {
      const data = new FormData();
      data.append("jadwal_id", selectedJadwal.id);
      data.append("jalur", formData.jalur);
      data.append("kondisi", formData.kondisi);
      data.append("keterangan", formData.keterangan);
      data.append("foto", formData.foto);

      const response = await axios.post("http://localhost:8000/api/inspeksi/add", data, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          // Don't set Content-Type for FormData
        }
      });

      success("Data berhasil ditambahkan ke cache!");
      
      if (response.data.coordinates.latitude && response.data.coordinates.longitude) {
        info(`Koordinat berhasil diekstrak: ${response.data.coordinates.latitude}, ${response.data.coordinates.longitude}`);
      } else {
        info("Data ditambahkan, namun koordinat tidak berhasil diekstrak dari gambar");
      }

      setShowModal(false);
      setEditIndex(null);
      fetchCacheData(selectedJadwal.id);
    } catch (err) {
      console.error("Error adding data:", err);
      error(err.response?.data?.detail || "Gagal menambahkan data");
    }
  };

  const handleEdit = (index) => {
    setEditIndex(index);
    setShowModal(true);
  };

  const handleDeleteClick = (index) => {
    setDeleteIndex(index);
    setShowDeleteModal(true);
  };

  const handleDeleteConfirm = async () => {
    if (!selectedJadwal) return;

    try {
      const item = cacheData[deleteIndex];
      await axios.delete(`http://localhost:8000/api/inspeksi/delete/${selectedJadwal.id}/${item.no}`, {
        headers: getAuthHeaders()
      });
      success("Data berhasil dihapus!");
      setShowDeleteModal(false);
      setDeleteIndex(null);
      fetchCacheData(selectedJadwal.id);
    } catch (err) {
      console.error("Error deleting data:", err);
      error(err.response?.data?.detail || "Gagal menghapus data");
    }
  };

  const handleGenerate = async () => {
    if (!selectedJadwal || cacheData.length === 0) {
      error("Tidak ada data untuk di-generate");
      return;
    }

    setIsGenerating(true);
    
    try {
      const response = await axios.post(`http://localhost:8000/api/inspeksi/generate-from-cache/${selectedJadwal.id}`, {}, {
        responseType: "blob",
        timeout: 120000,
        headers: getAuthHeaders()
      });

      // Download file
      const blob = new Blob([response.data], { 
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" 
      });
      const url = URL.createObjectURL(blob);
      const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `inspeksi-jadwal-${selectedJadwal.id}-${timestamp}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);

      success("Excel berhasil di-generate dengan data aset dan jadwal!");
      
    } catch (err) {
      console.error("Error generating Excel:", err);
      error(err.response?.data?.detail || "Gagal generate Excel");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!selectedJadwal || cacheData.length === 0) {
      error("Tidak ada data untuk disimpan");
      return;
    }

    const confirmSave = window.confirm(
      "Setelah disimpan, jadwal akan ditandai selesai dan data cache akan dibersihkan. Lanjutkan?"
    );
    
    if (!confirmSave) return;

    setIsSaving(true);
    const formData = new FormData();
    
    try {
      // Prepare data for saving
      for (let i = 0; i < cacheData.length; i++) {
        const item = cacheData[i];
        
        formData.append("entries", JSON.stringify({
          no: item.no,
          jalur: item.jalur,
          kondisi: item.kondisi,
          keterangan: item.keterangan
        }));

        // Fetch image from cache
        if (item.foto_path) {
          try {
            const imageResponse = await axios.get(item.foto_path, { responseType: 'blob' });
            const imageFile = new File([imageResponse.data], item.foto_filename || `image_${i}.jpg`, {
              type: 'image/jpeg'
            });
            formData.append("images", imageFile);
          } catch (imgError) {
            console.error(`Failed to fetch image for item ${i+1}:`, imgError);
            // Create placeholder
            const emptyBlob = new Blob([''], { type: 'image/jpeg' });
            const emptyFile = new File([emptyBlob], 'placeholder.jpg', { type: 'image/jpeg' });
            formData.append("images", emptyFile);
          }
        } else {
          // No image - create placeholder
          const emptyBlob = new Blob([''], { type: 'image/jpeg' });
          const emptyFile = new File([emptyBlob], 'no-image.jpg', { type: 'image/jpeg' });
          formData.append("images", emptyFile);
        }
      }

      const response = await axios.post(`http://localhost:8000/api/inspeksi/save/${selectedJadwal.id}`, formData, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          // Don't set Content-Type for FormData
        },
        timeout: 60000
      });

      success(`Inspeksi berhasil diselesaikan! Total: ${response.data.total_saved} data`);
      
      // Reset state and go back to jadwal list
      setSelectedJadwal(null);
      setCacheData([]);
      fetchJadwalForInspeksi(); // Refresh jadwal list
      
    } catch (err) {
      console.error("Error saving data:", err);
      error(err.response?.data?.detail || "Gagal menyimpan data");
    } finally {
      setIsSaving(false);
    }
  };

  const handleBackToJadwal = () => {
    setSelectedJadwal(null);
    setCacheData([]);
    fetchJadwalForInspeksi();
  };

  const getKondisiColor = (kondisi) => {
    switch (kondisi) {
      case "baik": return "bg-green-100 text-green-800 border-green-200";
      case "sedang": return "bg-yellow-100 text-yellow-800 border-yellow-200";
      case "buruk": return "bg-red-100 text-red-800 border-red-200";
      default: return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const getKondisiIcon = (kondisi) => {
    switch (kondisi) {
      case "baik": return "🟢";
      case "sedang": return "🟡";
      case "buruk": return "🔴";
      default: return "⚪";
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
            <p className="text-gray-500">Hanya petugas yang dapat mengakses halaman Inspeksi.</p>
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
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Memuat data inspeksi...</p>
          </div>
        </div>
      </AdminLayout>
    );
  }

  // Show jadwal selection if no jadwal selected
  if (!selectedJadwal) {
    return (
      <AdminLayout>
        {/* Header Section */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Inspeksi Lapangan</h1>
              <p className="text-gray-600">Pilih jadwal untuk memulai inspeksi</p>
            </div>
            <div className="flex items-center space-x-2">
              <div className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                {jadwalList.length} Jadwal Siap
              </div>
            </div>
          </div>
        </div>

        {/* Jadwal Selection */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">Daftar Jadwal Inspeksi</h3>
            <p className="text-sm text-gray-600 mt-1">Pilih jadwal yang akan diinspeksi</p>
          </div>
          
          {jadwalList.length === 0 ? (
            <div className="p-12 text-center">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Tidak ada jadwal siap inspeksi</h3>
              <p className="text-gray-500 mb-4">Silakan buat jadwal terlebih dahulu di menu Jadwal.</p>
              <button
                onClick={() => navigate('/jadwal')}
                className="inline-flex items-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <span>Buat Jadwal</span>
              </button>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {jadwalList.map((jadwal) => (
                <div key={jadwal.id} className="p-6 hover:bg-gray-50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-start space-x-4">
                        <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                          <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                          </svg>
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-3 mb-2">
                            <h3 className="text-lg font-semibold text-gray-900">{jadwal.nama_inspektur}</h3>
                            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
                              {jadwal.status}
                            </span>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-600">
                            <div>
                              <p><span className="font-medium">Tanggal:</span> {formatDate(jadwal.tanggal)}</p>
                              <p><span className="font-medium">Waktu:</span> {formatTime(jadwal.waktu)}</p>
                            </div>
                            <div>
                              <p><span className="font-medium">Aset:</span> {jadwal.nama_aset || 'N/A'}</p>
                              <p><span className="font-medium">ID Aset:</span> {jadwal.id_aset || 'N/A'}</p>
                            </div>
                          </div>
                          <div className="mt-2">
                            <p className="text-sm text-gray-600">
                              <span className="font-medium">Alamat:</span> {jadwal.alamat}
                            </p>
                          </div>
                          {jadwal.keterangan && (
                            <div className="mt-2">
                              <p className="text-sm text-gray-500">
                                <span className="font-medium">Keterangan:</span> {jadwal.keterangan}
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="ml-6">
                      <button
                        onClick={() => handleStartInspeksi(jadwal)}
                        className="flex items-center space-x-2 bg-gradient-to-r from-green-600 to-green-700 text-white px-6 py-3 rounded-xl hover:from-green-700 hover:to-green-800 transition-all duration-200 shadow-lg hover:shadow-xl"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                        </svg>
                        <span>Mulai Inspeksi</span>
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </AdminLayout>
    );
  }

  // Show inspeksi form when jadwal selected
  return (
    <AdminLayout>
      {/* Header Section with Jadwal Info */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={handleBackToJadwal}
              className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              <span>Kembali ke Daftar Jadwal</span>
            </button>
          </div>
          <div className="flex items-center space-x-2">
            <div className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
              {cacheData.length} Data Cache
            </div>
          </div>
        </div>
        
        {/* Selected Jadwal Info */}
        <div className="mt-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200">
          <div className="flex items-start space-x-4">
            <div className="w-12 h-12 bg-blue-600 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold text-gray-900 mb-2">
                Inspeksi: {selectedJadwal.nama_inspektur}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-700">
                <div>
                  <p><span className="font-medium">Tanggal:</span> {formatDate(selectedJadwal.tanggal)}</p>
                  <p><span className="font-medium">Waktu:</span> {formatTime(selectedJadwal.waktu)}</p>
                </div>
                <div>
                  <p><span className="font-medium">Aset:</span> {selectedJadwal.nama_aset}</p>
                  <p><span className="font-medium">ID Aset:</span> {selectedJadwal.id_aset}</p>
                </div>
              </div>
              <div className="mt-2">
                <p className="text-sm text-gray-700">
                  <span className="font-medium">Alamat:</span> {selectedJadwal.alamat}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-4 mb-6">
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center space-x-2 bg-gradient-to-r from-green-600 to-green-700 text-white px-6 py-3 rounded-xl hover:from-green-700 hover:to-green-800 transition-all duration-200 shadow-lg hover:shadow-xl"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          <span>Tambah Data</span>
        </button>

        <button
          onClick={handleGenerate}
          disabled={cacheData.length === 0 || isGenerating}
          className="flex items-center space-x-2 bg-gradient-to-r from-purple-600 to-purple-700 text-white px-6 py-3 rounded-xl hover:from-purple-700 hover:to-purple-800 transition-all duration-200 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGenerating ? (
            <>
              <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Generating...</span>
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span>Generate Excel</span>
            </>
          )}
        </button>

        <button
          onClick={handleSave}
          disabled={cacheData.length === 0 || isSaving}
          className="flex items-center space-x-2 bg-gradient-to-r from-blue-600 to-blue-700 text-white px-6 py-3 rounded-xl hover:from-blue-700 hover:to-blue-800 transition-all duration-200 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSaving ? (
            <>
              <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Saving...</span>
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
              </svg>
              <span>Selesaikan Inspeksi</span>
            </>
          )}
        </button>
      </div>

      {/* Data Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Data Inspeksi</h3>
            <div className="text-sm text-gray-500">
              {cacheData.length} item
            </div>
          </div>
        </div>
        
        {cacheData.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Belum ada data inspeksi</h3>
            <p className="text-gray-500 mb-4">Mulai dengan menambahkan data inspeksi pertama untuk jadwal ini.</p>
            <button
              onClick={() => setShowModal(true)}
              className="inline-flex items-center space-x-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              <span>Tambah Data Pertama</span>
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">No</th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Jalur</th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Kondisi</th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Keterangan</th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Koordinat</th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Foto</th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Aksi</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {cacheData.map((item, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">{item.no}</td>
                    <td className="px-6 py-4 text-sm text-gray-900 max-w-xs">
                      <div className="truncate">{item.jalur}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border ${getKondisiColor(item.kondisi)}`}>
                        <span className="mr-1">{getKondisiIcon(item.kondisi)}</span>
                        {item.kondisi}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 max-w-xs">
                      <div className="truncate">{item.keterangan || "-"}</div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {item.latitude && item.longitude ? (
                        <div className="space-y-1">
                          <div className="text-xs font-mono bg-green-50 px-2 py-1 rounded border">
                            📍 {item.latitude}
                          </div>
                          <div className="text-xs font-mono bg-green-50 px-2 py-1 rounded border">
                            🌍 {item.longitude}
                          </div>
                        </div>
                      ) : (
                        <span className="text-gray-400 text-xs">Tidak tersedia</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <div className="flex items-center space-x-2">
                        <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        <span className="truncate max-w-20">{item.foto_filename || "image.jpg"}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="flex items-center space-x-3">
                        <button
                          onClick={() => handleEdit(i)}
                          className="text-blue-600 hover:text-blue-800 transition-colors"
                          title="Edit"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button
                          onClick={() => handleDeleteClick(i)}
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

      {/* Add/Edit Modal */}
      {showModal && (
        <AddEditModal
          initialData={editIndex !== null ? cacheData[editIndex] : null}
          onSave={handleAddData}
          onClose={() => {
            setShowModal(false);
            setEditIndex(null);
          }}
        />
      )}

      {/* Delete Modal */}
      <DeleteModal
        isOpen={showDeleteModal}
        title="Hapus Data Inspeksi"
        message="Apakah Anda yakin ingin menghapus data ini?"
        itemName={deleteIndex !== null ? `${cacheData[deleteIndex]?.jalur} (${cacheData[deleteIndex]?.kondisi})` : ""}
        onConfirm={handleDeleteConfirm}
        onClose={() => {
          setShowDeleteModal(false);
          setDeleteIndex(null);
        }}
      />
    </AdminLayout>
  );
};

export default Inspeksi;