import { useState } from "react";

const AddEditModal = ({ initialData, onSave, onClose }) => {
  const [form, setForm] = useState({
    jalur: initialData?.jalur || "",
    kondisi: initialData?.kondisi || "Baik",
    keterangan: initialData?.keterangan || "",
    foto: initialData?.foto || null,
  });

  const handleChange = (e) => {
    const { name, value, files } = e.target;
    if (name === "foto") {
      setForm({ ...form, foto: files[0] });
    } else {
      setForm({ ...form, [name]: value });
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.foto) {
      alert("Silakan upload foto.");
      return;
    }
    onSave(form);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center">
      <form onSubmit={handleSubmit} className="bg-white p-6 rounded w-full max-w-lg shadow-lg space-y-4">
        <h2 className="text-xl font-bold">Input Data</h2>

        <input type="text" name="jalur" placeholder="Jalur" className="w-full border p-2" value={form.jalur} onChange={handleChange} required />
        
        <select name="kondisi" className="w-full border p-2" value={form.kondisi} onChange={handleChange}>
          <option value="Baik">Baik</option>
          <option value="Sedang">Sedang</option>
          <option value="Buruk">Buruk</option>
        </select>

        <textarea name="keterangan" placeholder="Keterangan" className="w-full border p-2" value={form.keterangan} onChange={handleChange} />

        <input type="file" name="foto" accept="image/png, image/jpeg" className="w-full border p-2" onChange={handleChange} />

        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="bg-gray-400 text-white px-4 py-2 rounded">Batal</button>
          <button type="submit" className="bg-green-600 text-white px-4 py-2 rounded">Simpan</button>
        </div>
      </form>
    </div>
  );
};

export default AddEditModal;
