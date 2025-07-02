import { useState } from "react";
import AdminLayout from "../components/AdminLayout";
import AddEditModal from "../components/AddEditModal";
import ConfirmModal from "../components/ConfirmModal";
import axios from "axios";
import dayjs from "dayjs";

const Dashboard = () => {
  const [data, setData] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [editIndex, setEditIndex] = useState(null);
  const [deleteIndex, setDeleteIndex] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleEdit = (index) => {
    setEditIndex(index);
    setShowModal(true);
  };

  const handleDeleteClick = (index) => {
    setDeleteIndex(index);
    setShowConfirmModal(true);
  };

  const handleDelete = () => {
    const newData = [...data];
    newData.splice(deleteIndex, 1);
    setData(newData);
    setShowConfirmModal(false);
    setDeleteIndex(null);
  };

  const handleSave = (entry) => {
    if (editIndex !== null) {
      const newData = [...data];
      newData[editIndex] = entry;
      setData(newData);
    } else {
      setData([...data, entry]);
    }
    setShowModal(false);
    setEditIndex(null);
  };

  const handleSaveData = async () => {
    if (data.length === 0) {
      alert("Tidak ada data untuk disimpan.");
      return;
    }

    const formData = new FormData();
    data.forEach((item, i) => {
      formData.append("entries", JSON.stringify({
        no: i + 1,
        jalur: item.jalur,
        kondisi: item.kondisi,
        keterangan: item.keterangan
      }));
      formData.append("images", item.foto);
    });

    try {
      await axios.post("http://localhost:8000/api/save", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      alert("Data berhasil disimpan!");
      setData([]);
    } catch (error) {
      alert("Gagal menyimpan data: " + error.message);
    }
  };

  const handleGenerate = async () => {
    if (data.length === 0) {
      alert("Tidak ada data untuk di-generate.");
      return;
    }

    setIsGenerating(true);
    const formData = new FormData();
    data.forEach((item, i) => {
      formData.append("entries", JSON.stringify({
        no: i + 1,
        jalur: item.jalur,
        kondisi: item.kondisi,
        keterangan: item.keterangan
      }));
      formData.append("images", item.foto);
    });

    const timestamp = dayjs().format("YYYYMMDD-HHmmss");

    try {
      const response = await axios.post("http://localhost:8000/api/generate", formData, {
        responseType: "blob",
        headers: { "Content-Type": "multipart/form-data" },
      });

      const blob = new Blob([response.data], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `output-${timestamp}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      alert("Gagal generate: " + error.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const getKondisiColor = (kondisi) => {
    switch (kondisi) {
      case "Baik": return "bg-green-100 text-green-800 border-green-200";
      case "Sedang": return "bg-yellow-100 text-yellow-800 border-yellow-200";
      case "Buruk": return "bg-red-100 text-red-800 border-red-200";
      default: return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const getKondisiIcon = (kondisi) => {
    switch (kondisi) {
      case "Baik": return "🟢";
      case "Sedang": return "🟡";
      case "Buruk": return "🔴";
      default: return "⚪";
    }
  };

  return (
    <AdminLayout>
      {/* Header Section */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Dashboard OCR</h1>
            <p className="text-gray-600">Kelola data infrastruktur Jasa Marga</p>
          </div>
          <div className="flex items-center space-x-2">
            <div className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
              {data.length} Data
            </div>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Total Data</p>
              <p className="text-2xl font-bold text-gray-900">{data.length}</p>
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
              <p className="text-sm text-gray-600 mb-1">Kondisi Baik</p>
              <p className="text-2xl font-bold text-green-600">{data.filter(item => item.kondisi === 'Baik').length}</p>
            </div>
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <span className="text-2xl">🟢</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Kondisi Sedang</p>
              <p className="text-2xl font-bold text-yellow-600">{data.filter(item => item.kondisi === 'Sedang').length}</p>
            </div>
            <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
              <span className="text-2xl">🟡</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Kondisi Buruk</p>
              <p className="text-2xl font-bold text-red-600">{data.filter(item => item.kondisi === 'Buruk').length}</p>
            </div>
            <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
              <span className="text-2xl">🔴</span>
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
          onClick={handleSaveData}
          disabled={data.length === 0}
          className="flex items-center space-x-2 bg-gradient-to-r from-blue-600 to-blue-700 text-white px-6 py-3 rounded-xl hover:from-blue-700 hover:to-blue-800 transition-all duration-200 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
          </svg>
          <span>Simpan Data</span>
        </button>

        <button
          onClick={handleGenerate}
          disabled={data.length === 0 || isGenerating}
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
      </div>

      {/* Data Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Data Infrastruktur</h3>
        </div>
        
        {data.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Belum ada data</h3>
            <p className="text-gray-500 mb-4">Mulai dengan menambahkan data infrastruktur pertama Anda.</p>
            <button
              onClick={() => setShowModal(true)}
              className="inline-flex items-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
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
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Foto</th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Aksi</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data.map((item, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">{i + 1}</td>
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
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <div className="flex items-center space-x-2">
                        <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        <span className="truncate max-w-20">{item.foto?.name || "-"}</span>
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

      {/* Modals */}
      {showModal && (
        <AddEditModal
          initialData={editIndex !== null ? data[editIndex] : null}
          onSave={handleSave}
          onClose={() => {
            setShowModal(false);
            setEditIndex(null);
          }}
        />
      )}

      {showConfirmModal && (
        <ConfirmModal
          title="Konfirmasi Hapus"
          message="Apakah Anda yakin ingin menghapus data ini? Tindakan ini tidak dapat dibatalkan."
          onConfirm={handleDelete}
          onCancel={() => {
            setShowConfirmModal(false);
            setDeleteIndex(null);
          }}
        />
      )}
    </AdminLayout>
  );
};

export default Dashboard;