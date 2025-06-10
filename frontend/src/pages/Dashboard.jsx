import { useState } from "react";
import AdminLayout from "../components/AdminLayout";
import AddEditModal from "../components/AddEditModal";
import axios from "axios";
import dayjs from "dayjs";

const Dashboard = () => {
  const [data, setData] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editIndex, setEditIndex] = useState(null);

  const handleAdd = () => {
    setEditIndex(null);
    setShowModal(true);
  };

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
  };

  const handleGenerate = async () => {
    const formData = new FormData();
    data.forEach((item, i) => {
      formData.append("entries", JSON.stringify({
        no: i + 1,
        jalur: item.jalur,
        kondisi: item.kondisi,
        keterangan: item.keterangan
      }));
      formData.append("images", item.foto); // input image
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
    }
  };

  const handleSimpan = async () => {
    try {
      const payload = {
        data,
        saved_at: new Date().toISOString(),
      };
      await axios.post("http://localhost:8000/api/save", payload);
      alert("Data berhasil disimpan.");
      setData([]);
    } catch (error) {
      alert("Gagal menyimpan data: " + error.message);
    }
  };

  return (
    <AdminLayout>
      <div className="flex gap-4 mb-4">
        <button onClick={handleAdd} className="bg-green-600 text-white px-4 py-2 rounded">Tambah</button>
        <button onClick={handleGenerate} className="bg-blue-600 text-white px-4 py-2 rounded">Generate</button>
        <button onClick={handleSimpan} className="bg-purple-600 text-white px-4 py-2 rounded">Simpan</button>
      </div>

      <table className="w-full table-auto border text-sm bg-white shadow">
        <thead>
          <tr className="bg-gray-100">
            <th className="border p-2">No</th>
            <th className="border p-2">Jalur</th>
            <th className="border p-2">Kondisi</th>
            <th className="border p-2">Keterangan</th>
            <th className="border p-2">Foto</th>
            <th className="border p-2">Aksi</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item, i) => (
            <tr key={i}>
              <td className="border p-2">{i + 1}</td>
              <td className="border p-2">{item.jalur}</td>
              <td className="border p-2">{item.kondisi}</td>
              <td className="border p-2">{item.keterangan}</td>
              <td className="border p-2">{item.foto?.name}</td>
              <td className="border p-2 flex gap-2">
                <button onClick={() => handleEdit(i)} className="text-blue-600">✏️</button>
                <button onClick={() => handleDelete(i)} className="text-red-600">🗑️</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showModal && (
        <AddEditModal
          initialData={editIndex !== null ? data[editIndex] : null}
          onSave={handleSave}
          onClose={() => setShowModal(false)}
        />
      )}
    </AdminLayout>
  );
};

export default Dashboard;
