import { useState } from "react";


const AddEditModal = ({ initialData, onSave, onClose }) => {
  const [form, setForm] = useState({
    jalur: initialData?.jalur || "",
    kondisi: initialData?.kondisi || "Baik",
    keterangan: initialData?.keterangan || "",
    foto: initialData?.foto || null,
  });
  
  // ✅ TAMBAHAN: Loading state
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.foto) {
      alert("Silakan upload foto.");
      return;
    }
    
    // ✅ Set loading state
    setIsLoading(true);
    
    try {
      await onSave(form);
    } catch (error) {
      console.error("Error saving data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value, files } = e.target;
    if (name === "foto") {
      setForm({ ...form, foto: files[0] });
    } else {
      setForm({ ...form, [name]: value });
    }
  };

  

  const getKondisiColor = (kondisi) => {
    switch (kondisi) {
      case "Baik": return "text-green-600 bg-green-50 border-green-200";
      case "Sedang": return "text-yellow-600 bg-yellow-50 border-yellow-200";
      case "Buruk": return "text-red-600 bg-red-50 border-red-200";
      default: return "text-gray-600 bg-gray-50 border-gray-200";
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-white">
                {initialData ? "Edit Data" : "Tambah Data Baru"}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="text-white/70 hover:text-white transition-colors p-1"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6 max-h-[calc(90vh-80px)] overflow-y-auto">
          {/* Jalur */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Nama Jalur <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              name="jalur"
              placeholder="Contoh: A"
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 bg-gray-50 focus:bg-white"
              value={form.jalur}
              onChange={handleChange}
              required
            />
          </div>

          {/* Kondisi */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Kondisi Infrastruktur
            </label>
            <select
              name="kondisi"
              className={`w-full px-4 py-3 border rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 font-medium ${getKondisiColor(form.kondisi)}`}
              value={form.kondisi}
              onChange={handleChange}
            >
              <option value="Baik">🟢 Baik</option>
              <option value="Sedang">🟡 Sedang</option>
              <option value="Buruk">🔴 Buruk</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Pilih kondisi berdasarkan evaluasi visual infrastruktur
            </p>
          </div>

          {/* Keterangan */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Keterangan Detail
            </label>
            <textarea
              name="keterangan"
              placeholder="Jelaskan detail kondisi, kerusakan, atau catatan penting lainnya..."
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 bg-gray-50 focus:bg-white resize-none"
              rows="4"
              value={form.keterangan}
              onChange={handleChange}
            />
          </div>

          {/* Upload Foto */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Upload Foto <span className="text-red-500">*</span>
            </label>
            <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center hover:border-blue-400 transition-colors">
              <input
                type="file"
                name="foto"
                accept="image/png, image/jpeg, image/jpg"
                className="hidden"
                id="foto-upload"
                onChange={handleChange}
              />
              <label htmlFor="foto-upload" className="cursor-pointer">
                <div className="space-y-3">
                  <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center mx-auto">
                    <svg className="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-blue-600 font-medium">Klik untuk upload foto</p>
                    <p className="text-xs text-gray-500 mt-1">PNG, JPG hingga 10MB</p>
                  </div>
                  {form.foto && (
                    <div className="mt-3 p-2 bg-green-50 border border-green-200 rounded-lg">
                      <p className="text-sm text-green-700 font-medium">
                        ✓ {form.foto.name || "File terpilih"}
                      </p>
                    </div>
                  )}
                </div>
              </label>
            </div>
          </div>

          {/* Buttons */}
          <div className="flex justify-end space-x-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              className="px-6 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors font-medium"
            >
              Batal
            </button>
            <button
    type="submit"
    disabled={isLoading}
    className={`px-6 py-3 rounded-xl font-medium shadow-lg hover:shadow-xl flex items-center space-x-2 transition-all duration-200 ${
      isLoading 
        ? 'bg-gray-400 cursor-not-allowed' 
        : 'bg-gradient-to-r from-green-600 to-green-700 text-white hover:from-green-700 hover:to-green-800'
    }`}
  >
    {isLoading ? (
      <>
        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
        <span>Menyimpan...</span>
      </>
    ) : (
      <>
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
        <span>Simpan Data</span>
      </>
    )}
  </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddEditModal;