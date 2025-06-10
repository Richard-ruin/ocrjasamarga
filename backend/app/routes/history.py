from fastapi import APIRouter, HTTPException
from app.config import history_collection, temp_collection
from datetime import datetime

router = APIRouter()

# 🔵 Ambil Semua History
@router.get("/history")
def get_all_history():
    all_data = list(history_collection.find({}, {"_id": 0}))
    return all_data

# 🔴 Hapus Riwayat berdasarkan timestamp
@router.delete("/history/delete/{timestamp}")
def delete_history(timestamp: str):
    result = history_collection.delete_one({"timestamp": timestamp})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return {"message": "Riwayat berhasil dihapus"}

# 🟡 Edit Riwayat: Load data ke dashboard
@router.post("/history/edit/{timestamp}")
def edit_history(timestamp: str):
    doc = history_collection.find_one({"timestamp": timestamp})
    if not doc:
        raise HTTPException(status_code=404, detail="Riwayat tidak ditemukan")

    temp_collection.delete_many({})  # bersihkan data dashboard
    # kembalikan data ke collection sementara
    for idx, d in enumerate(doc["data"], start=1):
        d["no"] = idx  # reset nomor urut
        temp_collection.insert_one(d)

    return {"message": "Data berhasil dimuat ke dashboard"}
