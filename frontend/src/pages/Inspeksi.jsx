// src/pages/Inspeksi.jsx
import { useState, useEffect } from "react";
import AdminLayout from "../components/AdminLayout";
import AddEditModal from "../components/AddEditModal";
import DeleteModal from "../components/DeleteModal";
import { useNotification } from "../context/NotificationContext";
import axios from "axios";
import dayjs from "dayjs";

const Inspeksi = () => {
  const { success, error, info } = useNotification();
  const [cacheData, setCacheData] = useState([]);
  const [stats, setStats] = useState({
    cache: { total_entries: 0, has_data: false },
    history: { total_saved: 0 },
    ocr_accuracy: {
      total_entries: 0,
      entries_with_coordinates: 0,
      coordinate_extraction_rate: 0,
      valid_indonesia_rate: 0
    }
  });
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [editIndex, setEditIndex] = useState(null);
  const [deleteIndex, setDeleteIndex] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const fetchCacheData = async () => {
    try {
      setLoading(true);
      const response = await axios.get("http://localhost:8000/api/inspeksi/all");
      setCacheData(response.data);
    } catch (err) {
      console.error("Error fetching cache data:", err);
      error("Gagal memuat data cache");
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get("http://localhost:8000/api/inspeksi/stats");
      setStats(response.data);
    } catch (err) {
      console.error("Error fetching stats:", err);
    }
  };

  useEffect(() => {
    fetchCacheData();
    fetchStats();
  }, []);

  const handleAddData = async (formData) => {
    try {
      const data = new FormData();
      data.append("jalur", formData.jalur);
      data.append("kondisi", formData.kondisi);
      data.append("keterangan", formData.keterangan);
      data.append("foto", formData.foto);

      const response = await axios.post("http://localhost:8000/api/inspeksi/add", data, {
        headers: { "Content-Type": "multipart/form-data" }
      });

      success("Data berhasil ditambahkan ke cache!");
      
      if (response.data.coordinates.latitude && response.data.coordinates.longitude) {
        info(`Koordinat berhasil diekstrak: ${response.data.coordinates.latitude}, ${response.data.coordinates.longitude}`);
      } else {
        info("Data ditambahkan, namun koordinat tidak berhasil diekstrak dari gambar");
      }

      setShowModal(false);
      setEditIndex(null);
      fetchCacheData();
      fetchStats();
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
    try {
      const item = cacheData[deleteIndex];
      await axios.delete(`http://localhost:8000/api/inspeksi/delete/${item.no}`);
      success("Data berhasil dihapus!");
      setShowDeleteModal(false);
      setDeleteIndex(null);
      fetchCacheData();
      fetchStats();
    } catch (err) {
      console.error("Error deleting data:", err);
      error(err.response?.data?.detail || "Gagal menghapus data");
    }
  };
// src/pages/Inspeksi.jsx - Update handleGenerate function
const handleGenerate = async () => {
  if (cacheData.length === 0) {
    error("Tidak ada data untuk di-generate");
    return;
  }

  setIsGenerating(true);
  
  try {
    console.log("🚀 Starting Excel generation from cache...");
    console.log("Cache data:", cacheData);

    // Gunakan endpoint generate-from-cache yang sudah ada
    const response = await axios.post("http://localhost:8000/api/inspeksi/generate-from-cache", {}, {
      responseType: "blob",
      timeout: 120000, // Increase timeout to 2 minutes
      headers: {
        'Content-Type': 'application/json'
      }
    });

    console.log("✅ Excel generation successful");

    // Download file
    const blob = new Blob([response.data], { 
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" 
    });
    const url = URL.createObjectURL(blob);
    const timestamp = dayjs().format("YYYYMMDD-HHmmss");
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `inspeksi-cache-${timestamp}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);

    success("Excel berhasil di-generate dari cache dengan koordinat!");
    
  } catch (err) {
    console.error("❌ Error generating Excel from cache:", err);
    
    // Handle different types of errors
    if (err.response) {
      // Server responded with error status
      console.error("Server response:", err.response.status, err.response.statusText);
      
      // Try to read error from blob if it's JSON
      if (err.response.data instanceof Blob) {
        try {
          const errorText = await err.response.data.text();
          console.error("Error details:", errorText);
          
          // Try to parse as JSON
          try {
            const errorJson = JSON.parse(errorText);
            error(`Server error: ${errorJson.detail || errorText}`);
          } catch {
            error(`Server error: ${errorText}`);
          }
        } catch {
          error(`Server error: ${err.response.status} ${err.response.statusText}`);
        }
      } else {
        error(err.response?.data?.detail || `Server error: ${err.response.status}`);
      }
    } else if (err.request) {
      // Network error
      console.error("Network error:", err.request);
      error("Network error: Tidak dapat terhubung ke server");
    } else {
      // Other error
      console.error("Error:", err.message);
      error(`Error: ${err.message}`);
    }
  } finally {
    setIsGenerating(false);
  }
};

  const handleSave = async () => {
    if (cacheData.length === 0) {
      error("Tidak ada data untuk disimpan");
      return;
    }

    const confirmSave = window.confirm(
      "Setelah disimpan, data cache akan dibersihkan dan halaman akan refresh. Lanjutkan?"
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

      const response = await axios.post("http://localhost:8000/api/inspeksi/save", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000
      });

      success(`Data berhasil disimpan ke history! Total: ${response.data.total_saved} data`);
      
      // Check if should refresh
      if (response.data.action === "refresh_page") {
        setTimeout(() => {
          window.location.reload();
        }, 2000);
      } else {
        fetchCacheData();
        fetchStats();
      }
      
    } catch (err) {
      console.error("Error saving data:", err);
      error(err.response?.data?.detail || "Gagal menyimpan data");
    } finally {
      setIsSaving(false);
    }
  };

  const handleClearCache = async () => {
    const confirmClear = window.confirm(
      "Yakin ingin menghapus semua data cache? Tindakan ini tidak dapat dibatalkan."
    );
    
    if (!confirmClear) return;

    try {
      await axios.delete("http://localhost:8000/api/inspeksi/clear-cache");
      success("Cache berhasil dibersihkan!");
      fetchCacheData();
      fetchStats();
    } catch (err) {
      console.error("Error clearing cache:", err);
      error(err.response?.data?.detail || "Gagal membersihkan cache");
    }
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

  return (
    <AdminLayout>
      {/* Header Section */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Inspeksi Lapangan</h1>
            <p className="text-gray-600">Input dan kelola data inspeksi infrastruktur</p>
          </div>
          <div className="flex items-center space-x-2">
            <div className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
              {cacheData.length} Data Cache
            </div>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Data Cache</p>
              <p className="text-2xl font-bold text-gray-900">{stats.cache.total_entries}</p>
            </div>
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">History Tersimpan</p>
              <p className="text-2xl font-bold text-purple-600">{stats.history.total_saved}</p>
            </div>
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">OCR Success Rate</p>
              <p className="text-2xl font-bold text-green-600">
                {Math.round(stats.ocr_accuracy.coordinate_extraction_rate)}%
              </p>
            </div>
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Valid Indonesia</p>
              <p className="text-2xl font-bold text-orange-600">
                {Math.round(stats.ocr_accuracy.valid_indonesia_rate)}%
              </p>
            </div>
            <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
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
              <span>Simpan ke History</span>
            </>
          )}
        </button>

        <button
          onClick={handleClearCache}
          disabled={cacheData.length === 0}
          className="flex items-center space-x-2 bg-gradient-to-r from-red-600 to-red-700 text-white px-6 py-3 rounded-xl hover:from-red-700 hover:to-red-800 transition-all duration-200 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
          <span>Clear Cache</span>
        </button>
      </div>

      {/* Data Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Data Cache Inspeksi</h3>
            <div className="text-sm text-gray-500">
              {cacheData.length} item dalam cache
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
            <h3 className="text-lg font-medium text-gray-900 mb-2">Belum ada data cache</h3>
            <p className="text-gray-500 mb-4">Mulai dengan menambahkan data inspeksi pertama.</p>
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
        title="Hapus Data Cache"
        message="Apakah Anda yakin ingin menghapus data ini dari cache?"
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