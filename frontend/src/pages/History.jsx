import { useEffect, useState } from "react";
import axios from "axios";
import AdminLayout from "../components/AdminLayout";
import { useNavigate } from "react-router-dom";

const History = () => {
  const [history, setHistory] = useState([]);
  const navigate = useNavigate();

  const fetchHistory = async () => {
    try {
      const res = await axios.get("http://localhost:8000/api/history");
      setHistory(res.data);
    } catch (err) {
  console.error(err);
}

  };

  const handleEdit = (id) => {
    navigate(`/edit/${id}`);
  };

  const handleDelete = async (id) => {
    const confirm = window.confirm("Apakah yakin ingin menghapus data ini?");
    if (!confirm) return;

    try {
      await axios.delete(`http://localhost:8000/api/history/${id}`);
      setHistory(history.filter((item) => item._id !== id));
    } catch (err) {
  console.error(err);
}

  };

  useEffect(() => {
    fetchHistory();
  }, []);

  return (
    <AdminLayout>
      <h1 className="text-xl font-semibold mb-4">Riwayat Tabel Tersimpan</h1>

      <table className="w-full table-auto border bg-white text-sm">
        <thead className="bg-gray-100">
          <tr>
            <th className="border p-2">Tanggal Simpan</th>
            <th className="border p-2">Jumlah Data</th>
            <th className="border p-2">Aksi</th>
          </tr>
        </thead>
        <tbody>
          {history.map((item, i) => (
            <tr key={i}>
              <td className="border p-2">{new Date(item.saved_at).toLocaleString()}</td>
              <td className="border p-2">{item.data.length}</td>
              <td className="border p-2 flex gap-2">
                <button onClick={() => handleEdit(item._id)} className="text-blue-600">✏️</button>
                <button onClick={() => handleDelete(item._id)} className="text-red-600">🗑️</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </AdminLayout>
  );
};

export default History;
