import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import AdminLayout from "../components/AdminLayout";
import AddEditModal from "../components/AddEditModal";
import dayjs from "dayjs";

const EditDashboard = () => {
  const { id } = useParams();
  const [data, setData] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editIndex, setEditIndex] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const res = await axios.get(`http://localhost:8000/api/history/${id}`);
      setData(res.data.data || []);
    } catch (err) {
      console.error("Error fetching data:", err);
      setError(err.response?.data?.detail || "Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) {
      fetchData();
    }
  }, [id]);

  const handleEdit = (index) => {
    setEditIndex(index);
    setShowModal(true);
  };

  const handleDelete = (index) => {
    const newData = [...data];
    newData.splice(index, 1);
    setData(newData);
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

  // ✅ Generate Excel dari history (tidak perlu kirim ulang gambar)
  const handleGenerateFromHistory = async () => {
    if (!id) {
      alert("ID history tidak valid");
      return;
    }

    setIsGenerating(true);
    try {
      const response = await axios.post(
        `http://localhost:8000/api/generate-from-history/${id}`,
        {},
        {
          responseType: "blob",
          timeout: 60000 // 60 detik timeout untuk generate
        }
      );

      const blob = new Blob([response.data], { 
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" 
      });
      const url = URL.createObjectURL(blob);
      const timestamp = dayjs().format("YYYYMMDD-HHmmss");
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `history-export-${timestamp}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      
    } catch (error) {
      console.error("Generate from history error:", error);
      let errorMessage = "Gagal generate Excel: ";
      
      if (error.response?.status === 404) {
        errorMessage += "History tidak ditemukan";
      } else if (error.response?.data) {
        // Handle blob error response
        if (error.response.data instanceof Blob) {
          const text = await error.response.data.text();
          try {
            const errorData = JSON.parse(text);
            errorMessage += errorData.detail || "Unknown error";
          } catch {
            errorMessage += "Server error";
          }
        } else {
          errorMessage += error.response.data.detail || "Unknown error";
        }
      } else {
        errorMessage += error.message;
      }
      
      alert(errorMessage);
    } finally {
      setIsGenerating(false);
    }
  };

  // ✅ Generate Excel dengan data yang sudah dimodifikasi (jika ada perubahan)
  const handleGenerateModified = async () => {
    if (data.length === 0) {
      alert("Tidak ada data untuk di-generate");
      return;
    }

    // Check if there are items without proper images
    const itemsWithoutImages = data.filter(item => 
      !item.foto_path && !item.foto && !item.is_from_history
    );

    if (itemsWithoutImages.length > 0) {
      const confirm = window.confirm(
        `${itemsWithoutImages.length} item tidak memiliki gambar. ` +
        "Generate tetap dilanjutkan tanpa gambar untuk item tersebut?"
      );
      if (!confirm) return;
    }

    setIsGenerating(true);
    const formData = new FormData();
    
    try {
      // Prepare data untuk generate
      for (let i = 0; i < data.length; i++) {
        const item = data[i];
        
        // Add entry data
        const entryData = {
          no: i + 1,
          jalur: item.jalur || "",
          kondisi: item.kondisi || "",
          keterangan: item.keterangan || ""
        };
        formData.append("entries", JSON.stringify(entryData));

        // Handle different types of foto data
        if (item.foto && item.foto instanceof File) {
          // New uploaded file
          formData.append("images", item.foto);
        } else if (item.foto_path && item.is_from_history) {
          // From history - need to fetch the image
          try {
            const imageResponse = await axios.get(
              `http://localhost:8000/api/history/image/${id}/${item.foto_filename}`,
              { responseType: 'blob' }
            );
            const imageFile = new File([imageResponse.data], item.foto_filename, {
              type: imageResponse.data.type
            });
            formData.append("images", imageFile);
          } catch (imgError) {
            console.error(`Failed to fetch image for item ${i+1}:`, imgError);
            // Create empty blob as placeholder
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

      const response = await axios.post("http://localhost:8000/api/generate", formData, {
        responseType: "blob",
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000
      });

      const blob = new Blob([response.data], { 
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" 
      });
      const url = URL.createObjectURL(blob);
      const timestamp = dayjs().format("YYYYMMDD-HHmmss");
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `modified-export-${timestamp}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      
    } catch (error) {
      console.error("Generate modified error:", error);
      alert("Gagal generate Excel: " + (error.response?.data?.detail || error.message));
    } finally {
      setIsGenerating(false);
    }
  };

  const getImageSrc = (item) => {
    if (item.foto && item.foto instanceof File) {
      return URL.createObjectURL(item.foto);
    } else if (item.foto_path && item.is_from_history && item.foto_filename) {
      return `http://localhost:8000/api/history/image/${id}/${item.foto_filename}`;
    }
    return null;
  };

  const getImageDisplayName = (item) => {
    if (item.foto && item.foto instanceof File) {
      return item.foto.name;
    } else if (item.foto_filename) {
      return item.original_filename || item.foto_filename;
    }
    return "-";
  };

  if (loading) {
    return (
      <AdminLayout>
        <div className="flex justify-center items-center h-64">
          <div className="flex items-center space-x-2">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <span className="text-lg">Loading history data...</span>
          </div>
        </div>
      </AdminLayout>
    );
  }

  if (error) {
    return (
      <AdminLayout>
        <div className="max-w-md mx-auto mt-8">
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            <strong className="font-bold">Error: </strong>
            <span>{error}</span>
          </div>
          <button 
            onClick={fetchData}
            className="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Edit History Data</h2>
            <p className="text-gray-600">ID: {id}</p>
          </div>
          <div className="flex items-center space-x-2">
            <div className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
              {data.length} Items
            </div>
          </div>
        </div>
        
        <div className="flex flex-wrap gap-3 mb-6">
          <button 
            onClick={() => {
              setEditIndex(null);
              setShowModal(true);
            }} 
            className="flex items-center space-x-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            <span>Tambah Data</span>
          </button>

          <button 
            onClick={handleGenerateFromHistory} 
            disabled={isGenerating}
            className="flex items-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isGenerating ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Generating...</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span>Generate Original</span>
              </>
            )}
          </button>

          <button 
            onClick={handleGenerateModified} 
            disabled={data.length === 0 || isGenerating}
            className="flex items-center space-x-2 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isGenerating ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Generating...</span>
              </>
            ) : (
              <>
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span>Generate Modified</span>
              </>
            )}
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full bg-white border border-gray-200 rounded-lg">
            <thead>
              <tr className="bg-gray-100 text-left text-gray-700 text-sm uppercase tracking-wider">
                <th className="px-4 py-2 border-b">No</th>
                <th className="px-4 py-2 border-b">Jalur</th>
                <th className="px-4 py-2 border-b">Kondisi</th>
                <th className="px-4 py-2 border-b">Keterangan</th>
                <th className="px-4 py-2 border-b">Foto</th>
                <th className="px-4 py-2 border-b">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {data.map((item, index) => (
                <tr key={index} className="hover:bg-gray-50 text-sm">
                  <td className="px-4 py-2 border-b">{index + 1}</td>
                  <td className="px-4 py-2 border-b">{item.jalur}</td>
                  <td className="px-4 py-2 border-b">{item.kondisi}</td>
                  <td className="px-4 py-2 border-b">{item.keterangan}</td>
                  <td className="px-4 py-2 border-b">
                    {getImageSrc(item) ? (
                      <img src={getImageSrc(item)} alt="preview" className="h-12 object-cover rounded" />
                    ) : (
                      <span className="text-gray-400 italic">Tidak ada foto</span>
                    )}
                    <div className="text-xs text-gray-500 mt-1">{getImageDisplayName(item)}</div>
                  </td>
                  <td className="px-4 py-2 border-b space-x-2">
                    <button 
                      onClick={() => handleEdit(index)} 
                      className="bg-yellow-400 text-white px-2 py-1 rounded hover:bg-yellow-500"
                    >
                      Edit
                    </button>
                    <button 
                      onClick={() => handleDelete(index)} 
                      className="bg-red-500 text-white px-2 py-1 rounded hover:bg-red-600"
                    >
                      Hapus
                    </button>
                  </td>
                </tr>
              ))}
              {data.length === 0 && (
                <tr>
                  <td colSpan="6" className="text-center text-gray-500 py-4">
                    Tidak ada data yang tersedia.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

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
    </AdminLayout>
  );
};

export default EditDashboard;
